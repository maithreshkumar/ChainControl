from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_invitation")]

    operations = [
        migrations.AlterField(
            model_name="role",
            name="code",
            field=models.CharField(
                choices=[
                    ("ADMIN", "Admin"),
                    ("VERIFIER", "Verifier"),
                    ("MANAGER", "Manager"),
                    ("AUDITOR", "Auditor"),
                    ("USER", "User"),
                ],
                max_length=20,
                unique=True,
            ),
        ),
    ]
