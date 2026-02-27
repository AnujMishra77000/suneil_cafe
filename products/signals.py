from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Product
from .tasks import update_product_search_vector_task


@receiver(post_save, sender=Product)
def update_search_vector(sender, instance, update_fields=None, **kwargs):
    # Skip indexing for updates that don't touch searchable fields.
    if update_fields is not None and not ({"name", "description"} & set(update_fields)):
        return
    # Defer indexing until DB commit completes and run async in Celery.
    transaction.on_commit(lambda: update_product_search_vector_task.delay(instance.pk))
