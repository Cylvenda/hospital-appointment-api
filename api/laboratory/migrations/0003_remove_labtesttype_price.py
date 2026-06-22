from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("laboratory", "0002_labtesttype_is_active"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="labtesttype",
            name="price",
        ),
    ]
