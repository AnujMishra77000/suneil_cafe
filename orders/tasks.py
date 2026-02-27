from celery import shared_task
from .models import Order,SMSLog
from .utils import build_customer_message, build_admin_message
from .gateway import send_sms_via_twilio, send_whatsapp_via_twilio, send_email_notification
from django.conf import settings

@shared_task
def send_order_notifications(order_id):
    order = Order.objects.prefetch_related('items__product', 'customer').get(id=order_id)

    customer_msg = build_customer_message(order)
    admin_msg = build_admin_message(order)

    try:
        send_sms_via_twilio(order.customer.phone, customer_msg)
    except Exception:
        pass
    try:
        if getattr(settings, "TWILIO_WHATSAPP_NUMBER", None):
            send_whatsapp_via_twilio(order.customer.phone, customer_msg)
    except Exception:
        pass

    ADMIN_PHONE = getattr(settings, "ADMIN_PHONE", "") or "+19592106648"
    try:
        send_sms_via_twilio(ADMIN_PHONE, admin_msg)
    except Exception:
        pass
    try:
        if getattr(settings, "TWILIO_WHATSAPP_NUMBER", None):
            send_whatsapp_via_twilio(ADMIN_PHONE, admin_msg)
    except Exception:
        pass
    if getattr(settings, "ADMIN_EMAIL", None):
        send_email_notification(settings.ADMIN_EMAIL, "New Order", admin_msg)

@shared_task(bind=True, max_retries=3)
def send_sms_task(self, sms_log_id):
    sms_log = SMSLog.objects.get(id=sms_log_id)

    try:
        sms_log.attempt_count += 1
        sms_log.save(update_fields=["attempt_count"])

        sid = send_sms_via_twilio(sms_log.phone_number, sms_log.message)

        sms_log.status = "SENT"
        sms_log.error_message = ""
        sms_log.save()

    except Exception as exc:
        sms_log.status = "FAILED"
        sms_log.error_message = str(exc)
        sms_log.save()

        raise self.retry(exc=exc, countdown=60 * sms_log.attempt_count)
