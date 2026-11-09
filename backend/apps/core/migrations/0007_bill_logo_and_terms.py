from django.db import migrations, models

import apps.core.models


# Terms written by 0006. Replaced only when the shop has not edited them.
PREVIOUS_TERMS = (
    "Goods once sold will not be taken back or exchanged.\n"
    "Warranty, where applicable, is as per the manufacturer only.\n"
    "Please check the items and the bill before leaving the counter.\n"
    "Subject to local jurisdiction."
)

NEXT_TERMS = apps.core.models.InvoiceCopy.DEFAULT_TERMS


def widen_existing_terms(apps, schema_editor):
    """Give shops that still use the short default the longer bill terms."""
    settings_model = apps.get_model("core", "ApplicationSettings")
    settings_model.objects.filter(invoice_terms__in=["", PREVIOUS_TERMS]).update(invoice_terms=NEXT_TERMS)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_bill_letterhead_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="applicationsettings",
            name="logo",
            field=models.ImageField(blank=True, null=True, upload_to=apps.core.models.shop_logo_upload_to),
        ),
        migrations.AlterField(
            model_name="applicationsettings",
            name="email",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AlterField(
            model_name="applicationsettings",
            name="gstin",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AlterField(
            model_name="applicationsettings",
            name="invoice_terms",
            field=models.TextField(blank=True, default=NEXT_TERMS),
        ),
        migrations.RunPython(widen_existing_terms, migrations.RunPython.noop),
    ]
