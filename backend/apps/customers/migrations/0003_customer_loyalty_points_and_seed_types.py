# Generated manually for loyalty stub + default customer types.

from django.db import migrations, models


def seed_customer_types(apps, schema_editor):
    CustomerType = apps.get_model("customers", "CustomerType")
    defaults = (
        ("general", "General"),
        ("electrician", "Electrician"),
        ("contractor", "Contractor"),
        ("builder", "Builder"),
        ("wholesale", "Wholesale"),
        ("retail", "Retail"),
        ("other", "Other"),
    )
    for code, name in defaults:
        CustomerType.objects.get_or_create(code=code, defaults={"name": name, "is_active": True})


def unseed_customer_types(apps, schema_editor):
    # Keep types — they may already be linked to customers.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0002_customer_current_balance"),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="loyalty_points",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RunPython(seed_customer_types, unseed_customer_types),
    ]
