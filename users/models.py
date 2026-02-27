from django.db import models

class Customer(models.Model):
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=15, db_index=True)
    whatsapp_no = models.CharField(max_length=15)
    address = models.TextField(blank=True, default="")

    def __str__(self):
        return self.name
