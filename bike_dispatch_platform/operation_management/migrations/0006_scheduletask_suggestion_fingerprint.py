from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("operation_management", "0005_scheduletask_created_by_creator_role"),
    ]

    operations = [
        migrations.AddField(
            model_name="scheduletask",
            name="suggestion_fingerprint",
            field=models.CharField(blank=True, db_index=True, max_length=128, verbose_name="建议指纹"),
        ),
    ]
