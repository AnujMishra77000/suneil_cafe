from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.http import Http404
from django.db.models import Q
from django.db import transaction
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.views.generic import TemplateView
from django.utils.decorators import method_decorator
from django.contrib.admin.views.decorators import staff_member_required
from django.core.files.storage import default_storage
from django.utils.text import get_valid_filename
from django.core.cache import cache
from django.conf import settings
from .models import Advertisement, Product, Section, Category, ProductViewLog
from .cache_utils import catalog_cache_key, invalidate_catalog_cache
from .services import ProductService
from .forms import AdminAdvertisementForm, AdminProductCreateForm
from .tasks import process_product_image_upload_task
from .serializers import (
    ProductSerializer,
    ProductCardSerializer,
    SectionSerializer,
    CategorySerializer,
    ProductViewLogSerializer,
    RelatedProductSerializer,
)


class StorefrontHomeView(TemplateView):
    template_name = "products/storefront_home.html"
    OFFER_SLOTS = (1, 2, 3)

    @classmethod
    def _active_ads_by_slot(cls):
        cache_key = catalog_cache_key("home_ads")
        cached_ids = cache.get(cache_key)
        if cached_ids:
            ordered_ids = [item["id"] for item in cached_ids]
            ads_map = Advertisement.objects.in_bulk(ordered_ids)
            if len(ads_map) == len(ordered_ids):
                return [ads_map[ad_id] for ad_id in ordered_ids]

        slot_ads = {}
        field_names = (
            "id",
            "title",
            "subtitle",
            "image",
            "cta_label",
            "cta_url",
            "display_order",
        )

        queryset = Advertisement.objects.filter(
            is_active=True,
            display_order__in=cls.OFFER_SLOTS,
        ).only(*field_names).order_by("display_order", "-created_at")

        for ad in queryset:
            slot_ads.setdefault(ad.display_order, ad)
            if len(slot_ads) == len(cls.OFFER_SLOTS):
                break

        if len(slot_ads) < len(cls.OFFER_SLOTS):
            selected_ids = [ad.id for ad in slot_ads.values()]
            fallback_qs = Advertisement.objects.filter(is_active=True).exclude(
                id__in=selected_ids
            ).only(*field_names).order_by("-created_at")
            empty_slots = [slot for slot in cls.OFFER_SLOTS if slot not in slot_ads]
            for slot, ad in zip(empty_slots, fallback_qs):
                slot_ads[slot] = ad

        payload = [{"id": ad.id} for ad in [slot_ads[slot] for slot in cls.OFFER_SLOTS if slot in slot_ads]]
        cache.set(cache_key, payload, 180)
        return [slot_ads[slot] for slot in cls.OFFER_SLOTS if slot in slot_ads]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["ads"] = self._active_ads_by_slot()
        return context


def _normalize_public_section_name(section_name):
    section = (section_name or "").strip().lower()
    if section == "backery":
        section = "bakery"
    if section not in {"bakery", "snacks"}:
        raise Http404("Section not found")
    return section


class StorefrontSectionView(TemplateView):
    template_name = "products/storefront_section.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        section = _normalize_public_section_name(self.kwargs["section_name"])
        context["section_name"] = section
        context["section_title"] = section.title()
        return context


class StorefrontCategoryView(TemplateView):
    template_name = "products/storefront_category.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        section = _normalize_public_section_name(self.kwargs["section_name"])
        category = get_object_or_404(
            Category.objects.select_related("section").only("id", "name", "section__name"),
            id=self.kwargs["category_id"],
        )
        category_section = (category.section.name or "").strip().lower()
        if section == "bakery":
            allowed_sections = {"bakery", "backery"}
        else:
            allowed_sections = {"snacks", "snack"}
        if category_section not in allowed_sections:
            raise Http404("Category not found for this section")

        context["section_name"] = section
        context["section_title"] = section.title()
        context["category_id"] = category.id
        context["category_name"] = category.name
        return context


class BillingPageView(TemplateView):
    template_name = "products/billing.html"


class CustomerOrderDetailsPageView(TemplateView):
    template_name = "products/order_details.html"


class CheckoutPageView(TemplateView):
    template_name = "products/checkout.html"


class OrderSuccessPageView(TemplateView):
    template_name = "products/order_success.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["order_id"] = (self.request.GET.get("order_id") or "").strip()
        return context


class BuyProductPageView(TemplateView):
    template_name = "products/buy_product.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["product_id"] = self.kwargs["product_id"]
        return context


@method_decorator(staff_member_required, name="dispatch")
class LatencyDashboardView(TemplateView):
    template_name = "products/latency_dashboard.html"


@method_decorator(staff_member_required, name="dispatch")
class AdminProductSectionSelectView(TemplateView):
    template_name = "products/admin_product_section_select.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sections"] = Section.objects.order_by("name")
        return context


@method_decorator(staff_member_required, name="dispatch")
class AdminProductCreateView(TemplateView):
    template_name = "products/admin_product_add.html"

    def _resolve_section(self):
        return get_object_or_404(Section.objects.only("id", "name"), id=self.kwargs["section_id"])

    @staticmethod
    def _load_related_flag(request):
        return (request.GET.get("load_related") or request.POST.get("load_related") or "").strip() == "1"

    def _build_form(self, section, data=None, files=None, load_related=False):
        options = ProductService.admin_form_options(section.id, load_related=load_related)
        return AdminProductCreateForm(
            data,
            files,
            section=section,
            category_queryset=options["categories"],
            related_choices=options["related"],
            load_related=load_related,
        )

    @staticmethod
    def _save_temp_upload(uploaded_file):
        safe_name = get_valid_filename(uploaded_file.name or "upload.bin")
        temp_path = f"tmp/product_uploads/{safe_name}"
        return default_storage.save(temp_path, uploaded_file)

    def get(self, request, *args, **kwargs):
        section = self._resolve_section()
        load_related = self._load_related_flag(request)
        form = self._build_form(section, load_related=load_related)
        return self.render_to_response(
            {
                "section": section,
                "form": form,
                "created": request.GET.get("created") == "1",
                "product_name": request.GET.get("product_name", ""),
                "load_related": load_related,
            }
        )

    def post(self, request, *args, **kwargs):
        section = self._resolve_section()
        load_related = self._load_related_flag(request)
        form = self._build_form(section, request.POST, request.FILES, load_related=load_related)
        if form.is_valid():
            uploaded_image = form.cleaned_data.get("image")
            temp_path = None
            if uploaded_image is not None:
                temp_path = self._save_temp_upload(uploaded_image)

            product = form.save(commit=False)
            if temp_path:
                # Save product first; attach image asynchronously in background.
                product.image = ""
            product.save()
            form.save_m2m()

            if temp_path:
                transaction.on_commit(
                    lambda: process_product_image_upload_task.delay(product.id, temp_path)
                )

            fresh_form = self._build_form(section, load_related=load_related)
            return self.render_to_response(
                {
                    "section": section,
                    "form": fresh_form,
                    "created": True,
                    "product_name": product.name,
                    "load_related": load_related,
                }
            )

        return self.render_to_response(
            {
                "section": section,
                "form": form,
                "created": False,
                "product_name": "",
                "load_related": load_related,
            }
        )


@method_decorator(staff_member_required, name="dispatch")
class AdminStockTrackerView(TemplateView):
    template_name = "products/admin_stock_tracker.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sections"] = Section.objects.only("id", "name").order_by("name")
        return context


@method_decorator(staff_member_required, name="dispatch")
class AdminAdvertisingManageView(TemplateView):
    template_name = "products/admin_advertising_manage.html"
    OFFER_SLOTS = (1, 2, 3)

    def _latest_ads_by_slot(self):
        slot_ads = {}
        field_names = (
            "id",
            "title",
            "subtitle",
            "image",
            "cta_label",
            "cta_url",
            "display_order",
            "is_active",
        )

        queryset = Advertisement.objects.filter(
            display_order__in=self.OFFER_SLOTS
        ).only(*field_names).order_by("display_order", "-created_at")

        for ad in queryset:
            slot_ads.setdefault(ad.display_order, ad)
            if len(slot_ads) == len(self.OFFER_SLOTS):
                break

        if len(slot_ads) < len(self.OFFER_SLOTS):
            selected_ids = [ad.id for ad in slot_ads.values()]
            fallback_qs = Advertisement.objects.exclude(id__in=selected_ids).only(
                *field_names
            ).order_by("-created_at")
            empty_slots = [slot for slot in self.OFFER_SLOTS if slot not in slot_ads]
            for slot, ad in zip(empty_slots, fallback_qs):
                slot_ads[slot] = ad

        return slot_ads

    def _build_slot_forms(self, post_data=None, files_data=None):
        slot_ads = self._latest_ads_by_slot()
        slot_forms = []
        for slot in self.OFFER_SLOTS:
            prefix = f"slot_{slot}"
            instance = slot_ads.get(slot)
            form = AdminAdvertisementForm(
                post_data,
                files_data,
                instance=instance,
                prefix=prefix,
            )
            form.initial["display_order"] = slot
            form.fields["display_order"].initial = slot
            slot_forms.append({"slot": slot, "form": form, "ad": instance})
        return slot_forms

    @staticmethod
    def _slot_has_input(slot, post_data, files_data):
        prefix = f"slot_{slot}"
        for name in ("title", "subtitle", "cta_label", "cta_url"):
            if (post_data.get(f"{prefix}-{name}") or "").strip():
                return True
        return bool(files_data.get(f"{prefix}-image"))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["slot_forms"] = kwargs.get("slot_forms") or self._build_slot_forms()
        context["saved"] = kwargs.get("saved", False)
        return context

    def post(self, request, *args, **kwargs):
        action = (request.POST.get("action") or "save_slots").strip().lower()
        if action != "save_slots":
            return self.render_to_response(self.get_context_data())

        slot_forms = self._build_slot_forms(request.POST, request.FILES)
        rendered_slot_forms = []
        has_errors = False
        saved_any = False

        for slot_entry in slot_forms:
            slot = slot_entry["slot"]
            form = slot_entry["form"]
            instance = slot_entry["ad"]

            if instance is None and not self._slot_has_input(slot, request.POST, request.FILES):
                blank_form = AdminAdvertisementForm(prefix=f"slot_{slot}")
                blank_form.initial["display_order"] = slot
                blank_form.fields["display_order"].initial = slot
                rendered_slot_forms.append({"slot": slot, "form": blank_form, "ad": None})
                continue

            if form.is_valid():
                ad = form.save(commit=False)
                ad.display_order = slot
                ad.save()
                saved_any = True
                rendered_slot_forms.append({"slot": slot, "form": form, "ad": ad})
            else:
                has_errors = True
                rendered_slot_forms.append(slot_entry)

        if has_errors:
            return self.render_to_response(self.get_context_data(slot_forms=rendered_slot_forms))

        return self.render_to_response(
            self.get_context_data(
                slot_forms=self._build_slot_forms(),
                saved=saved_any,
            )
        )


class AdminStockListAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        section_key = (request.GET.get("section") or "").strip().lower()
        products = Product.objects.select_related("category", "category__section").only(
            "id",
            "name",
            "stock_qty",
            "is_available",
            "price",
            "category__id",
            "category__name",
            "category__section__name",
        )

        if section_key:
            if section_key in {"bakery", "backery"}:
                products = products.filter(category__section__name__in=["Bakery", "Backery"])
            elif section_key in {"snacks", "snack"}:
                products = products.filter(category__section__name__in=["Snacks", "Snack"])
            elif section_key.isdigit():
                products = products.filter(category__section_id=int(section_key))
            else:
                products = products.filter(category__section__name__icontains=section_key)

        products = products.order_by("category__section__name", "category__name", "name")
        payload = [
            {
                "id": product.id,
                "name": product.name,
                "category": product.category.name,
                "section": product.category.section.name,
                "price": str(product.price),
                "stock_qty": product.stock_qty,
                "is_available": product.is_available,
            }
            for product in products
        ]
        return Response({"items": payload})


class AdminStockUpdateAPIView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        try:
            product_id = int(request.data.get("product_id"))
            stock_qty = int(request.data.get("stock_qty"))
        except (TypeError, ValueError):
            return Response({"detail": "product_id and stock_qty must be valid integers"}, status=400)

        if stock_qty < 0:
            return Response({"detail": "stock_qty cannot be negative"}, status=400)

        product = get_object_or_404(Product, pk=product_id)
        product.stock_qty = stock_qty
        product.is_available = stock_qty > 0
        product.save(update_fields=["stock_qty", "is_available"])
        invalidate_catalog_cache()

        return Response(
            {
                "id": product.id,
                "stock_qty": product.stock_qty,
                "is_available": product.is_available,
            },
            status=status.HTTP_200_OK,
        )


# 🧁 List all Sections (Bakery, Snacks)
class SectionListAPIView(generics.ListAPIView):
    serializer_class = SectionSerializer
    pagination_class = None

    def list(self, request, *args, **kwargs):
        cache_key = catalog_cache_key("sections")
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        queryset = Section.objects.only("id", "name").order_by("name")
        payload = self.get_serializer(queryset, many=True).data
        cache.set(cache_key, payload, 180)
        return Response(payload)


# 🍞 Categories by Section
class CategoryBySectionAPIView(generics.ListAPIView):
    serializer_class = CategorySerializer
    pagination_class = None

    def get_queryset(self):
        section_id = self.kwargs["section_id"]
        return Category.objects.filter(section_id=section_id).only("id", "name", "section_id").order_by("name")

    def list(self, request, *args, **kwargs):
        section_id = self.kwargs["section_id"]
        cache_key = catalog_cache_key("section_categories", section_id)
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        payload = self.get_serializer(self.get_queryset(), many=True).data
        cache.set(cache_key, payload, 180)
        return Response(payload)


class CategoryCardAPIView(APIView):
    """
    Returns lightweight category cards by section name.
    Uses one service path so card visuals stay consistent.
    """

    def get(self, request):
        section = request.GET.get("section", "").strip()
        if not section:
            return Response({"detail": "section query param is required"}, status=400)
        return Response(ProductService.category_cards(section))


# 🍩 Products by Category
class ProductByCategoryAPIView(generics.ListAPIView):
    serializer_class = ProductCardSerializer
    pagination_class = None

    def get_queryset(self):
        category_id = self.kwargs["category_id"]
        if settings.USE_LAYERED_ARCHITECTURE:
            return ProductService.products_by_category(category_id)

        # `select_related` prevents per-item FK fetches for category + section.
        return (
            Product.objects.select_related("category", "category__section")
            .only(
                "id",
                "name",
                "description",
                "price",
                "stock_qty",
                "is_available",
                "image",
                "category__id",
                "category__name",
                "category__section__name",
            )
            .filter(category_id=category_id)
            .order_by("-created_at", "name")
        )

    def list(self, request, *args, **kwargs):
        category_id = self.kwargs["category_id"]
        cache_key = catalog_cache_key("category_products", category_id)
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        payload = self.get_serializer(self.get_queryset(), many=True, context={"request": request}).data
        cache.set(cache_key, payload, 180)
        return Response(payload)


class ProductBySectionAPIView(generics.ListAPIView):
    serializer_class = ProductCardSerializer
    pagination_class = None

    def get_queryset(self):
        section_id = self.kwargs["section_id"]
        if settings.USE_LAYERED_ARCHITECTURE:
            return ProductService.products_by_section(section_id)

        # `select_related` keeps section/category joins in a single SQL query.
        return (
            Product.objects.select_related("category", "category__section")
            .only(
                "id",
                "name",
                "description",
                "price",
                "stock_qty",
                "is_available",
                "image",
                "category__id",
                "category__name",
                "category__section__name",
            )
            .filter(category__section_id=section_id)
            .order_by("-created_at", "name")
        )

    def list(self, request, *args, **kwargs):
        section_id = self.kwargs["section_id"]
        cache_key = catalog_cache_key("section_products", section_id)
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        payload = self.get_serializer(self.get_queryset(), many=True, context={"request": request}).data
        cache.set(cache_key, payload, 180)
        return Response(payload)


# single product details
def _record_unavailable_view(product_id):
    """Aggregate unavailable product views in cache to avoid per-request DB writes."""
    cache_key = catalog_cache_key("unavailable_view", product_id)
    try:
        cache.incr(cache_key)
    except ValueError:
        cache.set(cache_key, 1, 24 * 60 * 60)


class ProductDetailAPIView(generics.RetrieveAPIView):
    queryset = Product.objects.select_related("category", "category__section").prefetch_related("related_products")
    serializer_class = ProductSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()

        if not instance.is_available:
            _record_unavailable_view(instance.id)

        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class ProductSearchAPIView(APIView):
    def get(self, request):
        query = (request.GET.get("q") or "").strip()
        if not query:
            return Response([])

        cache_key = catalog_cache_key("search", query.lower()[:64])
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        if settings.USE_LAYERED_ARCHITECTURE:
            products = ProductService.search(query)
        else:
            search_query = SearchQuery(query)
            products = (
                Product.objects.select_related("category", "category__section")
                .annotate(rank=SearchRank("search_vector", search_query))
                .filter(rank__gte=0.05)
                .order_by("-rank", "name")
            )

            if not products.exists():
                products = (
                    Product.objects.select_related("category", "category__section")
                    .filter(
                        Q(name__icontains=query)
                        | Q(description__icontains=query)
                        | Q(category__name__icontains=query)
                        | Q(category__section__name__icontains=query)
                    )
                    .distinct()
                    .order_by("name")
                )

        payload = ProductCardSerializer(products, many=True, context={"request": request}).data
        cache.set(cache_key, payload, 120 if len(payload) < 10 else 180)
        return Response(payload)

class ProductViewLogCreateAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ProductViewLogSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = serializer.validated_data["product"]
        _record_unavailable_view(product.id)
        return Response({"status": "accepted"}, status=status.HTTP_202_ACCEPTED)


class RelatedProductAPIView(generics.ListAPIView):
    serializer_class = RelatedProductSerializer
    pagination_class = None

    def get_queryset(self):
        product_id = self.kwargs["pk"]
        product = get_object_or_404(
            Product.objects.select_related("category").prefetch_related("related_products"),
            pk=product_id,
        )

        explicit_related = product.related_products.filter(is_available=True)
        if explicit_related.exists():
            return explicit_related.select_related("category", "category__section")

        return Product.objects.filter(
            category=product.category,
            is_available=True,
        ).exclude(pk=product.pk).select_related("category", "category__section")[:8]
