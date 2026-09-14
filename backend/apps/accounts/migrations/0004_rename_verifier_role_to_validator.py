from django.db import migrations, models


def rename_verifier_role(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Role.objects.filter(code="VERIFIER").update(code="VALIDATOR", name="Validator")


def restore_verifier_role(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Role.objects.filter(code="VALIDATOR").update(code="VERIFIER", name="Verifier")


class Migration(migrations.Migration):
    dependencies = [("accounts", "0003_alter_role_code")]

    operations = [
        migrations.RunPython(rename_verifier_role, restore_verifier_role),
        migrations.AlterField(
            model_name="role",
            name="code",
            field=models.CharField(
                choices=[
                    ("ADMIN", "Admin"),
                    ("VALIDATOR", "Validator"),
                    ("MANAGER", "Manager"),
                    ("AUDITOR", "Auditor"),
                    ("USER", "User"),
                ],
                max_length=20,
                unique=True,
            ),
        ),
    ]
