# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-10-14 12:18
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("geneinfo", "0017_auto_20191004_1414")]

    operations = [
        migrations.CreateModel(
            name="EnsemblToGeneSymbol",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("ensembl_gene_id", models.CharField(max_length=32, null=True)),
                ("gene_symbol", models.CharField(max_length=32)),
            ],
        ),
        migrations.CreateModel(
            name="RefseqToGeneSymbol",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("entrez_id", models.CharField(max_length=16, null=True)),
                ("gene_symbol", models.CharField(max_length=32)),
            ],
        ),
        migrations.AddIndex(
            model_name="refseqtogenesymbol",
            index=models.Index(fields=["entrez_id"], name="geneinfo_re_entrez__3b440a_idx"),
        ),
        migrations.AddIndex(
            model_name="ensembltogenesymbol",
            index=models.Index(fields=["ensembl_gene_id"], name="geneinfo_en_ensembl_9b7f1b_idx"),
        ),
    ]