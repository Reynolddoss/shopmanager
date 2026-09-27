import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_applicationsettings_enforce_safe_selling_price_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="applicationsettings",
            name="invoice_prefix",
            field=models.CharField(default="SH", max_length=16),
        ),
        migrations.AlterField(
            model_name="applicationsettings",
            name="sale_invoice_prefix",
            field=models.CharField(default="SH", max_length=16),
        ),
        migrations.AlterField(
            model_name="applicationsettings",
            name="shop_name",
            field=models.CharField(default="", max_length=255),
        ),
        migrations.CreateModel(
            name="ShopOperator",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("full_name", models.CharField(max_length=128)),
                ("phone", models.CharField(blank=True, default="", max_length=32)),
                ("is_owner", models.BooleanField(db_index=True, default=False)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="shop_operator",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["full_name"],
            },
        ),
    ]
