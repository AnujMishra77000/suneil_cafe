from decimal import Decimal, ROUND_HALF_UP

from .coupon_rules import extract_discount_percent, normalize_coupon_code


MONEY_STEP = Decimal("0.01")
DELIVERY_CHARGE_THRESHOLD = Decimal("100.00")
DELIVERY_CHARGE_AMOUNT = Decimal("10.00")


def _to_money(value):
    return Decimal(str(value or 0)).quantize(MONEY_STEP, rounding=ROUND_HALF_UP)


def _delivery_charge_for_subtotal(subtotal):
    subtotal_value = _to_money(subtotal)
    if subtotal_value <= Decimal("0.00"):
        return Decimal("0.00")
    if subtotal_value < DELIVERY_CHARGE_THRESHOLD:
        return DELIVERY_CHARGE_AMOUNT
    return Decimal("0.00")


def _discount_breakdown(subtotal, coupon_code, discount_percent):
    subtotal_value = _to_money(subtotal)
    delivery_charge = _delivery_charge_for_subtotal(subtotal_value)
    percent = int(discount_percent or 0)
    if not coupon_code or percent <= 0:
        total = (subtotal_value + delivery_charge).quantize(MONEY_STEP, rounding=ROUND_HALF_UP)
        return {
            "subtotal": subtotal_value,
            "coupon_code": "",
            "discount_percent": 0,
            "discount_amount": Decimal("0.00"),
            "delivery_charge": delivery_charge,
            "total": total,
        }

    discount_amount = (subtotal_value * Decimal(percent) / Decimal("100")).quantize(
        MONEY_STEP,
        rounding=ROUND_HALF_UP,
    )
    discounted_total = max(subtotal_value - discount_amount, Decimal("0.00")).quantize(
        MONEY_STEP,
        rounding=ROUND_HALF_UP,
    )
    total = (discounted_total + delivery_charge).quantize(
        MONEY_STEP,
        rounding=ROUND_HALF_UP,
    )
    return {
        "subtotal": subtotal_value,
        "coupon_code": coupon_code,
        "discount_percent": percent,
        "discount_amount": discount_amount,
        "delivery_charge": delivery_charge,
        "total": total,
    }


def get_active_coupon(code):
    from .models import CouponCode

    normalized = normalize_coupon_code(code)
    if not normalized:
        raise ValueError("Enter a coupon code.")

    coupon = CouponCode.objects.filter(code=normalized, is_active=True).first()
    if not coupon:
        raise ValueError("Coupon code is invalid or inactive.")
    return coupon


def validate_coupon_payload(code):
    coupon = get_active_coupon(code)
    return {
        "coupon_code": coupon.code,
        "discount_percent": coupon.discount_percent,
    }


def calculate_coupon_breakdown(subtotal, coupon_code=""):
    normalized = normalize_coupon_code(coupon_code)
    if not normalized:
        return _discount_breakdown(subtotal, "", 0)
    coupon = get_active_coupon(normalized)
    return _discount_breakdown(subtotal, coupon.code, coupon.discount_percent)


def apply_stored_coupon_breakdown(subtotal, coupon_code="", discount_percent=0):
    normalized = normalize_coupon_code(coupon_code)
    percent = int(discount_percent or 0)
    if normalized and percent <= 0:
        percent = extract_discount_percent(normalized)
    return _discount_breakdown(subtotal, normalized, percent)
