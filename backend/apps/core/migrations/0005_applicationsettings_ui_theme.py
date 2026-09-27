from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_shop_operator_and_generic_defaults"),
    ]

    operations = [
        migrations.AddField(
            model_name="applicationsettings",
            name="ui_theme",
            field=models.CharField(
                default="midnight",
                help_text="Desktop UI theme id: midnight, slate, or paper.",
                max_length=32,
            ),
        ),
    ]
