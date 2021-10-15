# Generated by Django 3.2.7 on 2021-10-08 11:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("importer", "0009_auto_20211008_1015"),
    ]

    operations = [
        migrations.AlterField(
            model_name="variantsetimportinfo",
            name="genomebuild",
            field=models.CharField(
                choices=[("GRCh37", "GRCh37"), ("GRCh38", "GRCh38")],
                default="GRCh37",
                help_text="Genome build used in the variant set.",
                max_length=32,
            ),
        ),
    ]