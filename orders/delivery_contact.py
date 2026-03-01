from django.conf import settings

from .models import DeliveryContactSetting


def get_delivery_contact_number():
    setting = DeliveryContactSetting.objects.only("delivery_contact_number").order_by("id").first()
    if setting is None:
        return (
            str(getattr(settings, "ADMIN_PHONE", "") or "").strip()
            or str(getattr(settings, "TWILIO_PHONE_NUMBER", "") or "").strip()
        )
    return str(setting.delivery_contact_number or "").strip()


def get_or_create_delivery_contact_setting():
    setting = DeliveryContactSetting.objects.order_by("id").first()
    if setting is not None:
        return setting
    return DeliveryContactSetting.objects.create()
