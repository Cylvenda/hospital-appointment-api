from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ("health_education", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="educationalcontent",
            name="video_file",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="health_education/videos/",
                validators=[
                    django.core.validators.FileExtensionValidator(
                        allowed_extensions=["mp4", "mov", "webm", "m4v"]
                    )
                ],
            ),
        ),
    ]
