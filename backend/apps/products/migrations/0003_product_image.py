# Generated manually for product catalog photos.

from django.db import migrations, models
import apps.products.models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0002_tag_product_max_stock_quantity_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="image",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to=apps.products.models.product_image_upload_to,
            ),
        ),
    ]
