from django.core.exceptions import ValidationError
from django.db import models

from .phone_utils import PhoneNormalizationError, normalize_phone


class Customer(models.Model):
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=15, unique=True, db_index=True)
    whatsapp_no = models.CharField(max_length=15)
    address = models.TextField(blank=True, default="")

    def clean(self):
        try:
            normalized_phone = normalize_phone(self.phone)
        except PhoneNormalizationError as exc:
            raise ValidationError({"phone": str(exc)}) from exc

        try:
            normalized_whatsapp = normalize_phone(
                self.whatsapp_no or normalized_phone,
                allow_blank=False,
            )
        except PhoneNormalizationError as exc:
            raise ValidationError({"whatsapp_no": str(exc)}) from exc

        self.phone = normalized_phone
        self.whatsapp_no = normalized_whatsapp

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
