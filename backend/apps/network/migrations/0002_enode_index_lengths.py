from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("network", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="blockchainnode",
            name="enode",
            field=models.CharField(max_length=255, unique=True),
        ),
        migrations.AlterField(
            model_name="nodepeersnapshot",
            name="peer_enode",
            field=models.CharField(max_length=255),
        ),
    ]
