from django.db import migrations, models


def populate_asset_type(apps, schema_editor):
    Asset = apps.get_model("assets", "Asset")
    Asset.objects.filter(kind="DIGITAL").update(asset_type="DIGITAL_ASSET")
    Asset.objects.filter(kind="PHYSICAL").update(asset_type="UNIQUE_PHYSICAL_ASSET")


class Migration(migrations.Migration):
    dependencies = [("assets", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="asset",
            name="asset_type",
            field=models.CharField(blank=True, max_length=32, null=True),
        ),
        migrations.RunPython(populate_asset_type, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="asset",
            name="asset_type",
            field=models.CharField(
                choices=[
                    ("UNIQUE_PHYSICAL_ASSET", "Unique physical asset"),
                    ("DIGITAL_ASSET", "Digital asset"),
                ],
                max_length=32,
            ),
        ),
        migrations.AddIndex(
            model_name="asset",
            index=models.Index(fields=["asset_type", "state"], name="assets_asse_asset_t_2ad6b6_idx"),
        ),
    ]
