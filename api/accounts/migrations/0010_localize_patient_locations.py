from django.db import migrations, models


def copy_location_names(apps, schema_editor):
    PatientProfile = apps.get_model("accounts", "PatientProfile")

    for profile in PatientProfile.objects.select_related(
        "region", "district"
    ).iterator():
        profile.region_text = profile.region.name if profile.region else None
        profile.district_text = profile.district.name if profile.district else None
        profile.save(update_fields=["region_text", "district_text"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0009_patientprofile_patient_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="patientprofile",
            name="region_text",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="patientprofile",
            name="district_text",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="patientprofile",
            name="ward",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.RunPython(copy_location_names, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="patientprofile",
            name="district",
        ),
        migrations.RemoveField(
            model_name="patientprofile",
            name="region",
        ),
        migrations.RenameField(
            model_name="patientprofile",
            old_name="region_text",
            new_name="region",
        ),
        migrations.RenameField(
            model_name="patientprofile",
            old_name="district_text",
            new_name="district",
        ),
        migrations.DeleteModel(
            name="District",
        ),
        migrations.DeleteModel(
            name="Region",
        ),
    ]
