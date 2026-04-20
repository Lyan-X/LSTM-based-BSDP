# Legacy compatibility migration retained to preserve historical numbering.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("data_process", "0002_alter_parkingspotrealtime_options_and_more"),
    ]

    operations = []
