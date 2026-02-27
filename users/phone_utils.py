from __future__ import annotations


class PhoneNormalizationError(ValueError):
    pass


def normalize_phone(value, *, allow_blank=False):
    """Return canonical 10-digit phone number used across the app."""
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if not digits and allow_blank:
        return ""

    if len(digits) < 10:
        raise PhoneNormalizationError("Phone number must contain at least 10 digits")

    return digits[-10:]
