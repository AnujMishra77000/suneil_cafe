from celery import shared_task
from django.contrib.postgres.search import SearchVector
from django.core.files import File
from django.core.files.storage import default_storage

from .models import Product


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def update_product_search_vector_task(self, product_id):
    Product.objects.filter(pk=product_id).update(
        search_vector=(
            SearchVector("name", weight="A") + SearchVector("description", weight="B")
        )
    )


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def process_product_image_upload_task(self, product_id, temp_path):
    product = Product.objects.filter(pk=product_id).first()
    if not product:
        if default_storage.exists(temp_path):
            default_storage.delete(temp_path)
        return

    if not default_storage.exists(temp_path):
        return

    with default_storage.open(temp_path, "rb") as src:
        filename = temp_path.split("/")[-1]
        product.image.save(filename, File(src), save=True)

    default_storage.delete(temp_path)
