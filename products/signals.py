from django.db import transaction
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from .cache_utils import invalidate_catalog_cache
from .models import Advertisement, Category, Product, Section
from .tasks import update_product_search_vector_task


@receiver(post_save, sender=Product)
def update_search_vector(sender, instance, update_fields=None, **kwargs):
    # Skip indexing for updates that don't touch searchable fields.
    if update_fields is not None and not ({"name", "description"} & set(update_fields)):
        return
    # Defer indexing until DB commit completes and run async in Celery.
    transaction.on_commit(lambda: update_product_search_vector_task.delay(instance.pk))


@receiver(post_save, sender=Product)
@receiver(post_delete, sender=Product)
@receiver(post_save, sender=Category)
@receiver(post_delete, sender=Category)
@receiver(post_save, sender=Section)
@receiver(post_delete, sender=Section)
@receiver(post_save, sender=Advertisement)
@receiver(post_delete, sender=Advertisement)
def invalidate_catalog_on_model_changes(sender, **kwargs):
    # Catalog endpoints are read-heavy and version-keyed; bumping version
    # invalidates all relevant cache entries without wildcard deletes.
    invalidate_catalog_cache()


@receiver(m2m_changed, sender=Product.related_products.through)
def invalidate_catalog_on_related_m2m(sender, action, **kwargs):
    if action in {"post_add", "post_remove", "post_clear"}:
        invalidate_catalog_cache()
