# Generated by Django 3.2.7 on 2021-10-08 10:15

from django.db import migrations
import varfish.utils


class Migration(migrations.Migration):

    dependencies = [
        ("clinvar_export", "0002_bootstrap_records"),
    ]

    operations = [
        migrations.AlterField(
            model_name="family",
            name="pedigree",
            field=varfish.utils.JSONField(
                blank=True, default=list, help_text="Pedigree information.", null=True
            ),
        ),
        migrations.AlterField(
            model_name="submission",
            name="diseases",
            field=varfish.utils.JSONField(blank=True, default=list, null=True),
        ),
        migrations.AlterField(
            model_name="submissionindividual",
            name="phenotypes",
            field=varfish.utils.JSONField(blank=True, default=list, null=True),
        ),
    ]