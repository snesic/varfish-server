# Generated by Django 3.2.4 on 2021-06-17 14:09

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("geneinfo", "0023_materialized_view_geneidinhpo_fix"),
    ]

    operations = [
        migrations.AlterField(
            model_name="ncbigenerif",
            name="pubmed_ids",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.CharField(max_length=16), default=list, size=None
            ),
        ),
    ]
