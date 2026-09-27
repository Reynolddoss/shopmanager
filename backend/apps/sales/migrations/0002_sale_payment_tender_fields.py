# Generated manually for counter payment tender / change / UPI reference.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="sale",
            name="amount_tendered",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
        migrations.AddField(
            model_name="sale",
            name="change_given",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
        migrations.AddField(
            model_name="sale",
            name="payment_reference",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
    ]
