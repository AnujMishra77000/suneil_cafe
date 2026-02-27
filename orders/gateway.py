from twilio.rest import Client
from django.conf import settings
import logging
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def send_sms_via_twilio(number, message):
    if not number.startswith("+"):
        number = f"+{number}"

    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

    response = client.messages.create(
        body=message,
        from_=settings.TWILIO_PHONE_NUMBER,
        to=number
    )

    return response.sid

def send_whatsapp_via_twilio(number, message):
    if not number.startswith("+"):
        number = f"+{number}"
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    from_number = getattr(settings, "TWILIO_WHATSAPP_NUMBER", None)
    if not from_number:
        raise Exception("TWILIO_WHATSAPP_NUMBER not configured")
    response = client.messages.create(
        body=message,
        from_=f"whatsapp:{from_number}",
        to=f"whatsapp:{number}"
    )
    return response.sid

def send_email_notification(to_email, subject, message):
    try:
        send_mail(subject, message, None, [to_email], fail_silently=False)
        return True
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return False
