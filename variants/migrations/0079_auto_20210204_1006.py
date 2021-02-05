# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2021-02-04 10:06
from __future__ import unicode_literals

import django.contrib.postgres.fields
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("variants", "0078_exportprojectcasesfilebgjob_cohort"),
    ]

    operations = [
        migrations.CreateModel(
            name="CasePhenotypeTerms",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("individual", models.CharField(help_text="Individual", max_length=128)),
                (
                    "terms",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.CharField(max_length=128),
                        default=list,
                        help_text="Phenotype annotation terms with HPO, Orphanet, and OMIM terms",
                        size=None,
                    ),
                ),
            ],
            options={"ordering": ("individual",),},
        ),
        migrations.AlterModelOptions(name="case", options={"ordering": ("-date_modified",)},),
        migrations.AddField(
            model_name="casephenotypeterms",
            name="case",
            field=models.ForeignKey(
                help_text="Case for this annotation",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="phenotype_terms",
                to="variants.Case",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="casephenotypeterms", unique_together=set([("case", "individual")]),
        ),
    ]