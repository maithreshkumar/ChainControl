from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("identities", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="decentralizedidentity",
            name="state",
            field=models.CharField(
                choices=[
                    ("INVITED", "Invited"),
                    ("VALIDATION_PENDING", "Validation pending"),
                    ("BLOCKCHAIN_PENDING", "Blockchain pending"),
                    ("ACTIVE", "Active"),
                    ("SUSPENDED", "Suspended"),
                    ("REVOKED", "Revoked"),
                    ("REGISTRATION_FAILED", "Registration failed"),
                ],
                default="INVITED",
                max_length=24,
            ),
        ),
    ]
