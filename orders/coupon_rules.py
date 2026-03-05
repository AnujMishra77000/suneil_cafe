import re


_TRAILING_DIGITS_RE = re.compile(r"(\d{2})$")


def normalize_coupon_code(raw_value):
    return "".join(str(raw_value or "").strip().upper().split())


def extract_discount_percent(code):
    normalized = normalize_coupon_code(code)
    if not normalized:
        raise ValueError("Enter a coupon code.")

    match = _TRAILING_DIGITS_RE.search(normalized)
    if not match:
        raise ValueError("Coupon code must end with two discount digits.")

    percent = int(match.group(1))
    if percent <= 0 or percent > 100:
        raise ValueError("Coupon discount must be between 1 and 100.")
    return percent
