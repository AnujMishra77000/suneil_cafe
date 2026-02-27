import re

from .models import ServiceablePincode


PINCODE_PATTERN = re.compile(r"\b(\d{6})\b")


def normalize_pincode(value):
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    return digits if len(digits) == 6 else ""


def extract_pincode_from_text(text):
    match = PINCODE_PATTERN.search(str(text or ""))
    if not match:
        return ""
    return normalize_pincode(match.group(1))


def resolve_order_pincode(pincode="", address=""):
    normalized = normalize_pincode(pincode)
    if normalized:
        return normalized
    return extract_pincode_from_text(address)


def ensure_serviceable_pincode(pincode="", address=""):
    resolved = resolve_order_pincode(pincode=pincode, address=address)
    if not resolved:
        raise ValueError("Delivery pincode is required. Enter a valid 6-digit pincode.")

    is_serviceable = ServiceablePincode.objects.filter(code=resolved, is_active=True).exists()
    if not is_serviceable:
        raise ValueError(f"Sorry, we do not deliver to pincode {resolved} yet.")

    return resolved
