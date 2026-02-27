from io import BytesIO
from decimal import Decimal
from datetime import datetime, time, timedelta
from urllib.parse import urlencode
import json
import csv

from django.conf import settings
from django.db import DatabaseError, transaction
from django.db.models import Count, F, Sum, Value, DecimalField, ExpressionWrapper
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.generic import TemplateView
from django.views import View
from django.contrib.admin.views.decorators import staff_member_required

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .admin_repositories import AdminRepository
from .admin_services import AdminAnalyticsService
from .analytics import sales_summary, category_sales, top_products, unavailable_product_demand
from .models import Bill
from .models import Order, OrderItem, OrderFeedback, BillItem, SalesRecord, ServiceablePincode
from .serializers import OrderSerializer, OrderFeedbackWriteSerializer, BillSerializer
from .services import create_order, create_order_from_cart
from products.cache_utils import invalidate_catalog_cache
from products.models import Category, Product, Section
from users.customer_resolver import resolve_primary_customer
from .pincode_service import normalize_pincode


class CreateOrderAPIView(APIView):
    """
    Handles:
    - Add to cart checkout
    - Buy now single product
    """

    def post(self, request):
        serializer = OrderSerializer(data=request.data)

        if serializer.is_valid():
            try:
                order = create_order(serializer.validated_data)

                return Response(
                    {
                        "message": "Order placed successfully 🎉",
                        "order_id": order.id,
                        "total_price": order.total_price,
                        "status": order.status,
                    },
                    status=status.HTTP_201_CREATED,
                )

            except Exception as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

            except DatabaseError:
                return Response(
                    {"error": "System busy, please try again"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BillsByOrderAPIView(APIView):
    def get(self, request, order_id):
        bills = Bill.objects.filter(order_id=order_id).prefetch_related("items")
        if not bills.exists():
            return Response({"error": "Bills not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = BillSerializer(bills, many=True)
        return Response(serializer.data)


class CustomerHistoryByPhoneAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        phone = (request.GET.get("phone") or "").strip()
        if not phone:
            return Response(
                {"detail": "phone query param is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        customer = resolve_primary_customer(phone=phone, create_if_missing=False)
        if not customer:
            return Response(
                {
                    "exists": False,
                    "customer": None,
                    "orders": [],
                }
            )

        orders = list(
            # Use indexed customer FK and prefetch line items to avoid N+1 in history payload.
            Order.objects.filter(customer_id=customer.id)
            .select_related("feedback")
            .prefetch_related("items__product")
            .order_by("-created_at")
        )
        order_payload = []
        for order in orders:
            feedback_obj = getattr(order, "feedback", None)
            order_payload.append(
                {
                    "id": order.id,
                    "created_at": order.created_at,
                    "status": order.status,
                    "total_price": str(order.total_price),
                    "items": [
                        {
                            "product_name": item.product.name,
                            "quantity": item.quantity,
                            "price": str(item.price),
                        }
                        for item in order.items.all()
                    ],
                    "feedback": (
                        {
                            "id": feedback_obj.id,
                            "rating": feedback_obj.rating,
                            "message": feedback_obj.message,
                            "created_at": feedback_obj.created_at,
                            "updated_at": feedback_obj.updated_at,
                        }
                        if feedback_obj
                        else None
                    ),
                }
            )

        return Response(
            {
                "exists": True,
                "customer": {
                    "name": customer.name,
                    "phone": customer.phone,
                    "whatsapp_no": customer.whatsapp_no,
                    "address": customer.address,
                },
                "orders": order_payload,
            }
        )


class OrderFeedbackAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @staticmethod
    def _normalize_phone(value):
        return "".join(ch for ch in str(value or "") if ch.isdigit())

    def post(self, request):
        serializer = OrderFeedbackWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        order_id = serializer.validated_data["order_id"]
        phone = serializer.validated_data["phone"]
        message = serializer.validated_data["message"]
        rating = serializer.validated_data.get("rating")

        order = Order.objects.filter(id=order_id).first()
        if not order:
            return Response({"detail": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        if self._normalize_phone(order.phone) != self._normalize_phone(phone):
            return Response(
                {"detail": "This order is not linked to this phone number."},
                status=status.HTTP_403_FORBIDDEN,
            )

        feedback, created = OrderFeedback.objects.update_or_create(
            order=order,
            defaults={
                "phone": (order.phone or phone).strip(),
                "rating": rating,
                "message": message,
            },
        )

        return Response(
            {
                "detail": "Feedback saved successfully.",
                "created": created,
                "feedback": {
                    "id": feedback.id,
                    "order_id": order.id,
                    "phone": feedback.phone,
                    "rating": feedback.rating,
                    "message": feedback.message,
                    "updated_at": feedback.updated_at,
                },
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class ServiceablePincodeListAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        rows = ServiceablePincode.objects.filter(is_active=True).order_by("code")[:200]
        payload = [
            {
                "code": row.code,
                "area_name": row.area_name,
                "label": f"{row.code}{(' - ' + row.area_name) if row.area_name else ''}",
            }
            for row in rows
        ]
        return Response({"pincodes": payload})


@method_decorator(cache_page(60), name="dispatch")
class AdminAnalyticsAPIView(APIView):
    def get(self, request):
        data = {
            "sales_summary": sales_summary(),
            "category_sales": category_sales(),
            "top_products": top_products(),
            "unavailable_product_demand": unavailable_product_demand(),
        }
        return Response(data)


@method_decorator(staff_member_required, name="dispatch")
class AdminDashboardView(TemplateView):
    template_name = "orders/admin_dashboard.html"


@method_decorator(staff_member_required, name="dispatch")
class AdminPincodeManageView(TemplateView):
    template_name = "orders/admin_pincode_manage.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["rows"] = ServiceablePincode.objects.order_by("code")
        context["saved"] = self.request.GET.get("saved", "")
        context["error"] = kwargs.get("error") or self.request.GET.get("error") or ""
        return context

    def post(self, request, *args, **kwargs):
        action = (request.POST.get("action") or "add").strip().lower()

        if action == "toggle":
            code = normalize_pincode(request.POST.get("code"))
            target = (request.POST.get("target") or "").strip()
            if not code or target not in {"0", "1"}:
                context = self.get_context_data(error="Invalid pincode status update request.")
                return self.render_to_response(context, status=400)

            updated = ServiceablePincode.objects.filter(code=code).update(is_active=(target == "1"))
            if not updated:
                context = self.get_context_data(error="Pincode not found.")
                return self.render_to_response(context, status=404)

            return redirect("/admin-dashboard/pincodes/?saved=status")

        code = normalize_pincode(request.POST.get("code"))
        area_name = (request.POST.get("area_name") or "").strip()
        is_active = (request.POST.get("is_active") or "").strip().lower() in {"1", "true", "on", "yes"}

        if not code:
            context = self.get_context_data(error="Enter a valid 6-digit pincode.")
            return self.render_to_response(context, status=400)

        ServiceablePincode.objects.update_or_create(
            code=code,
            defaults={
                "area_name": area_name,
                "is_active": is_active,
            },
        )
        return redirect("/admin-dashboard/pincodes/?saved=1")


@method_decorator(staff_member_required, name="dispatch")
class AdminOrderDetailsView(TemplateView):
    template_name = "orders/admin_order_details.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        phone = (self.request.GET.get("phone") or "").strip()
        rows = OrderItem.objects.select_related("order", "order__feedback", "product")
        if phone:
            rows = rows.filter(order__phone__icontains=phone)
        rows = rows.order_by("-order__created_at", "-order_id", "id")
        context["rows"] = rows
        context["query_phone"] = phone
        return context


@method_decorator(staff_member_required, name="dispatch")
class AdminBillingListView(TemplateView):
    template_name = "orders/admin_billing_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        phone = (self.request.GET.get("phone") or "").strip()
        rows = Bill.objects.filter(recipient_type="ADMIN").select_related("order")
        if phone:
            rows = rows.filter(phone__icontains=phone)
        context["rows"] = rows.prefetch_related("items").order_by("-created_at")[:150]
        context["query_phone"] = phone
        return context


@method_decorator(staff_member_required, name="dispatch")
class AdminBillDetailView(TemplateView):
    template_name = "orders/admin_bill_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        bill_id = kwargs.get("bill_id")
        bill = get_object_or_404(
            Bill.objects.filter(recipient_type="ADMIN").select_related("order").prefetch_related("items"),
            id=bill_id,
        )
        item_rows = [
            {
                "product_name": item.product_name,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "line_total": item.unit_price * Decimal(item.quantity),
            }
            for item in bill.items.all()
        ]
        context["bill"] = bill
        context["item_rows"] = item_rows
        context["is_cancelled"] = _is_cancelled_status(bill.order.status)
        return context


def _is_cancelled_status(status_value):
    return str(status_value or "").strip().lower() == "cancelled"


@method_decorator(staff_member_required, name="dispatch")
class AdminBillEditView(TemplateView):
    template_name = "orders/admin_bill_edit.html"

    def _get_bill(self):
        return get_object_or_404(
            Bill.objects.filter(recipient_type="ADMIN").select_related("order").prefetch_related("items"),
            id=self.kwargs.get("bill_id"),
        )

    @staticmethod
    def _parse_item_qty(raw_value):
        text = str(raw_value or "").strip()
        if text == "":
            raise ValueError("Quantity is required for each product.")
        try:
            qty = int(text)
        except (TypeError, ValueError):
            raise ValueError("Quantity must be a valid number.")
        if qty < 0:
            raise ValueError("Quantity cannot be negative.")
        return qty

    def _build_order_item_rows(self, order_id):
        rows = []
        items = OrderItem.objects.select_related("product").filter(order_id=order_id).order_by("id")
        for item in items:
            rows.append(
                {
                    "id": item.id,
                    "product_name": item.product.name,
                    "product_stock_qty": item.product.stock_qty,
                    "quantity": item.quantity,
                    "unit_price": item.price,
                    "line_total": item.price * Decimal(item.quantity),
                }
            )
        return rows

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        bill = kwargs.get("bill") or self._get_bill()
        context["bill"] = bill
        context["order_item_rows"] = kwargs.get("order_item_rows") or self._build_order_item_rows(bill.order_id)
        context["is_cancelled"] = _is_cancelled_status(bill.order.status)
        context["saved"] = self.request.GET.get("saved") == "1"
        context["error"] = kwargs.get("error") or self.request.GET.get("error") or ""
        return context

    def post(self, request, *args, **kwargs):
        bill = self._get_bill()
        customer_name = (request.POST.get("customer_name") or "").strip()
        phone = (request.POST.get("phone") or "").strip()
        shipping_address = (request.POST.get("shipping_address") or "").strip()

        if not customer_name or not phone or not shipping_address:
            context = self.get_context_data(
                bill=bill,
                order_item_rows=self._build_order_item_rows(bill.order_id),
                error="Customer name, phone number, and address are required.",
            )
            return self.render_to_response(context, status=400)

        with transaction.atomic():
            order = Order.objects.select_for_update().get(id=bill.order_id)
            if _is_cancelled_status(order.status):
                return redirect(f"/admin-dashboard/billing/{bill.id}/edit/?error=cancelled")

            order_items = list(
                OrderItem.objects.select_for_update()
                .select_related("product")
                .filter(order_id=order.id)
                .order_by("id")
            )
            if not order_items:
                context = self.get_context_data(
                    bill=bill,
                    order_item_rows=[],
                    error="No order items found for this bill.",
                )
                return self.render_to_response(context, status=400)

            product_ids = [item.product_id for item in order_items]
            products_by_id = {
                product.id: product
                for product in Product.objects.select_for_update().filter(id__in=product_ids)
            }

            new_quantities = {}
            for item in order_items:
                raw_qty = request.POST.get(f"item_qty_{item.id}")
                try:
                    parsed_qty = self._parse_item_qty(raw_qty)
                except ValueError as exc:
                    context = self.get_context_data(
                        bill=bill,
                        order_item_rows=self._build_order_item_rows(order.id),
                        error=f"{item.product.name}: {exc}",
                    )
                    return self.render_to_response(context, status=400)
                new_quantities[item.id] = parsed_qty

            if not any(qty > 0 for qty in new_quantities.values()):
                context = self.get_context_data(
                    bill=bill,
                    order_item_rows=self._build_order_item_rows(order.id),
                    error="At least one product quantity must be greater than zero.",
                )
                return self.render_to_response(context, status=400)

            net_delta_by_product = {}
            for item in order_items:
                target_qty = new_quantities[item.id]
                delta = target_qty - item.quantity
                net_delta_by_product[item.product_id] = net_delta_by_product.get(item.product_id, 0) + delta

            for product_id, net_delta in net_delta_by_product.items():
                if net_delta <= 0:
                    continue
                product = products_by_id.get(product_id)
                product_name = next(
                    (row.product.name for row in order_items if row.product_id == product_id),
                    f"Product #{product_id}",
                )
                if not product:
                    context = self.get_context_data(
                        bill=bill,
                        order_item_rows=self._build_order_item_rows(order.id),
                        error=f"Product not found for {product_name}.",
                    )
                    return self.render_to_response(context, status=400)
                if product.stock_qty < net_delta:
                    context = self.get_context_data(
                        bill=bill,
                        order_item_rows=self._build_order_item_rows(order.id),
                        error=(
                            f"Insufficient stock for {product_name}. "
                            f"Available: {product.stock_qty}, requested extra: {net_delta}."
                        ),
                    )
                    return self.render_to_response(context, status=400)

            for product_id, net_delta in net_delta_by_product.items():
                if net_delta == 0:
                    continue
                product = products_by_id.get(product_id)
                if not product:
                    continue
                product.stock_qty = product.stock_qty - net_delta
                product.is_available = product.stock_qty > 0
                product.save(update_fields=["stock_qty", "is_available"])

            for item in order_items:
                target_qty = new_quantities[item.id]
                if target_qty == 0:
                    item.delete()
                elif target_qty != item.quantity:
                    item.quantity = target_qty
                    item.save(update_fields=["quantity"])

            updated_items = list(
                OrderItem.objects.select_related("product")
                .filter(order_id=order.id)
                .order_by("id")
            )

            new_total = sum(
                (item.price * Decimal(item.quantity) for item in updated_items),
                Decimal("0.00"),
            )

            order.customer_name = customer_name
            order.phone = phone
            order.shipping_address = shipping_address
            order.total_price = new_total
            order.save(update_fields=["customer_name", "phone", "shipping_address", "total_price"])

            order_bills = list(Bill.objects.filter(order_id=order.id))
            for order_bill in order_bills:
                order_bill.customer_name = customer_name
                order_bill.phone = phone
                order_bill.shipping_address = shipping_address
                order_bill.total_amount = new_total

            Bill.objects.bulk_update(
                order_bills,
                ["customer_name", "phone", "shipping_address", "total_amount"],
            )

            bill_ids = [order_bill.id for order_bill in order_bills]
            BillItem.objects.filter(bill_id__in=bill_ids).delete()
            new_bill_items = []
            for order_bill in order_bills:
                for order_item in updated_items:
                    new_bill_items.append(
                        BillItem(
                            bill_id=order_bill.id,
                            product_name=order_item.product.name,
                            quantity=order_item.quantity,
                            unit_price=order_item.price,
                        )
                    )
            if new_bill_items:
                BillItem.objects.bulk_create(new_bill_items)

        return redirect(f"/admin-dashboard/billing/{bill.id}/edit/?saved=1")


class AdminBillingDataAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        limit = min(max(int(request.GET.get("limit", 150) or 150), 1), 500)
        phone = (request.GET.get("phone") or "").strip()
        bills = Bill.objects.filter(recipient_type="ADMIN").select_related("order")
        if phone:
            bills = bills.filter(phone__icontains=phone)
        bills = bills.prefetch_related("items").order_by("-created_at")[:limit]

        payload = []
        for bill in bills:
            items = [
                {
                    "product_name": item.product_name,
                    "quantity": item.quantity,
                    "unit_price": str(item.unit_price),
                    "line_total": str(item.unit_price * Decimal(item.quantity)),
                }
                for item in bill.items.all()
            ]
            payload.append(
                {
                    "id": bill.id,
                    "bill_number": bill.bill_number,
                    "customer_name": bill.customer_name,
                    "phone": bill.phone,
                    "shipping_address": bill.shipping_address,
                    "total_amount": str(bill.total_amount),
                    "created_at": bill.created_at,
                    "order_status": bill.order.status,
                    "is_cancelled": _is_cancelled_status(bill.order.status),
                    "items": items,
                }
            )
        return Response({"bills": payload})


class AdminBillCancelAPIView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, bill_id):
        with transaction.atomic():
            bill = get_object_or_404(
                Bill.objects.filter(recipient_type="ADMIN").select_related("order"),
                id=bill_id,
            )
            order = Order.objects.select_for_update().get(id=bill.order_id)

            if _is_cancelled_status(order.status):
                return Response(
                    {
                        "detail": "Bill is already cancelled.",
                        "already_cancelled": True,
                        "order_status": order.status,
                    },
                    status=status.HTTP_200_OK,
                )

            order_items = list(OrderItem.objects.select_related("product").filter(order_id=order.id))
            product_ids = [item.product_id for item in order_items]
            if product_ids:
                Product.objects.select_for_update().filter(id__in=product_ids)

            for item in order_items:
                Product.objects.filter(id=item.product_id).update(
                    stock_qty=F("stock_qty") + item.quantity,
                    is_available=True,
                )

            order.status = "Cancelled"
            order.save(update_fields=["status"])
            SalesRecord.objects.filter(order_id=order.id).delete()
            invalidate_catalog_cache()

        return Response(
            {
                "detail": "Bill cancelled and stock restored successfully.",
                "bill_id": bill.id,
                "order_id": order.id,
                "order_status": order.status,
                "is_cancelled": True,
            },
            status=status.HTTP_200_OK,
        )


def _sales_today_window():
    now = timezone.localtime()
    day = now.date()
    start_dt = datetime.combine(day, time(hour=6, minute=0, second=0))
    end_dt = datetime.combine(day, time(hour=23, minute=59, second=59, microsecond=999999))
    if settings.USE_TZ:
        tz = timezone.get_current_timezone()
        start_dt = timezone.make_aware(start_dt, tz)
        end_dt = timezone.make_aware(end_dt, tz)
    return start_dt, end_dt


def _parse_date(date_text):
    if not date_text:
        return None
    try:
        return datetime.strptime(date_text, "%Y-%m-%d").date()
    except ValueError:
        return None


def _month_bounds(day):
    first = day.replace(day=1)
    if first.month == 12:
        next_month = first.replace(year=first.year + 1, month=1, day=1)
    else:
        next_month = first.replace(month=first.month + 1, day=1)
    last = next_month - timedelta(days=1)
    return first, last


def _window_to_datetimes(start_day, end_day):
    start_dt = datetime.combine(start_day, time(hour=6, minute=0, second=0))
    end_dt = datetime.combine(end_day, time(hour=23, minute=59, second=59, microsecond=999999))
    if settings.USE_TZ:
        tz = timezone.get_current_timezone()
        start_dt = timezone.make_aware(start_dt, tz)
        end_dt = timezone.make_aware(end_dt, tz)
    return start_dt, end_dt


def _period_window(period, base_day):
    period = (period or "daily").strip().lower()
    if period not in {"daily", "weekly", "monthly", "yearly"}:
        period = "daily"

    start_day = base_day
    end_day = base_day
    if period == "weekly":
        start_day = base_day - timedelta(days=base_day.weekday())
        end_day = start_day + timedelta(days=6)
    elif period == "monthly":
        start_day, end_day = _month_bounds(base_day)
    elif period == "yearly":
        start_day = base_day.replace(month=1, day=1)
        end_day = base_day.replace(month=12, day=31)

    return period, _window_to_datetimes(start_day, end_day)


def _resolve_section_by_slug(raw_slug):
    raw_slug = (raw_slug or "").strip().lower()
    section_slug = "bakery" if raw_slug in {"bakery", "backery"} else raw_slug
    if section_slug == "bakery":
        section = (
            Section.objects.filter(name__iexact="Bakery").first()
            or Section.objects.filter(name__iexact="Backery").first()
        )
    elif section_slug == "snacks":
        section = Section.objects.filter(name__iexact="Snacks").first()
    else:
        section = Section.objects.filter(name__iexact=raw_slug).first()

    if not section:
        section = (
            Section.objects.filter(name__iexact="Bakery").first()
            or Section.objects.filter(name__iexact="Backery").first()
            or get_object_or_404(Section, name__iexact="Snacks")
        )
        section_slug = "bakery" if section.name.lower() in {"bakery", "backery"} else section.name.lower()
    return section, section_slug


def _section_category_sales_rows(section, start_dt, end_dt):
    category_names = list(
        Category.objects.filter(section=section).values_list("name", flat=True).order_by("name")
    )
    qs = SalesRecord.objects.filter(
        sold_at__gte=start_dt,
        sold_at__lte=end_dt,
        category__in=category_names,
    )
    rows = list(
        qs.values("category")
        .annotate(
            total_qty=Coalesce(Sum("quantity"), Value(0)),
            total_amount=Coalesce(
                Sum(_sales_line_total_expr()),
                Value(Decimal("0.00"), output_field=DecimalField(max_digits=14, decimal_places=2)),
            ),
        )
        .order_by("-total_amount", "category")
    )
    return qs, rows


def _sales_window_from_request(request):
    now = timezone.localtime()
    today = now.date()

    range_key = (request.GET.get("range") or "daily").strip().lower()
    if range_key not in {"daily", "weekly", "monthly", "custom"}:
        range_key = "daily"

    date_input = (request.GET.get("date") or "").strip()
    start_date_input = (request.GET.get("start_date") or "").strip()
    end_date_input = (request.GET.get("end_date") or "").strip()

    base_day = _parse_date(date_input) or today
    start_day = base_day
    end_day = base_day

    if range_key == "weekly":
        start_day = base_day - timedelta(days=base_day.weekday())
        end_day = start_day + timedelta(days=6)
    elif range_key == "monthly":
        start_day, end_day = _month_bounds(base_day)
    elif range_key == "custom":
        custom_start = _parse_date(start_date_input)
        custom_end = _parse_date(end_date_input)
        if custom_start and custom_end:
            if custom_end < custom_start:
                custom_start, custom_end = custom_end, custom_start
            start_day = custom_start
            end_day = custom_end
        elif custom_start:
            start_day = custom_start
            end_day = custom_start
        elif custom_end:
            start_day = custom_end
            end_day = custom_end

    start_dt, end_dt = _window_to_datetimes(start_day, end_day)

    query_params = {"range": range_key}
    if range_key in {"daily", "weekly", "monthly"}:
        query_params["date"] = base_day.isoformat()
    elif range_key == "custom":
        query_params["start_date"] = start_day.isoformat()
        query_params["end_date"] = end_day.isoformat()

    return {
        "range_key": range_key,
        "start_dt": start_dt,
        "end_dt": end_dt,
        "date_input": base_day.isoformat(),
        "start_date_input": start_day.isoformat(),
        "end_date_input": end_day.isoformat(),
        "query_params": query_params,
        "query_string": urlencode(query_params),
    }


def _sales_line_total_expr():
    return ExpressionWrapper(
        F("price") * F("quantity"),
        output_field=DecimalField(max_digits=14, decimal_places=2),
    )


@method_decorator(staff_member_required, name="dispatch")
class AdminSalesAnalyticsView(TemplateView):
    template_name = "orders/admin_sales_analytics.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        window = _sales_window_from_request(self.request)
        start_dt = window["start_dt"]
        end_dt = window["end_dt"]
        qs = SalesRecord.objects.filter(sold_at__gte=start_dt, sold_at__lte=end_dt)

        totals = qs.aggregate(
            total_earning=Coalesce(
                Sum(_sales_line_total_expr()),
                Value(Decimal("0.00"), output_field=DecimalField(max_digits=14, decimal_places=2)),
            ),
            total_items=Coalesce(Sum("quantity"), Value(0)),
            total_entries=Count("id"),
        )

        category_map = {}
        category_rows = (
            qs.values("category")
            .annotate(
                total_qty=Coalesce(Sum("quantity"), Value(0)),
                total_amount=Coalesce(
                    Sum(_sales_line_total_expr()),
                    Value(Decimal("0.00"), output_field=DecimalField(max_digits=14, decimal_places=2)),
                ),
            )
            .order_by("category")
        )
        for row in category_rows:
            key = (row["category"] or "").strip().lower()
            category_map[key] = row

        categories = []
        for cat in Category.objects.select_related("section").order_by("name"):
            key = cat.name.strip().lower()
            row = category_map.get(key)
            categories.append(
                {
                    "id": cat.id,
                    "name": cat.name,
                    "section": cat.section.name,
                    "total_qty": row["total_qty"] if row else 0,
                    "total_amount": row["total_amount"] if row else Decimal("0.00"),
                }
            )

        context.update(
            {
                "window_start": start_dt,
                "window_end": end_dt,
                "total_earning": totals["total_earning"],
                "total_items": totals["total_items"],
                "total_entries": totals["total_entries"],
                "categories": categories,
                "range_key": window["range_key"],
                "date_input": window["date_input"],
                "start_date_input": window["start_date_input"],
                "end_date_input": window["end_date_input"],
                "query_string": window["query_string"],
            }
        )
        return context


@method_decorator(staff_member_required, name="dispatch")
class AdminCategorySalesDetailView(TemplateView):
    template_name = "orders/admin_category_sales_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category = get_object_or_404(Category, id=kwargs["category_id"])
        window = _sales_window_from_request(self.request)
        start_dt = window["start_dt"]
        end_dt = window["end_dt"]
        qs = SalesRecord.objects.filter(
            sold_at__gte=start_dt,
            sold_at__lte=end_dt,
            category__iexact=category.name,
        )
        product_rows = (
            qs.values("product_name", "price")
            .annotate(
                total_qty=Coalesce(Sum("quantity"), Value(0)),
                total_amount=Coalesce(
                    Sum(_sales_line_total_expr()),
                    Value(Decimal("0.00"), output_field=DecimalField(max_digits=14, decimal_places=2)),
                ),
            )
            .order_by("product_name", "price")
        )
        totals = qs.aggregate(
            total_qty=Coalesce(Sum("quantity"), Value(0)),
            total_amount=Coalesce(
                Sum(_sales_line_total_expr()),
                Value(Decimal("0.00"), output_field=DecimalField(max_digits=14, decimal_places=2)),
            ),
        )
        context.update(
            {
                "category": category,
                "window_start": start_dt,
                "window_end": end_dt,
                "product_rows": product_rows,
                "total_qty": totals["total_qty"],
                "total_amount": totals["total_amount"],
                "range_key": window["range_key"],
                "date_input": window["date_input"],
                "start_date_input": window["start_date_input"],
                "end_date_input": window["end_date_input"],
                "query_string": window["query_string"],
            }
        )
        return context


class AdminSalesAnalyticsExportAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        window = _sales_window_from_request(request)
        start_dt = window["start_dt"]
        end_dt = window["end_dt"]
        qs = SalesRecord.objects.filter(sold_at__gte=start_dt, sold_at__lte=end_dt)
        rows = list(
            qs.values("category", "product_name", "price")
            .annotate(
                total_qty=Coalesce(Sum("quantity"), Value(0)),
                total_amount=Coalesce(
                    Sum(_sales_line_total_expr()),
                    Value(Decimal("0.00"), output_field=DecimalField(max_digits=14, decimal_places=2)),
                ),
            )
            .order_by("category", "product_name", "price")
        )

        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = (
            f'attachment; filename="sales_summary_{window["range_key"]}_{start_dt.date()}_{end_dt.date()}.csv"'
        )
        writer = csv.writer(resp)
        writer.writerow(["report_generated_at", timezone.localtime().strftime("%Y-%m-%d %H:%M:%S")])
        writer.writerow(["window_start", start_dt.strftime("%Y-%m-%d %H:%M:%S")])
        writer.writerow(["window_end", end_dt.strftime("%Y-%m-%d %H:%M:%S")])
        writer.writerow([])

        grand_qty = 0
        grand_total = Decimal("0.00")
        current_category = None
        category_qty = 0
        category_total = Decimal("0.00")

        for row in rows:
            row_category = (row["category"] or "").strip() or "Uncategorized"
            row_qty = int(row["total_qty"] or 0)
            row_amount = Decimal(row["total_amount"] or "0.00")

            if current_category != row_category:
                if current_category is not None:
                    writer.writerow(["TOTAL", category_qty, "", f"{category_total:.2f}"])
                    writer.writerow([])
                current_category = row_category
                category_qty = 0
                category_total = Decimal("0.00")
                writer.writerow(["category", current_category])
                writer.writerow(["product_name", "quantity", "price", "line_total"])

            category_qty += row_qty
            category_total += row_amount
            grand_qty += row_qty
            grand_total += row_amount
            writer.writerow([row["product_name"], row_qty, f"{Decimal(row['price']):.2f}", f"{row_amount:.2f}"])

        if current_category is not None:
            writer.writerow(["TOTAL", category_qty, "", f"{category_total:.2f}"])
            writer.writerow([])
        else:
            writer.writerow(["category", "No sales records in selected range"])
            writer.writerow([])

        writer.writerow(["GRAND_TOTAL", grand_qty, "", f"{grand_total:.2f}"])
        return resp


class AdminCategorySalesExportAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, category_id):
        category = get_object_or_404(Category, id=category_id)
        window = _sales_window_from_request(request)
        start_dt = window["start_dt"]
        end_dt = window["end_dt"]
        qs = SalesRecord.objects.filter(
            sold_at__gte=start_dt,
            sold_at__lte=end_dt,
            category__iexact=category.name,
        )
        rows = (
            qs.values("product_name", "price")
            .annotate(
                total_qty=Coalesce(Sum("quantity"), Value(0)),
                total_amount=Coalesce(
                    Sum(_sales_line_total_expr()),
                    Value(Decimal("0.00"), output_field=DecimalField(max_digits=14, decimal_places=2)),
                ),
            )
            .order_by("product_name", "price")
        )

        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = (
            f'attachment; filename="sales_{category.name.lower()}_{window["range_key"]}_{start_dt.date()}_{end_dt.date()}.csv"'
        )
        writer = csv.writer(resp)
        writer.writerow(["report_generated_at", timezone.localtime().strftime("%Y-%m-%d %H:%M:%S")])
        writer.writerow(["window_start", start_dt.strftime("%Y-%m-%d %H:%M:%S")])
        writer.writerow(["window_end", end_dt.strftime("%Y-%m-%d %H:%M:%S")])
        writer.writerow(["category", category.name])
        writer.writerow([])
        writer.writerow(["product_name", "quantity", "price", "line_total"])
        total_qty = 0
        total_amount = Decimal("0.00")
        for row in rows:
            qty = int(row["total_qty"] or 0)
            amount = Decimal(row["total_amount"] or "0.00")
            price = Decimal(row["price"] or "0.00")
            total_qty += qty
            total_amount += amount
            writer.writerow([row["product_name"], qty, f"{price:.2f}", f"{amount:.2f}"])
        writer.writerow(["TOTAL", total_qty, "", f"{total_amount:.2f}"])
        return resp


@method_decorator(staff_member_required, name="dispatch")
class AdminSalesVisualizationSelectorView(TemplateView):
    template_name = "orders/admin_sales_visualization_selector.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sections = []
        for section in Section.objects.order_by("name"):
            slug = "bakery" if section.name.lower() in {"bakery", "backery"} else section.name.lower()
            sections.append({"name": section.name, "slug": slug})
        context["sections"] = sections
        return context


@method_decorator(staff_member_required, name="dispatch")
class AdminSalesVisualizationDetailView(TemplateView):
    template_name = "orders/admin_sales_visualization_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        section, section_slug = _resolve_section_by_slug(kwargs.get("section_slug"))

        base_day = _parse_date((self.request.GET.get("date") or "").strip()) or timezone.localdate()
        period, (start_dt, end_dt) = _period_window(self.request.GET.get("period"), base_day)
        qs, category_rows = _section_category_sales_rows(section, start_dt, end_dt)
        total_amount = sum((Decimal(r["total_amount"] or "0.00") for r in category_rows), Decimal("0.00"))
        total_qty = sum((int(r["total_qty"] or 0) for r in category_rows), 0)

        chart_labels = []
        chart_values = []
        category_cards = []
        for row in category_rows:
            amount = Decimal(row["total_amount"] or "0.00")
            pct = (amount * Decimal("100.00") / total_amount) if total_amount > 0 else Decimal("0.00")
            chart_labels.append(row["category"])
            chart_values.append(float(amount))
            category_cards.append(
                {
                    "category": row["category"],
                    "qty": int(row["total_qty"] or 0),
                    "amount": amount,
                    "pct": pct.quantize(Decimal("0.01")),
                }
            )

        top_product_row = (
            qs.values("product_name", "category")
            .annotate(
                total_qty=Coalesce(Sum("quantity"), Value(0)),
                total_amount=Coalesce(
                    Sum(_sales_line_total_expr()),
                    Value(Decimal("0.00"), output_field=DecimalField(max_digits=14, decimal_places=2)),
                ),
            )
            .order_by("-total_amount", "-total_qty", "product_name")
            .first()
        )
        if top_product_row:
            top_headline = (
                f"Top product: {top_product_row['product_name']} from {top_product_row['category']} "
                f"with sales Rs {Decimal(top_product_row['total_amount']):.2f}"
            )
        else:
            top_headline = "No sales found for selected range."

        context.update(
            {
                "section": section,
                "section_slug": section_slug,
                "period": period,
                "date_input": base_day.isoformat(),
                "window_start": start_dt,
                "window_end": end_dt,
                "total_amount": total_amount,
                "total_qty": total_qty,
                "category_cards": category_cards,
                "top_headline": top_headline,
                "chart_labels_json": json.dumps(chart_labels),
                "chart_values_json": json.dumps(chart_values),
                "chart_image_url": (
                    f"/admin-dashboard/analytics/visualization/{section_slug}/chart.png"
                    f"?period={period}&date={base_day.isoformat()}"
                ),
            }
        )
        return context


@method_decorator(staff_member_required, name="dispatch")
@method_decorator(cache_page(120), name="dispatch")
class AdminSalesVisualizationChartImageView(View):
    def get(self, request, section_slug):
        section, _ = _resolve_section_by_slug(section_slug)
        base_day = _parse_date((request.GET.get("date") or "").strip()) or timezone.localdate()
        _, (start_dt, end_dt) = _period_window(request.GET.get("period"), base_day)
        _, category_rows = _section_category_sales_rows(section, start_dt, end_dt)

        labels = [row["category"] for row in category_rows]
        values = [float(Decimal(row["total_amount"] or "0.00")) for row in category_rows]

        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import seaborn as sns

        sns.set_theme(style="whitegrid")
        fig, ax = plt.subplots(figsize=(10, 6), dpi=120)
        fig.patch.set_facecolor("#f8fafc")
        ax.set_facecolor("#ffffff")

        if values and sum(values) > 0:
            palette = sns.color_palette("tab20", n_colors=len(values))
            wedges, texts, autotexts = ax.pie(
                values,
                labels=labels,
                autopct="%1.1f%%",
                startangle=140,
                colors=palette,
                wedgeprops={"linewidth": 1, "edgecolor": "white"},
                textprops={"fontsize": 10},
            )
            for t in autotexts:
                t.set_color("black")
                t.set_fontweight("bold")
            ax.axis("equal")
        else:
            ax.text(
                0.5,
                0.5,
                "No sales data for selected range",
                ha="center",
                va="center",
                fontsize=14,
                color="#6b7280",
            )
            ax.axis("off")

        ax.set_title(
            f"{section.name} Category Share ({start_dt.strftime('%Y-%m-%d')} to {end_dt.strftime('%Y-%m-%d')})",
            fontsize=14,
            fontweight="bold",
            color="#5a2e16",
            pad=14,
        )

        buf = BytesIO()
        fig.tight_layout()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return HttpResponse(buf.getvalue(), content_type="image/png")


class AdminDashboardAnalyticsAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        range_key = request.GET.get("range", "today")
        return Response(AdminAnalyticsService.dashboard_payload(range_key))


class AdminDashboardOrdersAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        limit = min(max(int(request.GET.get("limit", 20)), 1), 100)
        return Response({"orders": AdminAnalyticsService.recent_orders_payload(limit=limit)})


class AdminOrderAlertAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        last_id = int(request.GET.get("last_id", 0) or 0)
        latest_id = AdminRepository.latest_order_id()
        has_new = latest_id > last_id
        return Response({"has_new": has_new, "latest_id": latest_id})


class AdminProductSearchAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        q = (request.GET.get("q") or "").strip()
        if not q:
            return Response({"items": []})
        products = AdminRepository.product_search(q)
        return Response(
            {
                "items": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "category": p.category.name,
                        "section": p.category.section.name,
                        "price": str(p.price),
                        "stock_qty": p.stock_qty,
                        "is_available": p.is_available,
                        "image": request.build_absolute_uri(p.image.url) if p.image else None,
                    }
                    for p in products
                ]
            }
        )


def _excel_table_response(filename, headers, rows):
    html = [
        "<html><head><meta charset='utf-8'></head><body><table border='1'>",
        "<tr>",
    ]
    for h in headers:
        html.append(f"<th>{h}</th>")
    html.append("</tr>")
    for row in rows:
        html.append("<tr>")
        for cell in row:
            text = "" if cell is None else str(cell)
            safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            html.append(f"<td>{safe}</td>")
        html.append("</tr>")
    html.append("</table></body></html>")
    payload = "".join(html)

    resp = HttpResponse(payload, content_type="application/vnd.ms-excel; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="{filename}.xls"'
    return resp


def _pdf_escape(text):
    return str(text or "").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_pdf_document(stream, page_width=595, page_height=842):
    objects = []
    objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    objects.append(b"2 0 obj\n<< /Type /Pages /Count 1 /Kids [3 0 R] >>\nendobj\n")
    objects.append(
        (
            "3 0 obj\n"
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {int(page_width)} {int(page_height)}] "
            "/Resources << /Font << /F1 4 0 R /F2 6 0 R >> >> /Contents 5 0 R >>\n"
            "endobj\n"
        ).encode("ascii")
    )
    objects.append(b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")
    objects.append(
        f"5 0 obj\n<< /Length {len(stream)} >>\nstream\n".encode("ascii")
        + stream
        + b"\nendstream\nendobj\n"
    )
    objects.append(b"6 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>\nendobj\n")

    pdf = BytesIO()
    pdf.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for obj in objects:
        offsets.append(pdf.tell())
        pdf.write(obj)

    xref_pos = pdf.tell()
    pdf.write(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.write(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        pdf.write(f"{off:010d} 00000 n \n".encode("ascii"))
    pdf.write(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n".encode("ascii"))
    pdf.write(f"startxref\n{xref_pos}\n%%EOF".encode("ascii"))
    return pdf.getvalue()


def _build_simple_pdf(
    lines,
    *,
    font_size=12,
    line_step=16,
    top=800,
    left=50,
):
    commands = ["BT", f"/F1 {font_size} Tf"]
    y = top
    for line in lines:
        commands.append(f"1 0 0 1 {left} {y} Tm ({_pdf_escape(line)}) Tj")
        y -= line_step
        if y < 40:
            break
    commands.append("ET")
    stream = "\n".join(commands).encode("latin-1", errors="replace")
    return _build_pdf_document(stream)


def _money_str(value):
    return f"{Decimal(str(value or 0)):.2f}"


def _wrap_pdf_text(text, width=84):
    raw = str(text or "").strip()
    if not raw:
        return [""]

    words = raw.split()
    lines = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= width:
            current = candidate
            continue

        if current:
            lines.append(current)
            current = ""

        if len(word) <= width:
            current = word
            continue

        token = word
        while len(token) > width:
            lines.append(token[: width - 1] + "-")
            token = token[width - 1 :]
        current = token

    if current:
        lines.append(current)
    return lines


def _build_user_receipt_pdf(bill, owner_phone):
    page_width = 595
    left_margin = 22
    right_margin = 22
    top_margin = 16
    bottom_margin = 16
    content_width = page_width - left_margin - right_margin

    owner_phone_value = owner_phone or "-"
    address_lines = _wrap_pdf_text(f"Address: {bill.shipping_address}", width=90)

    item_rows = []
    for item in bill.items.all():
        name_lines = _wrap_pdf_text(item.product_name, width=40)
        row_height = max(1, len(name_lines)) * 11 + 6
        item_rows.append(
            {
                "name_lines": name_lines,
                "qty": int(item.quantity),
                "unit_price": _money_str(item.unit_price),
                "line_total": _money_str(item.unit_price * Decimal(item.quantity)),
                "height": row_height,
            }
        )

    meta_lines = 2 + len(address_lines)
    header_height = 30
    meta_height = meta_lines * 11 + 4
    table_header_height = 18
    rows_height = sum(row["height"] for row in item_rows)

    rendered_height = (
        header_height
        + 10
        + meta_height
        + table_header_height
        + rows_height
        + 2
        + 14
        + 16
    )
    page_height = int(max(190, top_margin + bottom_margin + rendered_height + 6))

    commands = []

    def set_stroke_gray(gray):
        commands.append(f"{gray:.2f} {gray:.2f} {gray:.2f} RG")

    def set_fill_gray(gray):
        commands.append(f"{gray:.2f} {gray:.2f} {gray:.2f} rg")

    def text(x, y_pos, txt, size=10, bold=False, gray=0.0):
        font = "F2" if bold else "F1"
        set_fill_gray(gray)
        commands.append("BT")
        commands.append(f"/{font} {size} Tf")
        commands.append(f"1 0 0 1 {x:.2f} {y_pos:.2f} Tm ({_pdf_escape(txt)}) Tj")
        commands.append("ET")

    y = page_height - top_margin

    set_stroke_gray(0.78)
    commands.append("1 w")
    commands.append(
        f"{left_margin:.2f} {bottom_margin:.2f} {content_width:.2f} {page_height - top_margin - bottom_margin:.2f} re S"
    )

    # Header strip
    set_stroke_gray(0.85)
    set_fill_gray(0.93)
    commands.append(
        f"{left_margin:.2f} {y - header_height:.2f} {content_width:.2f} {header_height:.2f} re B"
    )
    text(left_margin + 12, y - 20, "THATHWAMASI", size=13, bold=True)
    text(left_margin + 160, y - 20, "CUSTOMER RECEIPT", size=10, bold=True, gray=0.25)
    text(left_margin + content_width - 170, y - 20, f"Bill #{bill.bill_number}", size=9, gray=0.2)
    y -= header_height + 10

    # Meta block
    x = left_margin + 12
    text(x, y, f"Customer: {bill.customer_name}", size=9)
    text(left_margin + content_width - 205, y, f"Date: {bill.created_at.strftime('%Y-%m-%d %H:%M')}", size=9)
    y -= 11

    text(x, y, f"Customer Phone: {bill.phone}", size=9)
    text(left_margin + content_width - 205, y, f"Owner Phone: {owner_phone_value}", size=9)
    y -= 11

    for line in address_lines:
        text(x, y, line, size=9, gray=0.12)
        y -= 11

    y -= 4

    # Item table header
    set_stroke_gray(0.80)
    set_fill_gray(0.95)
    commands.append(f"{x - 2:.2f} {y - 14:.2f} {content_width - 20:.2f} 18 re B")
    item_x = x
    qty_x = x + 300
    unit_x = x + 360
    total_x = x + 445
    text(item_x, y - 1, "Product", size=9, bold=True)
    text(qty_x, y - 1, "Qty", size=9, bold=True)
    text(unit_x, y - 1, "Price", size=9, bold=True)
    text(total_x, y - 1, "Total", size=9, bold=True)
    y -= table_header_height

    # Item rows
    for row in item_rows:
        row_height = row["height"]
        set_stroke_gray(0.90)
        commands.append(f"{x - 2:.2f} {y - row_height + 4:.2f} {content_width - 20:.2f} 0 re S")

        for idx, name_line in enumerate(row["name_lines"]):
            text(item_x, y - (idx * 11), name_line, size=9, bold=(idx == 0 and len(row["name_lines"]) > 1))

        text(qty_x, y, str(row["qty"]), size=9)
        text(unit_x, y, f"Rs {row['unit_price']}", size=9)
        text(total_x, y, f"Rs {row['line_total']}", size=9, bold=True)
        y -= row_height

    y -= 2
    set_stroke_gray(0.75)
    commands.append(f"{x - 2:.2f} {y:.2f} {content_width - 20:.2f} 0 re S")
    y -= 14

    text(x + 350, y, "Grand Total", size=10, bold=True)
    text(x + 448, y, f"Rs {_money_str(bill.total_amount)}", size=11, bold=True)
    y -= 16

    text(x, y, "This is a computer-generated receipt.", size=8, gray=0.35)

    stream = "\n".join(commands).encode("latin-1", errors="replace")
    return _build_pdf_document(stream, page_width=page_width, page_height=page_height)

class UserBillPDFDownloadView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, bill_id):
        phone = (request.GET.get("phone") or "").strip()
        if not phone:
            return Response(
                {"detail": "phone query param is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        bill = get_object_or_404(
            Bill.objects.filter(recipient_type="USER").prefetch_related("items"),
            id=bill_id,
        )
        if str(bill.phone or "").strip() != phone:
            return Response(
                {"detail": "Bill not found for this phone"},
                status=status.HTTP_404_NOT_FOUND,
            )

        owner_phone = (
            getattr(settings, "ADMIN_PHONE", "")
            or getattr(settings, "TWILIO_PHONE_NUMBER", "")
            or ""
        ).strip()

        pdf_data = _build_user_receipt_pdf(bill, owner_phone)
        filename = f"receipt_{bill.bill_number or bill.id}.pdf"
        response = HttpResponse(pdf_data, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class AdminBillPDFDownloadView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, bill_id):
        bill = get_object_or_404(
            Bill.objects.filter(recipient_type="ADMIN").prefetch_related("items"),
            id=bill_id,
        )

        lines = [
            "Thathwamasi",
            "Billing Invoice",
            "",
            f"Bill Number: {bill.bill_number}",
            f"Date: {bill.created_at.strftime('%Y-%m-%d %H:%M')}",
            f"Customer: {bill.customer_name}",
            f"Phone: {bill.phone}",
            f"Address: {bill.shipping_address}",
            "",
            "Products:",
        ]
        for item in bill.items.all():
            lines.append(
                f"- {item.product_name} | Rs {item.unit_price} x {item.quantity} = Rs {item.unit_price * Decimal(item.quantity)}"
            )
        lines.append("")
        lines.append(f"Total Price: Rs {bill.total_amount}")

        pdf_data = _build_simple_pdf(lines)
        filename = f"bill_{bill.bill_number or bill.id}.pdf"
        response = HttpResponse(pdf_data, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class AdminSalesExportAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        range_key = request.GET.get("range", "today")
        fmt = (request.GET.get("format", "csv") or "csv").lower()
        qs = AdminRepository.sales_qs(range_key).select_related("order").order_by("-sold_at")
        headers = [
            "sold_at",
            "order_id",
            "category",
            "product_name",
            "price",
            "quantity",
        ]
        rows = [
            [
                item.sold_at.isoformat(),
                item.order_id,
                item.category,
                item.product_name,
                item.price,
                item.quantity,
            ]
            for item in qs
        ]

        filename = f"sales_{range_key}"
        if fmt in {"excel", "xls"}:
            return _excel_table_response(filename, headers, rows)

        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = f'attachment; filename="{filename}.csv"'
        writer = csv.writer(resp)
        writer.writerow(headers)
        writer.writerows(rows)
        return resp


class AdminOrdersExportAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        range_key = request.GET.get("range", "today")
        fmt = (request.GET.get("format", "csv") or "csv").lower()
        start = AdminRepository.range_start(range_key)
        qs = (
            Order.objects.filter(created_at__gte=start)
            .prefetch_related("items__product")
            .order_by("-created_at")
        )

        headers = [
            "order_id",
            "created_at",
            "customer_name",
            "phone",
            "shipping_address",
            "status",
            "product_name",
            "price",
            "quantity",
        ]
        rows = []
        for order in qs:
            for item in order.items.all():
                rows.append(
                    [
                        order.id,
                        order.created_at.isoformat(),
                        order.customer_name,
                        order.phone,
                        order.shipping_address,
                        order.status,
                        item.product.name,
                        item.price,
                        item.quantity,
                    ]
                )

        filename = f"orders_{range_key}"
        if fmt in {"excel", "xls"}:
            return _excel_table_response(filename, headers, rows)

        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = f'attachment; filename="{filename}.csv"'
        writer = csv.writer(resp)
        writer.writerow(headers)
        writer.writerows(rows)
        return resp


# it call to the notification
def place_order_view(request):
    cart = request.user.cart

    create_order_from_cart(request.user, cart)

    return Response({"message": "Order placed successfully"})
