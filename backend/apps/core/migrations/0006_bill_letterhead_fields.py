from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_applicationsettings_ui_theme"),
    ]

    operations = [
        migrations.AddField(
            model_name="applicationsettings",
            name="alternate_phone",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="applicationsettings",
            name="email",
            field=models.EmailField(blank=True, default="", max_length=254),
        ),
        migrations.AddField(
            model_name="applicationsettings",
            name="authorised_signatory",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
        migrations.AddField(
            model_name="applicationsettings",
            name="invoice_terms",
            field=models.TextField(
                blank=True,
                default=(
                    "Goods once sold will not be taken back or exchanged.\n"
                    "Warranty, where applicable, is as per the manufacturer only.\n"
                    "Please check the items and the bill before leaving the counter.\n"
                    "Subject to local jurisdiction."
                ),
            ),
        ),
    ]
