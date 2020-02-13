"""Tests for the ``queries`` module.

Remarks:

- VCF export is only tested for case one at the moment, as it shares a major part of the implementation with
  the render and tabular file export query.
"""

from clinvar.tests.factories import ClinvarFactory
from conservation.tests.factories import KnownGeneAAFactory
from frequencies.tests.factories import MitomapFactory, HelixMtDbFactory, MtDbFactory
from hgmd.tests.factories import HgmdPublicLocusFactory
from variants.models import Case, SmallVariantSet
from variants.queries import (
    CasePrefetchQuery,
    CaseExportTableQuery,
    CaseExportVcfQuery,
    CaseLoadPrefetchedQuery,
    ProjectPrefetchQuery,
    ProjectLoadPrefetchedQuery,
    KnownGeneAAQuery,
)
from geneinfo.tests.factories import (
    HgncFactory,
    AcmgFactory,
    GeneIdToInheritanceFactory,
    GnomadConstraintsFactory,
    ExacConstraintsFactory,
    MgiMappingFactory,
    RefseqToGeneSymbolFactory,
    EnsemblToGeneSymbolFactory,
)
from dbsnp.tests.factories import DbsnpFactory
from .factories import (
    SmallVariantFactory,
    SmallVariantSummaryFactory,
    ProjectFactory,
    ProjectCasesSmallVariantQueryFactory,
    SmallVariantQueryFactory,
    SmallVariantSetFactory,
)
from .helpers import TestBase, SupportQueryTestBase, SQLALCHEMY_ENGINE


# TODO: select correct cases from multiple ones
# TODO: prefetch from multiple cases


class TestCaseOneLoadSingletonResults(SupportQueryTestBase):
    def setUp(self):
        """Create a case and 3 variants, first one is linked to ACMG and has effect ambiguity.
        As we check the content of the results, make sure they are on the same chromosome to
        avoid ordering issues when we hit the change from chromosome Y to 1."""
        super().setUp()
        variant_set = SmallVariantSetFactory()
        case = variant_set.case
        self.acmg = AcmgFactory(entrez_id="1000")
        small_vars = [
            SmallVariantFactory(
                chromosome="1",
                ensembl_effect=["synonymous_variant"],
                refseq_effect=["stop_gained"],
                refseq_gene_id=self.acmg.entrez_id,
                variant_set=variant_set,
            ),
            SmallVariantFactory(chromosome="1", variant_set=variant_set),
            SmallVariantFactory(chromosome="1", variant_set=variant_set),
        ]
        # Prepare mode of inheritance
        self.modes_of_inheritance = [
            GeneIdToInheritanceFactory(
                ensembl_gene_id=small_vars[0].ensembl_gene_id,
                entrez_id=small_vars[0].refseq_gene_id,
                mode_of_inheritance="AD",
            ),
            GeneIdToInheritanceFactory(
                ensembl_gene_id=small_vars[0].ensembl_gene_id,
                entrez_id=small_vars[0].refseq_gene_id,
                mode_of_inheritance="AR",
            ),
        ]
        # Prepare constraints
        self.gnomad_constraints = GnomadConstraintsFactory(
            ensembl_gene_id=small_vars[0].ensembl_gene_id
        )
        self.exac_constraints = ExacConstraintsFactory(
            ensembl_transcript_id=small_vars[0].ensembl_transcript_id
        )
        # Prepare MGI records
        self.mgi = MgiMappingFactory(human_entrez_id=small_vars[0].refseq_gene_id)
        # Prepare smallvariant query results
        self.smallvariantquery = SmallVariantQueryFactory(case=case)
        self.smallvariantquery.query_results.add(small_vars[0].id, small_vars[1].id)
        # Prepare projectcases smallvariant query results
        self.projectcasessmallvariantquery = ProjectCasesSmallVariantQueryFactory(
            project=case.project
        )
        self.projectcasessmallvariantquery.query_results.add(small_vars[0].id, small_vars[2].id)

    def test_load_prefetched_case_results(self):
        results = self.run_query(
            CaseLoadPrefetchedQuery, {"filter_job_id": self.smallvariantquery.id}, 2
        )
        self.assertEqual(results[0].acmg_symbol, self.acmg.symbol)
        self.assertIsNone(results[1].acmg_symbol)
        self.assertTrue(results[0].effect_ambiguity)
        self.assertFalse(results[1].effect_ambiguity)
        self.assertEqual(
            results[0].modes_of_inheritance,
            [
                self.modes_of_inheritance[0].mode_of_inheritance,
                self.modes_of_inheritance[1].mode_of_inheritance,
            ],
        )
        self.assertEqual(results[0].gnomad_pLI, self.gnomad_constraints.pLI)
        self.assertEqual(results[0].exac_pLI, self.exac_constraints.pLI)
        self.assertEqual(results[0].mgi_id, self.mgi.mgi_id)
        self.assertIsNone(results[1].mgi_id)

    def test_load_prefetched_project_cases_results(self):
        results = self.run_query(
            ProjectLoadPrefetchedQuery,
            {"filter_job_id": self.projectcasessmallvariantquery.id},
            2,
            query_type="project",
        )
        self.assertEqual(results[0].acmg_symbol, self.acmg.symbol)
        self.assertIsNone(results[1].acmg_symbol)
        self.assertEqual(results[0].mgi_id, self.mgi.mgi_id)
        self.assertTrue(results[0].effect_ambiguity)
        self.assertFalse(results[1].effect_ambiguity)
        self.assertIsNone(results[1].mgi_id)


class TestCaseLoadPrefetchedSorting(SupportQueryTestBase):
    def setUp(self):
        super().setUp()
        variant_set = SmallVariantSetFactory()
        self.small_vars = SmallVariantFactory.create_batch(10, variant_set=variant_set)
        self.small_vars.reverse()
        self.smallvariantquery = SmallVariantQueryFactory(case=variant_set.case)
        self.smallvariantquery.query_results.add(*self.small_vars)

    def test_case_load_prefetched_sorted(self):
        results = self.run_query(
            CaseLoadPrefetchedQuery, {"filter_job_id": self.smallvariantquery.id}, 10
        )
        small_vars_sorted = sorted(self.small_vars, key=lambda x: x.chromosome_no)
        self.assertEqual(results[0]["chromosome"], small_vars_sorted[0].chromosome)
        self.assertEqual(results[1]["chromosome"], small_vars_sorted[1].chromosome)
        self.assertEqual(results[2]["chromosome"], small_vars_sorted[2].chromosome)
        self.assertEqual(results[3]["chromosome"], small_vars_sorted[3].chromosome)
        self.assertEqual(results[4]["chromosome"], small_vars_sorted[4].chromosome)
        self.assertEqual(results[5]["chromosome"], small_vars_sorted[5].chromosome)
        self.assertEqual(results[6]["chromosome"], small_vars_sorted[6].chromosome)
        self.assertEqual(results[7]["chromosome"], small_vars_sorted[7].chromosome)
        self.assertEqual(results[8]["chromosome"], small_vars_sorted[8].chromosome)
        self.assertEqual(results[9]["chromosome"], small_vars_sorted[9].chromosome)


class TestCaseOneQueryDatabaseSwitch(SupportQueryTestBase):
    """Test whether both RefSeq and ENSEMBL databases work."""

    def setUp(self):
        """Create a case with just one variant and HGNC record."""
        super().setUp()
        small_var = SmallVariantFactory()
        self.hgnc = HgncFactory(
            entrez_id=small_var.refseq_gene_id, ensembl_gene_id=small_var.ensembl_gene_id
        )
        self.ensembltogenesymbol = EnsemblToGeneSymbolFactory(
            ensembl_gene_id=small_var.ensembl_gene_id
        )
        self.refseqtogenesymbol = RefseqToGeneSymbolFactory(entrez_id=small_var.refseq_gene_id)

    def test_base_query_refseq_filter(self):
        self.run_query(CasePrefetchQuery, {"database_select": "refseq"}, 1)

    def test_base_query_refseq_export(self):
        self.run_query(CaseExportTableQuery, {"database_select": "refseq"}, 1)

    def test_base_query_refseq_vcf(self):
        self.run_query(CaseExportVcfQuery, {"database_select": "refseq"}, 1)

    def test_base_query_ensembl_filter(self):
        self.run_query(CasePrefetchQuery, {"database_select": "ensembl"}, 1)

    def test_base_query_ensembl_export(self):
        self.run_query(CaseExportTableQuery, {"database_select": "ensembl"}, 1)

    def test_base_query_ensembl_vcf(self):
        self.run_query(CaseExportVcfQuery, {"database_select": "ensembl"}, 1)

    def test_base_query_refseq_check_gene_symbol(self):
        results = self.run_query(CasePrefetchQuery, {"database_select": "refseq"}, 1)
        self.assertEqual(results[0].symbol, self.hgnc.symbol)
        self.assertEqual(results[0].gene_symbol, self.refseqtogenesymbol.gene_symbol)

    def test_base_query_ensembl_check_gene_symbol_from_hgnc(self):
        results = self.run_query(CasePrefetchQuery, {"database_select": "ensembl"}, 1)
        self.assertEqual(results[0].symbol, self.hgnc.symbol)
        self.assertEqual(results[0].gene_symbol, self.ensembltogenesymbol.gene_symbol)


class TestCaseOneQueryNotInDbsnp(SupportQueryTestBase):
    """Test whether both RefSeq and ENSEMBL databases work."""

    def setUp(self):
        """Create 3 variants and two dbSNP entries."""
        super().setUp()
        variant_set = SmallVariantSetFactory()
        small_vars = SmallVariantFactory.create_batch(3, variant_set=variant_set)
        DbsnpFactory(
            release=small_vars[0].release,
            chromosome=small_vars[0].chromosome,
            start=small_vars[0].start,
            end=small_vars[0].end,
            bin=small_vars[0].bin,
            reference=small_vars[0].reference,
            alternative=small_vars[0].alternative,
        )
        DbsnpFactory(
            release=small_vars[2].release,
            chromosome=small_vars[2].chromosome,
            start=small_vars[2].start,
            end=small_vars[2].end,
            bin=small_vars[2].bin,
            reference=small_vars[2].reference,
            alternative=small_vars[2].alternative,
        )

    def test_base_query_not_in_dbsnp_filter(self):
        self.run_query(CasePrefetchQuery, {"remove_if_in_dbsnp": True}, 1)

    def test_base_query_not_in_dbsnp_export(self):
        self.run_query(CaseExportTableQuery, {"remove_if_in_dbsnp": True}, 1)

    def test_base_query_not_in_dbsnp_vcf(self):
        self.run_query(CaseExportVcfQuery, {"remove_if_in_dbsnp": True}, 1)

    def test_base_query_filter(self):
        self.run_query(CasePrefetchQuery, {}, 3)

    def test_base_query_export(self):
        self.run_query(CaseExportTableQuery, {}, 3)

    def test_base_query_vcf(self):
        self.run_query(CaseExportVcfQuery, {}, 3)


class TestCaseOneQueryCase(SupportQueryTestBase):
    """Test with correct and incorrect case UUID"""

    def setUp(self):
        """Create case with just one variant."""
        super().setUp()
        SmallVariantFactory()

    def test_query_case_correct_filter(self):
        self.run_query(CasePrefetchQuery, {}, 1)

    def test_query_case_correct_export(self):
        self.run_query(CaseExportTableQuery, {}, 1)

    def test_query_case_correct_vcf(self):
        self.run_query(CaseExportVcfQuery, {}, 1)

    def test_query_case_incorrect_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {"case_uuid": "88888888-8888-8888-8888-888888888888"},
            1,
            Case.DoesNotExist,
        )

    def test_query_case_incorrect_export(self):
        self.run_query(
            CaseExportTableQuery,
            {"case_uuid": "88888888-8888-8888-8888-888888888888"},
            1,
            Case.DoesNotExist,
        )

    def test_query_case_incorrect_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {"case_uuid": "88888888-8888-8888-8888-888888888888"},
            1,
            Case.DoesNotExist,
        )

    def test_query_case_missing_variant_set_filter(self):
        SmallVariantSet.objects.all().delete()
        self.run_query(CasePrefetchQuery, {}, 1, RuntimeError)

    def test_query_case_missing_variant_set_export(self):
        SmallVariantSet.objects.all().delete()
        self.run_query(CaseExportTableQuery, {}, 1, RuntimeError)

    def test_query_case_missing_variant_set_vcf(self):
        SmallVariantSet.objects.all().delete()
        self.run_query(CaseExportVcfQuery, {}, 1, RuntimeError)


class TestCaseOneQueryCaseFromTwoCases(SupportQueryTestBase):
    """Test with correct and incorrect case UUID"""

    def setUp(self):
        """Create case with just one variant."""
        super().setUp()
        self.variant_sets = SmallVariantSetFactory.create_batch(2)
        SmallVariantFactory(variant_set=self.variant_sets[0])
        SmallVariantFactory(variant_set=self.variant_sets[1])
        SmallVariantFactory(variant_set=self.variant_sets[1])

    def test_query_case1_correct_filter(self):
        self.run_query(CasePrefetchQuery, {"case_uuid": self.variant_sets[0].case.sodar_uuid}, 1)

    def test_query_case1_correct_export(self):
        self.run_query(CaseExportTableQuery, {"case_uuid": self.variant_sets[0].case.sodar_uuid}, 1)

    def test_query_case1_correct_vcf(self):
        self.run_query(CaseExportVcfQuery, {"case_uuid": self.variant_sets[0].case.sodar_uuid}, 1)

    def test_query_case2_correct_filter(self):
        self.run_query(CasePrefetchQuery, {"case_uuid": self.variant_sets[1].case.sodar_uuid}, 2)

    def test_query_case2_correct_export(self):
        self.run_query(CaseExportTableQuery, {"case_uuid": self.variant_sets[1].case.sodar_uuid}, 2)

    def test_query_case2_correct_vcf(self):
        self.run_query(CaseExportVcfQuery, {"case_uuid": self.variant_sets[1].case.sodar_uuid}, 2)


class TestCaseOneQueryVarTypeSwitch(SupportQueryTestBase):
    """Test switch for variant type (SNV, MNV, InDel)"""

    def setUp(self):
        """Create one case with 3 variants of different var_type."""
        super().setUp()
        variant_set = SmallVariantSetFactory()
        SmallVariantFactory(var_type="snv", variant_set=variant_set)
        SmallVariantFactory(var_type="mnv", variant_set=variant_set)
        SmallVariantFactory(var_type="indel", variant_set=variant_set)

    def test_var_type_none_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {"var_type_snv": False, "var_type_mnv": False, "var_type_indel": False},
            0,
        )

    def test_var_type_none_export(self):
        self.run_query(
            CaseExportTableQuery,
            {"var_type_snv": False, "var_type_mnv": False, "var_type_indel": False},
            0,
        )

    def test_var_type_none_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {"var_type_snv": False, "var_type_mnv": False, "var_type_indel": False},
            0,
        )

    def test_var_type_mnv_filter(self):
        self.run_query(CasePrefetchQuery, {"var_type_snv": False, "var_type_indel": False}, 1)

    def test_var_type_mnv_export(self):
        self.run_query(CaseExportTableQuery, {"var_type_snv": False, "var_type_indel": False}, 1)

    def test_var_type_mnv_vcf(self):
        self.run_query(CaseExportVcfQuery, {"var_type_snv": False, "var_type_indel": False}, 1)

    def test_var_type_snv_filter(self):
        self.run_query(CasePrefetchQuery, {"var_type_mnv": False, "var_type_indel": False}, 1)

    def test_var_type_snv_export(self):
        self.run_query(CaseExportTableQuery, {"var_type_mnv": False, "var_type_indel": False}, 1)

    def test_var_type_snv_vcf(self):
        self.run_query(CaseExportVcfQuery, {"var_type_mnv": False, "var_type_indel": False}, 1)

    def test_var_type_indel_filter(self):
        self.run_query(CasePrefetchQuery, {"var_type_snv": False, "var_type_mnv": False}, 1)

    def test_var_type_indel_export(self):
        self.run_query(CaseExportTableQuery, {"var_type_snv": False, "var_type_mnv": False}, 1)

    def test_var_type_indel_vcf(self):
        self.run_query(CaseExportVcfQuery, {"var_type_snv": False, "var_type_mnv": False}, 1)

    def test_var_type_all_filter(self):
        self.run_query(CasePrefetchQuery, {}, 3)

    def test_var_type_all_export(self):
        self.run_query(CaseExportTableQuery, {}, 3)

    def test_var_type_all_vcf(self):
        self.run_query(CaseExportVcfQuery, {}, 3)


class TestCaseOneQueryFrequency(SupportQueryTestBase):
    """Test switch for all four frequency filters + frequency limits + homozygous limits

    Each limit is tested for lower, critical and higher values. The data is designed
    to cover this with one test function rather than having three test functions for this
    setting. 'None' is tested within the switch or the other function. This is the value
    when no value in the interface was entered.

    tested databases:
    - gnomad exomes, gnomad genomes, exac, thousand genomes
    """

    def setUp(self):
        """Create a case and 3 variants with different frequencies and count values and
        a corresponding variantsummary entry.
        """
        super().setUp()
        self.variant_set = SmallVariantSetFactory()
        for i in range(3):
            # this emulates 0.001, 0.01 and 0.1 frequency
            freq = 1 / 10 ** (3 - i)
            # this emulates increasing count starting from 1
            count = i + 1
            small_var = SmallVariantFactory(
                chromosome="1",
                gnomad_genomes_frequency=freq,
                gnomad_genomes_heterozygous=count,
                gnomad_genomes_homozygous=count,
                gnomad_exomes_frequency=freq,
                gnomad_exomes_heterozygous=count,
                gnomad_exomes_homozygous=count,
                exac_frequency=freq,
                exac_heterozygous=count,
                exac_homozygous=count,
                thousand_genomes_frequency=freq,
                thousand_genomes_heterozygous=count,
                thousand_genomes_homozygous=count,
                variant_set=self.variant_set,
            )
            SmallVariantSummaryFactory(
                chromosome=small_var.chromosome,
                start=small_var.start,
                end=small_var.end,
                bin=small_var.bin,
                reference=small_var.reference,
                alternative=small_var.alternative,
                count_het=count,
                count_hom_alt=count,
            )

    def _setup_additional_variant_with_missing_inhouse_record(self):
        # Setup an additional variant and make sure it passes the default filter settings.
        freq = 1 / 10 ** 3  # 0.001
        count = 1
        SmallVariantFactory(
            gnomad_genomes_frequency=freq,
            gnomad_genomes_heterozygous=count,
            gnomad_genomes_homozygous=count,
            gnomad_exomes_frequency=freq,
            gnomad_exomes_heterozygous=count,
            gnomad_exomes_homozygous=count,
            exac_frequency=freq,
            exac_heterozygous=count,
            exac_homozygous=count,
            thousand_genomes_frequency=freq,
            thousand_genomes_heterozygous=count,
            thousand_genomes_homozygous=count,
            variant_set=self.variant_set,
        )

    def test_frequency_filters_disabled_filter(self):
        self.run_query(CasePrefetchQuery, {}, 3)

    def test_frequency_filters_disabled_export(self):
        self.run_query(CaseExportTableQuery, {}, 3)

    def test_frequency_filters_disabled_vcf(self):
        self.run_query(CaseExportVcfQuery, {}, 3)

    def test_frequency_thousand_genomes_enabled_filter(self):
        self.run_query(CasePrefetchQuery, {"thousand_genomes_enabled": True}, 0)

    def test_frequency_thousand_genomes_enabled_export(self):
        self.run_query(CaseExportTableQuery, {"thousand_genomes_enabled": True}, 0)

    def test_frequency_thousand_genomes_enabled_vcf(self):
        self.run_query(CaseExportVcfQuery, {"thousand_genomes_enabled": True}, 0)

    def test_frequency_exac_enabled_filter(self):
        self.run_query(CasePrefetchQuery, {"exac_enabled": True}, 0)

    def test_frequency_exac_enabled_export(self):
        self.run_query(CaseExportTableQuery, {"exac_enabled": True}, 0)

    def test_frequency_exac_enabled_vcf(self):
        self.run_query(CaseExportVcfQuery, {"exac_enabled": True}, 0)

    def test_frequency_gnomad_exomes_enabled_filter(self):
        self.run_query(CasePrefetchQuery, {"gnomad_exomes_enabled": True}, 0)

    def test_frequency_gnomad_exomes_enabled_export(self):
        self.run_query(CaseExportTableQuery, {"gnomad_exomes_enabled": True}, 0)

    def test_frequency_gnomad_exomes_enabled_vcf(self):
        self.run_query(CaseExportVcfQuery, {"gnomad_exomes_enabled": True}, 0)

    def test_frequency_gnomad_genomes_enabled_filter(self):
        self.run_query(CasePrefetchQuery, {"gnomad_genomes_enabled": True}, 0)

    def test_frequency_gnomad_genomes_enabled_export(self):
        self.run_query(CaseExportTableQuery, {"gnomad_genomes_enabled": True}, 0)

    def test_frequency_gnomad_genomes_enabled_vcf(self):
        self.run_query(CaseExportVcfQuery, {"gnomad_genomes_enabled": True}, 0)

    def test_frequency_inhouse_enabled_filter(self):
        self.run_query(CasePrefetchQuery, {"inhouse_enabled": True}, 0)

    def test_frequency_inhouse_enabled_export(self):
        self.run_query(CaseExportTableQuery, {"inhouse_enabled": True}, 0)

    def test_frequency_inhouse_enabled_vcf(self):
        self.run_query(CaseExportVcfQuery, {"inhouse_enabled": True}, 0)

    def test_frequency_thousand_genomes_limits_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {
                "thousand_genomes_enabled": True,
                "thousand_genomes_frequency": 0.01,
                "thousand_genomes_homozygous": None,
                "thousand_genomes_heterozygous": None,
            },
            2,
        )

    def test_frequency_thousand_genomes_limits_export(self):
        self.run_query(
            CaseExportTableQuery,
            {
                "thousand_genomes_enabled": True,
                "thousand_genomes_frequency": 0.01,
                "thousand_genomes_homozygous": None,
                "thousand_genomes_heterozygous": None,
            },
            2,
        )

    def test_frequency_thousand_genomes_limits_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {
                "thousand_genomes_enabled": True,
                "thousand_genomes_frequency": 0.01,
                "thousand_genomes_homozygous": None,
                "thousand_genomes_heterozygous": None,
            },
            2,
        )

    def test_frequency_exac_limits_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {
                "exac_enabled": True,
                "exac_frequency": 0.01,
                "exac_homozygous": None,
                "exac_heterozygous": None,
            },
            2,
        )

    def test_frequency_exac_limits_export(self):
        self.run_query(
            CaseExportTableQuery,
            {
                "exac_enabled": True,
                "exac_frequency": 0.01,
                "exac_homozygous": None,
                "exac_heterozygous": None,
            },
            2,
        )

    def test_frequency_exac_limits_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {
                "exac_enabled": True,
                "exac_frequency": 0.01,
                "exac_homozygous": None,
                "exac_heterozygous": None,
            },
            2,
        )

    def test_frequency_gnomad_exomes_limits_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {
                "gnomad_exomes_enabled": True,
                "gnomad_exomes_frequency": 0.01,
                "gnomad_exomes_homozygous": None,
                "gnomad_exomes_heterozygous": None,
            },
            2,
        )

    def test_frequency_gnomad_exomes_limits_export(self):
        self.run_query(
            CaseExportTableQuery,
            {
                "gnomad_exomes_enabled": True,
                "gnomad_exomes_frequency": 0.01,
                "gnomad_exomes_homozygous": None,
                "gnomad_exomes_heterozygous": None,
            },
            2,
        )

    def test_frequency_gnomad_exomes_limits_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {
                "gnomad_exomes_enabled": True,
                "gnomad_exomes_frequency": 0.01,
                "gnomad_exomes_homozygous": None,
                "gnomad_exomes_heterozygous": None,
            },
            2,
        )

    def test_frequency_gnomad_genomes_limits_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {
                "gnomad_genomes_enabled": True,
                "gnomad_genomes_frequency": 0.01,
                "gnomad_genomes_homozygous": None,
                "gnomad_genomes_heterozygous": None,
            },
            2,
        )

    def test_frequency_gnomad_genomes_limits_export(self):
        self.run_query(
            CaseExportTableQuery,
            {
                "gnomad_genomes_enabled": True,
                "gnomad_genomes_frequency": 0.01,
                "gnomad_genomes_homozygous": None,
                "gnomad_genomes_heterozygous": None,
            },
            2,
        )

    def test_frequency_gnomad_genomes_limits_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {
                "gnomad_genomes_enabled": True,
                "gnomad_genomes_frequency": 0.01,
                "gnomad_genomes_homozygous": None,
                "gnomad_genomes_heterozygous": None,
            },
            2,
        )

    # NB: we use carriers instead of carriers for in-house DB

    def test_carriers_inhouse_limits_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {
                "inhouse_enabled": True,
                "inhouse_carriers": 4,
                "inhouse_homozygous": None,
                "inhouse_heterozygous": None,
            },
            2,
        )

    def test_carriers_inhouse_limits_export(self):
        self.run_query(
            CaseExportTableQuery,
            {
                "inhouse_enabled": True,
                "inhouse_carriers": 4,
                "inhouse_homozygous": None,
                "inhouse_heterozygous": None,
            },
            2,
        )

    def test_carriers_inhouse_limits_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {
                "inhouse_enabled": True,
                "inhouse_carriers": 4,
                "inhouse_homozygous": None,
                "inhouse_heterozygous": None,
            },
            2,
        )

    def test_carriers_inhouse_limits_filter_missing_inhouse_record(self):
        self._setup_additional_variant_with_missing_inhouse_record()
        self.run_query(
            CasePrefetchQuery,
            {
                "inhouse_enabled": True,
                "inhouse_carriers": 4,
                "inhouse_homozygous": None,
                "inhouse_heterozygous": None,
            },
            3,
        )

    def test_carriers_inhouse_limits_export_missing_inhouse_record(self):
        self._setup_additional_variant_with_missing_inhouse_record()
        self.run_query(
            CaseExportTableQuery,
            {
                "inhouse_enabled": True,
                "inhouse_carriers": 4,
                "inhouse_homozygous": None,
                "inhouse_heterozygous": None,
            },
            3,
        )

    def test_carriers_inhouse_limits_vcf_missing_inhouse_record(self):
        self._setup_additional_variant_with_missing_inhouse_record()
        self.run_query(
            CaseExportVcfQuery,
            {
                "inhouse_enabled": True,
                "inhouse_carriers": 4,
                "inhouse_homozygous": None,
                "inhouse_heterozygous": None,
            },
            3,
        )

    def test_homozygous_thousand_genomes_limits_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {
                "thousand_genomes_enabled": True,
                "thousand_genomes_frequency": None,
                "thousand_genomes_homozygous": 2,
                "thousand_genomes_heterozygous": None,
            },
            2,
        )

    def test_homozygous_thousand_genomes_limits_export(self):
        self.run_query(
            CaseExportTableQuery,
            {
                "thousand_genomes_enabled": True,
                "thousand_genomes_frequency": None,
                "thousand_genomes_homozygous": 2,
                "thousand_genomes_heterozygous": None,
            },
            2,
        )

    def test_homozygous_thousand_genomes_limits_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {
                "thousand_genomes_enabled": True,
                "thousand_genomes_frequency": None,
                "thousand_genomes_homozygous": 2,
                "thousand_genomes_heterozygous": None,
            },
            2,
        )

    def test_homozygous_exac_limits_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {
                "exac_enabled": True,
                "exac_frequency": None,
                "exac_homozygous": 2,
                "exac_heterozygous": None,
            },
            2,
        )

    def test_homozygous_exac_limits_export(self):
        self.run_query(
            CaseExportTableQuery,
            {
                "exac_enabled": True,
                "exac_frequency": None,
                "exac_homozygous": 2,
                "exac_heterozygous": None,
            },
            2,
        )

    def test_homozygous_exac_limits_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {
                "exac_enabled": True,
                "exac_frequency": None,
                "exac_homozygous": 2,
                "exac_heterozygous": None,
            },
            2,
        )

    def test_homozygous_gnomad_exomes_limits_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {
                "gnomad_exomes_enabled": True,
                "gnomad_exomes_frequency": None,
                "gnomad_exomes_homozygous": 2,
                "gnomad_exomes_heterozygous": None,
            },
            2,
        )

    def test_homozygous_gnomad_exomes_limits_export(self):
        self.run_query(
            CaseExportTableQuery,
            {
                "gnomad_exomes_enabled": True,
                "gnomad_exomes_frequency": None,
                "gnomad_exomes_homozygous": 2,
                "gnomad_exomes_heterozygous": None,
            },
            2,
        )

    def test_homozygous_gnomad_exomes_limits_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {
                "gnomad_exomes_enabled": True,
                "gnomad_exomes_frequency": None,
                "gnomad_exomes_homozygous": 2,
                "gnomad_exomes_heterozygous": None,
            },
            2,
        )

    def test_homozygous_gnomad_genomes_limits_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {
                "gnomad_genomes_enabled": True,
                "gnomad_genomes_frequency": None,
                "gnomad_genomes_homozygous": 2,
                "gnomad_genomes_heterozygous": None,
            },
            2,
        )

    def test_homozygous_gnomad_genomes_limits_export(self):
        self.run_query(
            CaseExportTableQuery,
            {
                "gnomad_genomes_enabled": True,
                "gnomad_genomes_frequency": None,
                "gnomad_genomes_homozygous": 2,
                "gnomad_genomes_heterozygous": None,
            },
            2,
        )

    def test_homozygous_gnomad_genomes_limits_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {
                "gnomad_genomes_enabled": True,
                "gnomad_genomes_frequency": None,
                "gnomad_genomes_homozygous": 2,
                "gnomad_genomes_heterozygous": None,
            },
            2,
        )

    def test_homozygous_inhouse_limits_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {
                "inhouse_enabled": True,
                "inhouse_carriers": None,
                "inhouse_homozygous": 2,
                "inhouse_heterozygous": None,
            },
            2,
        )

    def test_homozygous_inhouse_limits_export(self):
        self.run_query(
            CaseExportTableQuery,
            {
                "inhouse_enabled": True,
                "inhouse_carriers": None,
                "inhouse_homozygous": 2,
                "inhouse_heterozygous": None,
            },
            2,
        )

    def test_homozygous_inhouse_limits_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {
                "inhouse_enabled": True,
                "inhouse_carriers": None,
                "inhouse_homozygous": 2,
                "inhouse_heterozygous": None,
            },
            2,
        )

    def test_homozygous_inhouse_limits_filter_missing_inhouse_record(self):
        self._setup_additional_variant_with_missing_inhouse_record()
        self.run_query(
            CasePrefetchQuery,
            {
                "inhouse_enabled": True,
                "inhouse_carriers": None,
                "inhouse_homozygous": 2,
                "inhouse_heterozygous": None,
            },
            3,
        )

    def test_homozygous_inhouse_limits_export_missing_inhouse_record(self):
        self._setup_additional_variant_with_missing_inhouse_record()
        self.run_query(
            CaseExportTableQuery,
            {
                "inhouse_enabled": True,
                "inhouse_carriers": None,
                "inhouse_homozygous": 2,
                "inhouse_heterozygous": None,
            },
            3,
        )

    def test_homozygous_inhouse_limits_vcf_missing_inhouse_record(self):
        self._setup_additional_variant_with_missing_inhouse_record()
        self.run_query(
            CaseExportVcfQuery,
            {
                "inhouse_enabled": True,
                "inhouse_carriers": None,
                "inhouse_homozygous": 2,
                "inhouse_heterozygous": None,
            },
            3,
        )

    def test_heterozygous_thousand_genomes_limits_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {
                "thousand_genomes_enabled": True,
                "thousand_genomes_frequency": None,
                "thousand_genomes_homozygous": None,
                "thousand_genomes_heterozygous": 2,
            },
            2,
        )

    def test_heterozygous_thousand_genomes_limits_export(self):
        self.run_query(
            CaseExportTableQuery,
            {
                "thousand_genomes_enabled": True,
                "thousand_genomes_frequency": None,
                "thousand_genomes_homozygous": None,
                "thousand_genomes_heterozygous": 2,
            },
            2,
        )

    def test_heterozygous_thousand_genomes_limits_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {
                "thousand_genomes_enabled": True,
                "thousand_genomes_frequency": None,
                "thousand_genomes_homozygous": None,
                "thousand_genomes_heterozygous": 2,
            },
            2,
        )

    def test_heterozygous_exac_limits_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {
                "exac_enabled": True,
                "exac_frequency": None,
                "exac_homozygous": None,
                "exac_heterozygous": 2,
            },
            2,
        )

    def test_heterozygous_exac_limits_export(self):
        self.run_query(
            CaseExportTableQuery,
            {
                "exac_enabled": True,
                "exac_frequency": None,
                "exac_homozygous": None,
                "exac_heterozygous": 2,
            },
            2,
        )

    def test_heterozygous_exac_limits_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {
                "exac_enabled": True,
                "exac_frequency": None,
                "exac_homozygous": None,
                "exac_heterozygous": 2,
            },
            2,
        )

    def test_heterozygous_gnomad_exomes_limits_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {
                "gnomad_exomes_enabled": True,
                "gnomad_exomes_frequency": None,
                "gnomad_exomes_homozygous": None,
                "gnomad_exomes_heterozygous": 2,
            },
            2,
        )

    def test_heterozygous_gnomad_exomes_limits_export(self):
        self.run_query(
            CaseExportTableQuery,
            {
                "gnomad_exomes_enabled": True,
                "gnomad_exomes_frequency": None,
                "gnomad_exomes_homozygous": None,
                "gnomad_exomes_heterozygous": 2,
            },
            2,
        )

    def test_heterozygous_gnomad_exomes_limits_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {
                "gnomad_exomes_enabled": True,
                "gnomad_exomes_frequency": None,
                "gnomad_exomes_homozygous": None,
                "gnomad_exomes_heterozygous": 2,
            },
            2,
        )

    def test_heterozygous_inhouse_limits_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {
                "inhouse_enabled": True,
                "inhouse_carriers": None,
                "inhouse_homozygous": None,
                "inhouse_heterozygous": 2,
            },
            2,
        )

    def test_heterozygous_inhouse_limits_export(self):
        self.run_query(
            CaseExportTableQuery,
            {
                "inhouse_enabled": True,
                "inhouse_carriers": None,
                "inhouse_homozygous": None,
                "inhouse_heterozygous": 2,
            },
            2,
        )

    def test_heterozygous_inhouse_limits_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {
                "inhouse_enabled": True,
                "inhouse_carriers": None,
                "inhouse_homozygous": None,
                "inhouse_heterozygous": 2,
            },
            2,
        )

    def test_heterozygous_inhouse_limits_filter_missing_inhouse_record(self):
        self._setup_additional_variant_with_missing_inhouse_record()
        self.run_query(
            CasePrefetchQuery,
            {
                "inhouse_enabled": True,
                "inhouse_carriers": None,
                "inhouse_homozygous": None,
                "inhouse_heterozygous": 2,
            },
            3,
        )

    def test_heterozygous_inhouse_limits_export_missing_inhouse_record(self):
        self._setup_additional_variant_with_missing_inhouse_record()
        self.run_query(
            CaseExportTableQuery,
            {
                "inhouse_enabled": True,
                "inhouse_carriers": None,
                "inhouse_homozygous": None,
                "inhouse_heterozygous": 2,
            },
            3,
        )

    def test_heterozygous_inhouse_limits_vcf_missing_inhouse_record(self):
        self._setup_additional_variant_with_missing_inhouse_record()
        self.run_query(
            CaseExportVcfQuery,
            {
                "inhouse_enabled": True,
                "inhouse_carriers": None,
                "inhouse_homozygous": None,
                "inhouse_heterozygous": 2,
            },
            3,
        )


class TestCaseOneQueryMitochondrialFrequency(SupportQueryTestBase):
    """Test switch for all four frequency filters + frequency limits + homozygous limits

    Each limit is tested for lower, critical and higher values. The data is designed
    to cover this with one test function rather than having three test functions for this
    setting. 'None' is tested within the switch or the other function. This is the value
    when no value in the interface was entered.

    tested databases:
    - mtdb, helixmtdb, mitomap
    """

    def setUp(self):
        """Create a case and 3 variants with different frequencies and count values and
        a corresponding variantsummary entry.
        """
        super().setUp()
        self.variant_set = SmallVariantSetFactory()
        for i in range(3):
            # this emulates 0.001, 0.01 and 0.1 frequency
            freq = 1 / 10 ** (3 - i)
            # this emulates increasing count starting from 1
            count = i + 1
            small_var = SmallVariantFactory(
                chromosome="MT", chromosome_no=25, variant_set=self.variant_set,
            )
            coords = {
                "chromosome": small_var.chromosome,
                "start": small_var.start,
                "end": small_var.end,
                "reference": small_var.reference,
                "alternative": small_var.alternative,
            }
            MitomapFactory(**coords, ac=count, af=freq)
            MtDbFactory(**coords, ac=count, af=freq)
            HelixMtDbFactory(**coords, ac_hom=count, ac_het=count, af=freq)

    def test_frequency_filters_disabled_filter(self):
        self.run_query(CasePrefetchQuery, {}, 3)

    def test_frequency_filters_disabled_export(self):
        self.run_query(CaseExportTableQuery, {}, 3)

    def test_frequency_filters_disabled_vcf(self):
        self.run_query(CaseExportVcfQuery, {}, 3)

    def test_frequency_mtdb_enabled_filter(self):
        self.run_query(CasePrefetchQuery, {"mtdb_enabled": True}, 0)

    def test_frequency_mtdb_enabled_export(self):
        self.run_query(CaseExportTableQuery, {"mtdb_enabled": True}, 0)

    def test_frequency_mtdb_enabled_vcf(self):
        self.run_query(CaseExportVcfQuery, {"mtdb_enabled": True}, 0)

    def test_frequency_helixmtdb_enabled_filter(self):
        self.run_query(CasePrefetchQuery, {"helixmtdb_enabled": True}, 0)

    def test_frequency_helixmtdb_enabled_export(self):
        self.run_query(CaseExportTableQuery, {"helixmtdb_enabled": True}, 0)

    def test_frequency_helixmtdb_enabled_vcf(self):
        self.run_query(CaseExportVcfQuery, {"helixmtdb_enabled": True}, 0)

    def test_frequency_mitomap_enabled_filter(self):
        self.run_query(CasePrefetchQuery, {"mitomap_enabled": True}, 0)

    def test_frequency_mitomap_enabled_export(self):
        self.run_query(CaseExportTableQuery, {"mitomap_enabled": True}, 0)

    def test_frequency_mitomap_enabled_vcf(self):
        self.run_query(CaseExportVcfQuery, {"mitomap_enabled": True}, 0)

    def test_frequency_mtdb_limits_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {"mtdb_enabled": True, "mtdb_frequency": 0.01, "mtdb_count": None,},
            2,
        )

    def test_frequency_mtdb_limits_export(self):
        self.run_query(
            CaseExportTableQuery,
            {"mtdb_enabled": True, "mtdb_frequency": 0.01, "mtdb_count": None,},
            2,
        )

    def test_frequency_mtdb_limits_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {"mtdb_enabled": True, "mtdb_frequency": 0.01, "mtdb_count": None,},
            2,
        )

    def test_frequency_helixmtdb_limits_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {
                "helixmtdb_enabled": True,
                "helixmtdb_frequency": 0.01,
                "helixmtdb_hom_count": None,
                "helixmtdb_het_count": None,
            },
            2,
        )

    def test_frequency_helixmtdb_limits_export(self):
        self.run_query(
            CaseExportTableQuery,
            {
                "helixmtdb_enabled": True,
                "helixmtdb_frequency": 0.01,
                "helixmtdb_hom_count": None,
                "helixmtdb_het_count": None,
            },
            2,
        )

    def test_frequency_helixmtdb_limits_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {
                "helixmtdb_enabled": True,
                "helixmtdb_frequency": 0.01,
                "helixmtdb_hom_count": None,
                "helixmtdb_het_count": None,
            },
            2,
        )

    def test_frequency_mitomap_limits_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {"mitomap_enabled": True, "mitomap_frequency": 0.01, "mitomap_count": None,},
            2,
        )

    def test_frequency_mitomap_limits_export(self):
        self.run_query(
            CaseExportTableQuery,
            {"mitomap_enabled": True, "mitomap_frequency": 0.01, "mitomap_count": None,},
            2,
        )

    def test_frequency_mitomap_limits_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {"mitomap_enabled": True, "mitomap_frequency": 0.01, "mitomap_count": None,},
            2,
        )

    def test_count_mtdb_limits_filter(self):
        self.run_query(
            CasePrefetchQuery, {"mtdb_enabled": True, "mtdb_frequency": None, "mtdb_count": 2,}, 2,
        )

    def test_count_mtdb_limits_export(self):
        self.run_query(
            CaseExportTableQuery,
            {"mtdb_enabled": True, "mtdb_frequency": None, "mtdb_count": 2,},
            2,
        )

    def test_count_mtdb_limits_vcf(self):
        self.run_query(
            CaseExportVcfQuery, {"mtdb_enabled": True, "mtdb_frequency": None, "mtdb_count": 2,}, 2,
        )

    def test_count_helixmtdb_het_limits_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {
                "helixmtdb_enabled": True,
                "helixmtdb_frequency": None,
                "helixmtdb_hom_count": None,
                "helixmtdb_het_count": 2,
            },
            2,
        )

    def test_count_helixmtdb_het_limits_export(self):
        self.run_query(
            CaseExportTableQuery,
            {
                "helixmtdb_enabled": True,
                "helixmtdb_frequency": None,
                "helixmtdb_hom_count": None,
                "helixmtdb_het_count": 2,
            },
            2,
        )

    def test_count_helixmtdb_het_limits_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {
                "helixmtdb_enabled": True,
                "helixmtdb_frequency": None,
                "helixmtdb_hom_count": None,
                "helixmtdb_het_count": 2,
            },
            2,
        )

    def test_count_helixmtdb_hom_limits_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {
                "helixmtdb_enabled": True,
                "helixmtdb_frequency": None,
                "helixmtdb_hom_count": 2,
                "helixmtdb_het_count": None,
            },
            2,
        )

    def test_count_helixmtdb_hom_limits_export(self):
        self.run_query(
            CaseExportTableQuery,
            {
                "helixmtdb_enabled": True,
                "helixmtdb_frequency": None,
                "helixmtdb_hom_count": 2,
                "helixmtdb_het_count": None,
            },
            2,
        )

    def test_count_helixmtdb_hom_limits_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {
                "helixmtdb_enabled": True,
                "helixmtdb_frequency": None,
                "helixmtdb_hom_count": 2,
                "helixmtdb_het_count": None,
            },
            2,
        )

    def test_count_mitomap_limits_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {"mitomap_enabled": True, "mitomap_frequency": None, "mitomap_count": 2,},
            2,
        )

    def test_count_mitomap_limits_export(self):
        self.run_query(
            CaseExportTableQuery,
            {"mitomap_enabled": True, "mitomap_frequency": None, "mitomap_count": 2,},
            2,
        )

    def test_count_mitomap_limits_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {"mitomap_enabled": True, "mitomap_frequency": None, "mitomap_count": 2,},
            2,
        )


class TestCaseOneQueryEffects(SupportQueryTestBase):
    """Test effects settings (just an excerpt. everything else would be madness."""

    def setUp(self):
        """Create one case and 3 variants with different variant effects for refseq transcripts."""
        super().setUp()
        variant_set = SmallVariantSetFactory()
        SmallVariantFactory(
            refseq_effect=["missense_variant", "stop_lost"], variant_set=variant_set
        )
        SmallVariantFactory(
            refseq_effect=["missense_variant", "frameshift_variant"], variant_set=variant_set
        )
        SmallVariantFactory(refseq_effect=["frameshift_variant"], variant_set=variant_set)

    def test_effects_none_filter(self):
        self.run_query(CasePrefetchQuery, {"effects": []}, 0)

    def test_effects_none_export(self):
        self.run_query(CaseExportTableQuery, {"effects": []}, 0)

    def test_effects_none_vcf(self):
        self.run_query(CaseExportVcfQuery, {"effects": []}, 0)

    def test_effects_one_filter(self):
        self.run_query(CasePrefetchQuery, {"effects": ["missense_variant"]}, 2)

    def test_effects_one_export(self):
        self.run_query(CaseExportTableQuery, {"effects": ["missense_variant"]}, 2)

    def test_effects_one_vcf(self):
        self.run_query(CaseExportVcfQuery, {"effects": ["missense_variant"]}, 2)

    def test_effects_two_filter(self):
        self.run_query(CasePrefetchQuery, {"effects": ["stop_lost", "frameshift_variant"]}, 3)

    def test_effects_two_export(self):
        self.run_query(CaseExportTableQuery, {"effects": ["stop_lost", "frameshift_variant"]}, 3)

    def test_effects_two_vcf(self):
        self.run_query(CaseExportVcfQuery, {"effects": ["stop_lost", "frameshift_variant"]}, 3)

    def test_effects_all_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {"effects": ["missense_variant", "stop_lost", "frameshift_variant"]},
            3,
        )

    def test_effects_all_export(self):
        self.run_query(
            CaseExportTableQuery,
            {"effects": ["missense_variant", "stop_lost", "frameshift_variant"]},
            3,
        )

    def test_effects_all_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {"effects": ["missense_variant", "stop_lost", "frameshift_variant"]},
            3,
        )


class TestCaseOneQueryExonDistance(SupportQueryTestBase):
    """Test exon distance settings"""

    def setUp(self):
        """Create one case and 3 variants with different exon distances (including empty field)."""
        super().setUp()
        variant_set = SmallVariantSetFactory()
        SmallVariantFactory(refseq_exon_dist=None, variant_set=variant_set)
        SmallVariantFactory(refseq_exon_dist=1, variant_set=variant_set)
        SmallVariantFactory(refseq_exon_dist=10, variant_set=variant_set)

    def test_exon_dist_none_filter(self):
        self.run_query(CasePrefetchQuery, {"max_exon_dist": 0}, 0)

    def test_exon_dist_none_export(self):
        self.run_query(CasePrefetchQuery, {"max_exon_dist": 0}, 0)

    def test_exon_dist_none_vcf(self):
        self.run_query(CasePrefetchQuery, {"max_exon_dist": 0}, 0)

    def test_exon_dist_one_filter(self):
        self.run_query(CasePrefetchQuery, {"max_exon_dist": 1}, 1)

    def test_exon_dist_one_export(self):
        self.run_query(CasePrefetchQuery, {"max_exon_dist": 1}, 1)

    def test_exon_dist_one_vcf(self):
        self.run_query(CasePrefetchQuery, {"max_exon_dist": 1}, 1)

    def test_exon_dist_two_filter(self):
        self.run_query(CasePrefetchQuery, {"max_exon_dist": 10}, 2)

    def test_exon_dist_two_export(self):
        self.run_query(CasePrefetchQuery, {"max_exon_dist": 10}, 2)

    def test_exon_dist_two_vcf(self):
        self.run_query(CasePrefetchQuery, {"max_exon_dist": 10}, 2)

    def test_exon_dist_all_filter(self):
        self.run_query(CasePrefetchQuery, {}, 3)

    def test_exon_dist_all_export(self):
        self.run_query(CasePrefetchQuery, {}, 3)

    def test_exon_dist_all_vcf(self):
        self.run_query(CasePrefetchQuery, {}, 3)


class TestCaseOneQueryTranscriptCoding(SupportQueryTestBase):
    def setUp(self):
        super().setUp()
        variant_set = SmallVariantSetFactory()
        SmallVariantFactory(
            refseq_transcript_coding=False, ensembl_transcript_coding=False, variant_set=variant_set
        )
        SmallVariantFactory(
            refseq_transcript_coding=True, ensembl_transcript_coding=True, variant_set=variant_set
        )

    def test_transcript_empty_refseq_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {
                "database_select": "refseq",
                "transcripts_coding": False,
                "transcripts_noncoding": False,
            },
            0,
        )

    def test_transcript_empty_refseq_export_table(self):
        self.run_query(
            CaseExportTableQuery,
            {
                "database_select": "refseq",
                "transcripts_coding": False,
                "transcripts_noncoding": False,
            },
            0,
        )

    def test_transcript_empty_refseq_export_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {
                "database_select": "refseq",
                "transcripts_coding": False,
                "transcripts_noncoding": False,
            },
            0,
        )

    def test_transcript_empty_ensembl_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {
                "database_select": "ensembl",
                "transcripts_coding": False,
                "transcripts_noncoding": False,
            },
            0,
        )

    def test_transcript_empty_ensembl_export_table(self):
        self.run_query(
            CaseExportTableQuery,
            {
                "database_select": "ensembl",
                "transcripts_coding": False,
                "transcripts_noncoding": False,
            },
            0,
        )

    def test_transcript_empty_ensembl_export_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {
                "database_select": "ensembl",
                "transcripts_coding": False,
                "transcripts_noncoding": False,
            },
            0,
        )

    def test_transcript_coding_refseq_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {
                "database_select": "refseq",
                "transcripts_coding": True,
                "transcripts_noncoding": False,
            },
            1,
        )

    def test_transcript_coding_refseq_export_table(self):
        self.run_query(
            CaseExportTableQuery,
            {
                "database_select": "refseq",
                "transcripts_coding": True,
                "transcripts_noncoding": False,
            },
            1,
        )

    def test_transcript_coding_refseq_export_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {
                "database_select": "refseq",
                "transcripts_coding": True,
                "transcripts_noncoding": False,
            },
            1,
        )

    def test_transcript_coding_ensembl_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {
                "database_select": "ensembl",
                "transcripts_coding": True,
                "transcripts_noncoding": False,
            },
            1,
        )

    def test_transcript_coding_ensembl_export_table(self):
        self.run_query(
            CaseExportTableQuery,
            {
                "database_select": "ensembl",
                "transcripts_coding": True,
                "transcripts_noncoding": False,
            },
            1,
        )

    def test_transcript_coding_ensembl_export_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {
                "database_select": "ensembl",
                "transcripts_coding": True,
                "transcripts_noncoding": False,
            },
            1,
        )

    def test_transcript_noncoding_refseq_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {
                "database_select": "refseq",
                "transcripts_coding": False,
                "transcripts_noncoding": True,
            },
            1,
        )

    def test_transcript_noncoding_refseq_export_table(self):
        self.run_query(
            CaseExportTableQuery,
            {
                "database_select": "refseq",
                "transcripts_coding": False,
                "transcripts_noncoding": True,
            },
            1,
        )

    def test_transcript_noncoding_refseq_export_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {
                "database_select": "refseq",
                "transcripts_coding": False,
                "transcripts_noncoding": True,
            },
            1,
        )

    def test_transcript_noncoding_ensembl_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {
                "database_select": "ensembl",
                "transcripts_coding": False,
                "transcripts_noncoding": True,
            },
            1,
        )

    def test_transcript_noncoding_ensembl_export_table(self):
        self.run_query(
            CaseExportTableQuery,
            {
                "database_select": "ensembl",
                "transcripts_coding": False,
                "transcripts_noncoding": True,
            },
            1,
        )

    def test_transcript_noncoding_ensembl_export_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {
                "database_select": "ensembl",
                "transcripts_coding": False,
                "transcripts_noncoding": True,
            },
            1,
        )

    def test_transcript_coding_and_noncoding_refseq_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {
                "database_select": "refseq",
                "transcripts_coding": True,
                "transcripts_noncoding": True,
            },
            2,
        )

    def test_transcript_coding_and_noncoding_refseq_export_table(self):
        self.run_query(
            CaseExportTableQuery,
            {
                "database_select": "refseq",
                "transcripts_coding": True,
                "transcripts_noncoding": True,
            },
            2,
        )

    def test_transcript_coding_and_noncoding_refseq_export_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {
                "database_select": "refseq",
                "transcripts_coding": True,
                "transcripts_noncoding": True,
            },
            2,
        )

    def test_transcript_coding_and_noncoding_ensembl_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {
                "database_select": "ensembl",
                "transcripts_coding": True,
                "transcripts_noncoding": True,
            },
            2,
        )

    def test_transcript_coding_and_noncoding_ensembl_export_table(self):
        self.run_query(
            CaseExportTableQuery,
            {
                "database_select": "ensembl",
                "transcripts_coding": True,
                "transcripts_noncoding": True,
            },
            2,
        )

    def test_transcript_coding_and_noncoding_ensembl_export_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {
                "database_select": "ensembl",
                "transcripts_coding": True,
                "transcripts_noncoding": True,
            },
            2,
        )


class TestCaseOneQueryGenotype(SupportQueryTestBase):
    """Test effects settings (just an excerpt. everything else would be madness."""

    def setUp(self):
        """Create case and 9 variants with different variant quality and genotype settings."""
        super().setUp()
        variant_set = SmallVariantSetFactory()
        case = variant_set.case
        self.patient = case.index
        SmallVariantFactory(
            genotype={self.patient: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"}},
            variant_set=variant_set,
        )
        SmallVariantFactory(
            genotype={self.patient: {"ad": 10, "dp": 30, "gq": 99, "gt": "0/0"}},
            variant_set=variant_set,
        )
        SmallVariantFactory(
            genotype={self.patient: {"ad": 30, "dp": 30, "gq": 99, "gt": "1/1"}},
            variant_set=variant_set,
        )
        SmallVariantFactory(
            genotype={self.patient: {"ad": 0, "dp": 10, "gq": 66, "gt": "./."}},
            variant_set=variant_set,
        )
        SmallVariantFactory(
            genotype={self.patient: {"ad": 15, "dp": 20, "gq": 33, "gt": "1/0"}},
            variant_set=variant_set,
        )
        SmallVariantFactory(
            genotype={self.patient: {"ad": 21, "dp": 30, "gq": 99, "gt": "0/1"}},
            variant_set=variant_set,
        )
        SmallVariantFactory(
            genotype={self.patient: {"ad": 9, "dp": 30, "gq": 99, "gt": "0/1"}},
            variant_set=variant_set,
        )
        SmallVariantFactory(
            genotype={self.patient: {"ad": 6, "dp": 30, "gq": 99, "gt": "0/1"}},
            variant_set=variant_set,
        )

    def test_genotype_gt_any_filter(self):
        self.run_query(CasePrefetchQuery, {"%s_gt" % self.patient: "any"}, 8)

    def test_genotype_gt_any_export(self):
        self.run_query(CaseExportTableQuery, {"%s_gt" % self.patient: "any"}, 8)

    def test_genotype_gt_any_vcf(self):
        self.run_query(CaseExportVcfQuery, {"%s_gt" % self.patient: "any"}, 8)

    def test_genotype_gt_ref_filter(self):
        self.run_query(CasePrefetchQuery, {"%s_gt" % self.patient: "ref"}, 1)

    def test_genotype_gt_ref_export(self):
        self.run_query(CaseExportTableQuery, {"%s_gt" % self.patient: "ref"}, 1)

    def test_genotype_gt_ref_vcf(self):
        self.run_query(CaseExportVcfQuery, {"%s_gt" % self.patient: "ref"}, 1)

    def test_genotype_gt_het_filter(self):
        self.run_query(CasePrefetchQuery, {"%s_gt" % self.patient: "het"}, 5)

    def test_genotype_gt_het_export(self):
        self.run_query(CaseExportTableQuery, {"%s_gt" % self.patient: "het"}, 5)

    def test_genotype_gt_het_vcf(self):
        self.run_query(CaseExportVcfQuery, {"%s_gt" % self.patient: "het"}, 5)

    def test_genotype_gt_hom_filter(self):
        self.run_query(CasePrefetchQuery, {"%s_gt" % self.patient: "hom"}, 1)

    def test_genotype_gt_hom_export(self):
        self.run_query(CaseExportTableQuery, {"%s_gt" % self.patient: "hom"}, 1)

    def test_genotype_gt_hom_vcf(self):
        self.run_query(CaseExportVcfQuery, {"%s_gt" % self.patient: "hom"}, 1)

    def test_genotype_gt_variant_filter(self):
        self.run_query(CasePrefetchQuery, {"%s_gt" % self.patient: "variant"}, 6)

    def test_genotype_gt_variant_export(self):
        self.run_query(CaseExportTableQuery, {"%s_gt" % self.patient: "variant"}, 6)

    def test_genotype_gt_variant_vcf(self):
        self.run_query(CaseExportVcfQuery, {"%s_gt" % self.patient: "variant"}, 6)

    def test_genotype_gt_non_variant_filter(self):
        self.run_query(CasePrefetchQuery, {"%s_gt" % self.patient: "non-variant"}, 2)

    def test_genotype_gt_non_variant_export(self):
        self.run_query(CaseExportTableQuery, {"%s_gt" % self.patient: "non-variant"}, 2)

    def test_genotype_gt_non_variant_vcf(self):
        self.run_query(CaseExportVcfQuery, {"%s_gt" % self.patient: "non-variant"}, 2)

    def test_genotype_gt_non_reference_filter(self):
        self.run_query(CasePrefetchQuery, {"%s_gt" % self.patient: "non-reference"}, 7)

    def test_genotype_gt_non_reference_export(self):
        self.run_query(CaseExportTableQuery, {"%s_gt" % self.patient: "non-reference"}, 7)

    def test_genotype_gt_non_reference_vcf(self):
        self.run_query(CaseExportVcfQuery, {"%s_gt" % self.patient: "non-reference"}, 7)

    def test_genotype_ad_limits_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {"%s_fail" % self.patient: "drop-variant", "%s_ad" % self.patient: 15},
            5,
        )

    def test_genotype_ad_limits_export(self):
        self.run_query(
            CaseExportTableQuery,
            {"%s_fail" % self.patient: "drop-variant", "%s_ad" % self.patient: 15},
            5,
        )

    def test_genotype_ad_limits_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {"%s_fail" % self.patient: "drop-variant", "%s_ad" % self.patient: 15},
            5,
        )

    def test_genotype_ad_max_limits_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {"%s_fail" % self.patient: "drop-variant", "%s_ad_max" % self.patient: 10},
            4,
        )
        self.run_query(
            CasePrefetchQuery,
            {"%s_fail" % self.patient: "drop-variant", "%s_ad_max" % self.patient: 9},
            3,
        )

    def test_genotype_ad_max_limits_export(self):
        self.run_query(
            CaseExportTableQuery,
            {"%s_fail" % self.patient: "drop-variant", "%s_ad_max" % self.patient: 10},
            4,
        )
        self.run_query(
            CaseExportTableQuery,
            {"%s_fail" % self.patient: "drop-variant", "%s_ad_max" % self.patient: 9},
            3,
        )

    def test_genotype_ad_max_limits_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {"%s_fail" % self.patient: "drop-variant", "%s_ad_max" % self.patient: 10},
            4,
        )
        self.run_query(
            CaseExportVcfQuery,
            {"%s_fail" % self.patient: "drop-variant", "%s_ad_max" % self.patient: 9},
            3,
        )

    def test_genotype_ab_limits_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {"%s_fail" % self.patient: "drop-variant", "%s_ab" % self.patient: 0.3},
            6,
        )

    def test_genotype_ab_limits_export(self):
        self.run_query(
            CaseExportTableQuery,
            {"%s_fail" % self.patient: "drop-variant", "%s_ab" % self.patient: 0.3},
            6,
        )

    def test_genotype_ab_limits_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {"%s_fail" % self.patient: "drop-variant", "%s_ab" % self.patient: 0.3},
            6,
        )

    def test_genotype_dp_het_limits_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {"%s_fail" % self.patient: "drop-variant", "%s_dp_het" % self.patient: 21},
            7,
        )
        self.run_query(
            CasePrefetchQuery,
            {"%s_fail" % self.patient: "drop-variant", "%s_dp_het" % self.patient: 20},
            8,
        )

    def test_genotype_dp_het_limits_export(self):
        self.run_query(
            CaseExportTableQuery,
            {"%s_fail" % self.patient: "drop-variant", "%s_dp_het" % self.patient: 21},
            7,
        )
        self.run_query(
            CaseExportTableQuery,
            {"%s_fail" % self.patient: "drop-variant", "%s_dp_het" % self.patient: 20},
            8,
        )

    def test_genotype_dp_het_limits_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {"%s_fail" % self.patient: "drop-variant", "%s_dp_het" % self.patient: 21},
            7,
        )
        self.run_query(
            CaseExportTableQuery,
            {"%s_fail" % self.patient: "drop-variant", "%s_dp_het" % self.patient: 20},
            8,
        )

    def test_genotype_dp_hom_limits_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {"%s_fail" % self.patient: "drop-variant", "%s_dp_hom" % self.patient: 31},
            6,
        )
        self.run_query(
            CasePrefetchQuery,
            {"%s_fail" % self.patient: "drop-variant", "%s_dp_hom" % self.patient: 30},
            8,
        )

    def test_genotype_dp_hom_limits_export(self):
        self.run_query(
            CaseExportTableQuery,
            {"%s_fail" % self.patient: "drop-variant", "%s_dp_hom" % self.patient: 31},
            6,
        )
        self.run_query(
            CaseExportTableQuery,
            {"%s_fail" % self.patient: "drop-variant", "%s_dp_hom" % self.patient: 30},
            8,
        )

    def test_genotype_dp_hom_limits_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {"%s_fail" % self.patient: "drop-variant", "%s_dp_hom" % self.patient: 31},
            6,
        )
        self.run_query(
            CaseExportTableQuery,
            {"%s_fail" % self.patient: "drop-variant", "%s_dp_hom" % self.patient: 30},
            8,
        )

    def test_genotype_gq_limits_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {"%s_fail" % self.patient: "drop-variant", "%s_gq" % self.patient: 66},
            7,
        )

    def test_genotype_gq_limits_export(self):
        self.run_query(
            CaseExportTableQuery,
            {"%s_fail" % self.patient: "drop-variant", "%s_gq" % self.patient: 66},
            7,
        )

    def test_genotype_gq_limits_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {"%s_fail" % self.patient: "drop-variant", "%s_gq" % self.patient: 66},
            7,
        )

    def test_genotype_fail_ignore_filter(self):
        self.run_query(CasePrefetchQuery, {"%s_fail" % self.patient: "ignore"}, 8)

    def test_genotype_fail_ignore_export(self):
        self.run_query(CaseExportTableQuery, {"%s_fail" % self.patient: "ignore"}, 8)

    def test_genotype_fail_ignore_vcf(self):
        self.run_query(CaseExportVcfQuery, {"%s_fail" % self.patient: "ignore"}, 8)

    def test_genotype_fail_drop_variant_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {
                "%s_fail" % self.patient: "drop-variant",
                "%s_dp" % self.patient: 20,
                "%s_ab" % self.patient: 0.3,
                "%s_gq" % self.patient: 20,
                "%s_ad" % self.patient: 15,
            },
            4,
        )

    def test_genotype_fail_drop_variant_export(self):
        self.run_query(
            CaseExportTableQuery,
            {
                "%s_fail" % self.patient: "drop-variant",
                "%s_dp" % self.patient: 20,
                "%s_ab" % self.patient: 0.3,
                "%s_gq" % self.patient: 20,
                "%s_ad" % self.patient: 15,
            },
            4,
        )

    def test_genotype_fail_drop_variant_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {
                "%s_fail" % self.patient: "drop-variant",
                "%s_dp" % self.patient: 20,
                "%s_ab" % self.patient: 0.3,
                "%s_gq" % self.patient: 20,
                "%s_ad" % self.patient: 15,
            },
            4,
        )

    def test_genotype_fail_no_call_filter(self):
        self.run_query(
            CasePrefetchQuery,
            {
                "%s_fail" % self.patient: "no-call",
                "%s_dp" % self.patient: 20,
                "%s_ab" % self.patient: 0.3,
                "%s_gq" % self.patient: 20,
                "%s_ad" % self.patient: 15,
                "%s_gt" % self.patient: "het",
            },
            6,
        )

    def test_genotype_fail_no_call_export(self):
        self.run_query(
            CaseExportTableQuery,
            {
                "%s_fail" % self.patient: "no-call",
                "%s_dp" % self.patient: 20,
                "%s_ab" % self.patient: 0.3,
                "%s_gq" % self.patient: 20,
                "%s_ad" % self.patient: 15,
                "%s_gt" % self.patient: "het",
            },
            6,
        )

    def test_genotype_fail_no_call_vcf(self):
        self.run_query(
            CaseExportVcfQuery,
            {
                "%s_fail" % self.patient: "no-call",
                "%s_dp" % self.patient: 20,
                "%s_ab" % self.patient: 0.3,
                "%s_gq" % self.patient: 20,
                "%s_ad" % self.patient: 15,
                "%s_gt" % self.patient: "het",
            },
            6,
        )


class TestCaseOneWhitelistBlacklistRegionFilterQuery(SupportQueryTestBase):
    """Test whitelist, blacklist and genomic region filter settings."""

    def setUp(self):
        """Generate a case, 3 genes and variants: gene i has i variants."""
        super().setUp()
        variant_set = SmallVariantSetFactory()
        case = variant_set.case
        self.hgncs = HgncFactory.create_batch(3)
        for i, hgnc in enumerate(self.hgncs):
            SmallVariantFactory.create_batch(
                i + 1,
                chromosome="1",
                start=(i + 1) * 100 + i,
                refseq_gene_id=hgnc.entrez_id,
                ensembl_gene_id=hgnc.ensembl_gene_id,
                variant_set=variant_set,
            )

    def test_blacklist_empty(self):
        self.run_query(CasePrefetchQuery, {"gene_blacklist": []}, 6)

    def test_blacklist_empty_export(self):
        self.run_query(CaseExportTableQuery, {"gene_blacklist": []}, 6)

    def test_blacklist_empty_vcf(self):
        self.run_query(CaseExportVcfQuery, {"gene_blacklist": []}, 6)

    def test_blacklist_one_filter(self):
        self.run_query(CasePrefetchQuery, {"gene_blacklist": [self.hgncs[0].symbol]}, 5)

    def test_blacklist_one_export(self):
        self.run_query(CaseExportTableQuery, {"gene_blacklist": [self.hgncs[0].symbol]}, 5)

    def test_blacklist_one_vcf(self):
        self.run_query(CaseExportVcfQuery, {"gene_blacklist": [self.hgncs[0].symbol]}, 5)

    def test_blacklist_two_filter(self):
        self.run_query(
            CasePrefetchQuery, {"gene_blacklist": [hgnc.symbol for hgnc in self.hgncs[:2]]}, 3
        )

    def test_blacklist_two_export(self):
        self.run_query(
            CaseExportTableQuery, {"gene_blacklist": [hgnc.symbol for hgnc in self.hgncs[:2]]}, 3
        )

    def test_blacklist_two_vcf(self):
        self.run_query(
            CaseExportVcfQuery, {"gene_blacklist": [hgnc.symbol for hgnc in self.hgncs[:2]]}, 3
        )

    def test_blacklist_all_filter(self):
        self.run_query(
            CasePrefetchQuery, {"gene_blacklist": [hgnc.symbol for hgnc in self.hgncs]}, 0
        )

    def test_blacklist_all_export(self):
        self.run_query(
            CaseExportTableQuery, {"gene_blacklist": [hgnc.symbol for hgnc in self.hgncs]}, 0
        )

    def test_blacklist_all_vcf(self):
        self.run_query(
            CaseExportVcfQuery, {"gene_blacklist": [hgnc.symbol for hgnc in self.hgncs]}, 0
        )

    def test_whitelist_empty(self):
        self.run_query(CasePrefetchQuery, {"gene_whitelist": []}, 6)

    def test_whitelist_empty_export(self):
        self.run_query(CaseExportTableQuery, {"gene_whitelist": []}, 6)

    def test_whitelist_empty_vcf(self):
        self.run_query(CaseExportVcfQuery, {"gene_whitelist": []}, 6)

    def test_whitelist_one_filter(self):
        self.run_query(CasePrefetchQuery, {"gene_whitelist": [self.hgncs[0].symbol]}, 1)

    def test_whitelist_one_export(self):
        self.run_query(CaseExportTableQuery, {"gene_whitelist": [self.hgncs[0].symbol]}, 1)

    def test_whitelist_one_vcf(self):
        self.run_query(CaseExportVcfQuery, {"gene_whitelist": [self.hgncs[0].symbol]}, 1)

    def test_whitelist_two_filter(self):
        self.run_query(
            CasePrefetchQuery, {"gene_whitelist": [hgnc.symbol for hgnc in self.hgncs[:2]]}, 3
        )

    def test_whitelist_two_export(self):
        self.run_query(
            CaseExportTableQuery, {"gene_whitelist": [hgnc.symbol for hgnc in self.hgncs[:2]]}, 3
        )

    def test_whitelist_two_vcf(self):
        self.run_query(
            CaseExportVcfQuery, {"gene_whitelist": [hgnc.symbol for hgnc in self.hgncs[:2]]}, 3
        )

    def test_whitelist_all_filter(self):
        self.run_query(
            CasePrefetchQuery, {"gene_whitelist": [hgnc.symbol for hgnc in self.hgncs]}, 6
        )

    def test_whitelist_all_export(self):
        self.run_query(
            CaseExportTableQuery, {"gene_whitelist": [hgnc.symbol for hgnc in self.hgncs]}, 6
        )

    def test_whitelist_all_vcf(self):
        self.run_query(
            CaseExportVcfQuery, {"gene_whitelist": [hgnc.symbol for hgnc in self.hgncs]}, 6
        )

    def test_genomic_region_empty_filter(self):
        self.run_query(CasePrefetchQuery, {"genomic_region": []}, 6)

    def test_genomic_region_empty_export(self):
        self.run_query(CaseExportTableQuery, {"genomic_region": []}, 6)

    def test_genomic_region_empty_vcf(self):
        self.run_query(CaseExportVcfQuery, {"genomic_region": []}, 6)

    def test_genomic_region_one_region_filter(self):
        self.run_query(CasePrefetchQuery, {"genomic_region": [("1", 1, 199)]}, 1)

    def test_genomic_region_one_region_export(self):
        self.run_query(CaseExportTableQuery, {"genomic_region": [("1", 1, 199)]}, 1)

    def test_genomic_region_one_region_vcf(self):
        self.run_query(CaseExportVcfQuery, {"genomic_region": [("1", 1, 199)]}, 1)

    def test_genomic_region_two_regions_filter(self):
        self.run_query(CasePrefetchQuery, {"genomic_region": [("1", 1, 199), ("1", 300, 399)]}, 4)

    def test_genomic_region_two_regions_export(self):
        self.run_query(
            CaseExportTableQuery, {"genomic_region": [("1", 1, 199), ("1", 300, 399)]}, 4
        )

    def test_genomic_region_two_regions_vcf(self):
        self.run_query(CaseExportVcfQuery, {"genomic_region": [("1", 1, 199), ("1", 300, 399)]}, 4)

    def test_genomic_region_only_chromosome(self):
        self.run_query(CasePrefetchQuery, {"genomic_region": [("1", 0, 2 ** 31 - 1)]}, 6)


# ---------------------------------------------------------------------------
# Tests for Case 2
# ---------------------------------------------------------------------------

# Case 2 is a trio with affected child and unaffected parents. We test that
# the query works for the dominant (de novo), homozygous recessive, and
# compound heterozygous recessive.


class TestCaseTwoDominantQuery(SupportQueryTestBase):
    """Test the queries for dominant/de novo hypothesis"""

    def setUp(self):
        """Create a trio case with 4 variants."""
        super().setUp()
        self.variant_set = SmallVariantSetFactory(case__structure="trio")
        self.case = self.variant_set.case
        self.small_vars = [
            SmallVariantFactory(
                chromosome="1",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                },
                variant_set=self.variant_set,
            ),
            SmallVariantFactory(
                chromosome="1",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "1/1"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                },
                variant_set=self.variant_set,
            ),
            SmallVariantFactory(
                chromosome="1",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                },
                variant_set=self.variant_set,
            ),
            SmallVariantFactory(
                chromosome="1",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                },
                variant_set=self.variant_set,
            ),
        ]

    def test_query_de_novo_filter(self):
        res = self.run_query(
            CasePrefetchQuery,
            {
                "%s_gt" % self.case.pedigree[0]["patient"]: "het",
                "%s_gt" % self.case.pedigree[0]["father"]: "ref",
                "%s_gt" % self.case.pedigree[0]["mother"]: "ref",
            },
            1,
        )
        self.assertEqual(res[0].start, self.small_vars[0].start)

    def test_query_de_novo_export_table(self):
        res = self.run_query(
            CaseExportTableQuery,
            {
                "%s_gt" % self.case.pedigree[0]["patient"]: "het",
                "%s_gt" % self.case.pedigree[0]["father"]: "ref",
                "%s_gt" % self.case.pedigree[0]["mother"]: "ref",
            },
            1,
        )
        self.assertEqual(res[0].start, self.small_vars[0].start)

    def test_query_de_novo_export_vcf(self):
        res = self.run_query(
            CaseExportVcfQuery,
            {
                "%s_gt" % self.case.pedigree[0]["patient"]: "het",
                "%s_gt" % self.case.pedigree[0]["father"]: "ref",
                "%s_gt" % self.case.pedigree[0]["mother"]: "ref",
            },
            1,
        )
        self.assertEqual(res[0].start, self.small_vars[0].start)


class TestCaseTwoRecessiveHomozygousQuery(SupportQueryTestBase):
    """Test the queries for recessive homozygous hypothesis"""

    def setUp(self):
        """Create a trio case with 4 variants."""
        super().setUp()
        self.variant_set = SmallVariantSetFactory(case__structure="trio")
        self.case = self.variant_set.case
        self.small_vars = [
            SmallVariantFactory(
                chromosome="1",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                },
                variant_set=self.variant_set,
            ),
            SmallVariantFactory(
                chromosome="1",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "1/1"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                },
                variant_set=self.variant_set,
            ),
            SmallVariantFactory(
                chromosome="1",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                },
                variant_set=self.variant_set,
            ),
            SmallVariantFactory(
                chromosome="1",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                },
                variant_set=self.variant_set,
            ),
        ]

    def test_query_recessive_hom_filter(self):
        res = self.run_query(
            CasePrefetchQuery,
            {
                "%s_gt" % self.case.pedigree[0]["patient"]: "hom",
                "%s_gt" % self.case.pedigree[0]["father"]: "het",
                "%s_gt" % self.case.pedigree[0]["mother"]: "het",
            },
            1,
        )
        self.assertEqual(res[0].start, self.small_vars[1].start)

    def test_query_recessive_hom_export_table(self):
        res = self.run_query(
            CaseExportTableQuery,
            {
                "%s_gt" % self.case.pedigree[0]["patient"]: "hom",
                "%s_gt" % self.case.pedigree[0]["father"]: "het",
                "%s_gt" % self.case.pedigree[0]["mother"]: "het",
            },
            1,
        )
        self.assertEqual(res[0].start, self.small_vars[1].start)

    def test_query_recessive_hom_export_vcf(self):
        res = self.run_query(
            CaseExportVcfQuery,
            {
                "%s_gt" % self.case.pedigree[0]["patient"]: "hom",
                "%s_gt" % self.case.pedigree[0]["father"]: "het",
                "%s_gt" % self.case.pedigree[0]["mother"]: "het",
            },
            1,
        )
        self.assertEqual(res[0].start, self.small_vars[1].start)


class TestCaseTwoCompHetQuery(SupportQueryTestBase):
    """Test the queries for compound recessive heterozygous hypothesis"""

    def setUp(self):
        """Create a trio case with 4 variants and make sure the coordinates in the same gene are on the same chromosome."""
        super().setUp()
        self.variant_set = SmallVariantSetFactory(case__structure="trio")
        self.case = self.variant_set.case
        self.small_vars = [
            SmallVariantFactory(
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                },
                ensembl_gene_id="ENSG1",
                variant_set=self.variant_set,
            ),
            SmallVariantFactory(
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "1/1"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                },
                refseq_gene_id="2",
                ensembl_gene_id="ENSG2",
                variant_set=self.variant_set,
            ),
            SmallVariantFactory(
                chromosome="3",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                },
                refseq_gene_id="3",
                ensembl_gene_id="ENSG3",
                variant_set=self.variant_set,
            ),
            SmallVariantFactory(
                chromosome="3",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                },
                variant_set=self.variant_set,
                refseq_gene_id="3",
                ensembl_gene_id="ENSG3",
            ),
        ]

    def test_query_compound_het_prefetch_filter(self):
        res = self.run_query(
            CasePrefetchQuery,
            {"compound_recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            2,
        )
        self.assertEqual(res[0].start, self.small_vars[2].start)
        self.assertEqual(res[1].start, self.small_vars[3].start)

    def test_query_compound_het_export_tsv(self):
        res = self.run_query(
            CaseExportTableQuery,
            {"compound_recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            2,
        )
        self.assertEqual(res[0].start, self.small_vars[2].start)
        self.assertEqual(res[1].start, self.small_vars[3].start)

    def test_query_compound_het_export_vcf(self):
        res = self.run_query(
            CaseExportVcfQuery,
            {"compound_recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            2,
        )
        self.assertEqual(res[0].start, self.small_vars[2].start)
        self.assertEqual(res[1].start, self.small_vars[3].start)

    def test_query_compound_het_load_prefetched_filter(self):
        # Generate results
        res = self.run_query(
            CasePrefetchQuery,
            {"compound_recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            2,
        )
        # Add results to variant query
        query = SmallVariantQueryFactory(case=self.case)
        query.query_results.add(*[r.id for r in res])
        # Load Prefetched results
        res = self.run_query(
            CaseLoadPrefetchedQuery,
            {
                "compound_recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]},
                "filter_job_id": query.id,
            },
            2,
        )
        self.assertEqual(res[0].start, self.small_vars[2].start)
        self.assertEqual(res[1].start, self.small_vars[3].start)


class TestCaseTwoCompHetQuartetQuery(SupportQueryTestBase):
    """Test the queries for compound recessive heterozygous hypothesis with siblings."""

    def setUp(self):
        """Create a quartet case with 4 variants and make sure the coordinates in the same gene are on the same chromosome."""
        super().setUp()
        self.variant_set = SmallVariantSetFactory(case__structure="quartet")
        self.case = self.variant_set.case
        self.small_vars = [
            SmallVariantFactory(
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[1]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                },
                ensembl_gene_id="ENSG1",
                variant_set=self.variant_set,
            ),
            SmallVariantFactory(
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "1/1"},
                    self.case.pedigree[1]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "1/1"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                },
                refseq_gene_id="2",
                ensembl_gene_id="ENSG2",
                variant_set=self.variant_set,
            ),
            SmallVariantFactory(
                chromosome="3",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[1]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                },
                refseq_gene_id="3",
                ensembl_gene_id="ENSG3",
                variant_set=self.variant_set,
            ),
            SmallVariantFactory(
                chromosome="3",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[1]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                },
                variant_set=self.variant_set,
                refseq_gene_id="3",
                ensembl_gene_id="ENSG3",
            ),
            SmallVariantFactory(
                chromosome="4",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case.pedigree[1]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                },
                refseq_gene_id="4",
                ensembl_gene_id="ENSG4",
                variant_set=self.variant_set,
            ),
            SmallVariantFactory(
                chromosome="4",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case.pedigree[1]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                },
                variant_set=self.variant_set,
                refseq_gene_id="4",
                ensembl_gene_id="ENSG4",
            ),
        ]

    def test_query_index_compound_het_prefetch_filter(self):
        res = self.run_query(
            CasePrefetchQuery,
            {"compound_recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            2,
        )
        self.assertEqual(res[0].start, self.small_vars[2].start)
        self.assertEqual(res[1].start, self.small_vars[3].start)

    def test_query_index_compound_het_prefetch_export_tsv(self):
        res = self.run_query(
            CaseExportTableQuery,
            {"compound_recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            2,
        )
        self.assertEqual(res[0].start, self.small_vars[2].start)
        self.assertEqual(res[1].start, self.small_vars[3].start)

    def test_query_index_compound_het_prefetch_export_vcf(self):
        res = self.run_query(
            CaseExportVcfQuery,
            {"compound_recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            2,
        )
        self.assertEqual(res[0].start, self.small_vars[2].start)
        self.assertEqual(res[1].start, self.small_vars[3].start)

    def test_query_index_compound_het_load_prefetched_filter(self):
        # Generate results
        res = self.run_query(
            CasePrefetchQuery,
            {"compound_recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            2,
        )
        # Add results to variant query
        query = SmallVariantQueryFactory(case=self.case)
        query.query_results.add(*[r.id for r in res])
        # Load Prefetched results
        res = self.run_query(
            CaseLoadPrefetchedQuery,
            {
                "compound_recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]},
                "filter_job_id": query.id,
            },
            2,
        )
        self.assertEqual(res[0].start, self.small_vars[2].start)
        self.assertEqual(res[1].start, self.small_vars[3].start)

    def test_query_sibling_compound_het_prefetch_filter(self):
        res = self.run_query(
            CasePrefetchQuery,
            {"compound_recessive_indices": {self.case.name: self.case.pedigree[1]["patient"]}},
            2,
        )
        self.assertEqual(res[0].start, self.small_vars[4].start)
        self.assertEqual(res[1].start, self.small_vars[5].start)

    def test_query_sibling_compound_het_prefetch_export_tsv(self):
        res = self.run_query(
            CaseExportTableQuery,
            {"compound_recessive_indices": {self.case.name: self.case.pedigree[1]["patient"]}},
            2,
        )
        self.assertEqual(res[0].start, self.small_vars[4].start)
        self.assertEqual(res[1].start, self.small_vars[5].start)

    def test_query_sibling_compound_het_prefetch_export_vcf(self):
        res = self.run_query(
            CaseExportVcfQuery,
            {"compound_recessive_indices": {self.case.name: self.case.pedigree[1]["patient"]}},
            2,
        )
        self.assertEqual(res[0].start, self.small_vars[4].start)
        self.assertEqual(res[1].start, self.small_vars[5].start)

    def test_query_sibling_compound_het_load_prefetched_filter(self):
        # Generate results
        res = self.run_query(
            CasePrefetchQuery,
            {"compound_recessive_indices": {self.case.name: self.case.pedigree[1]["patient"]}},
            2,
        )
        # Add results to variant query
        query = SmallVariantQueryFactory(case=self.case)
        query.query_results.add(*[r.id for r in res])
        # Load Prefetched results
        res = self.run_query(
            CaseLoadPrefetchedQuery,
            {
                "compound_recessive_indices": {self.case.name: self.case.pedigree[1]["patient"]},
                "filter_job_id": query.id,
            },
            2,
        )
        self.assertEqual(res[0].start, self.small_vars[4].start)
        self.assertEqual(res[1].start, self.small_vars[5].start)


class TestCaseTwoCompHetQuintetQuery(SupportQueryTestBase):
    """Test the queries for compound recessive heterozygous hypothesis with grandparents."""

    def setUp(self):
        """Create a quartet case with 4 variants and make sure the coordinates in the same gene are on the same chromosome."""
        super().setUp()
        self.variant_set = SmallVariantSetFactory(case__structure="quintet")
        self.case = self.variant_set.case
        self.small_vars = [
            SmallVariantFactory(
                chromosome="3",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    # self.case.pedigree[1]["patient"] is self.case.pedigree[0]["father"]
                    self.case.pedigree[1]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case.pedigree[1]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                },
                refseq_gene_id="3",
                ensembl_gene_id="ENSG3",
                variant_set=self.variant_set,
            ),
            SmallVariantFactory(
                chromosome="3",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    # self.case.pedigree[1]["patient"] is self.case.pedigree[0]["father"]
                    self.case.pedigree[1]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case.pedigree[1]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                },
                variant_set=self.variant_set,
                refseq_gene_id="3",
                ensembl_gene_id="ENSG3",
            ),
            SmallVariantFactory(
                chromosome="4",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    # self.case.pedigree[1]["patient"] is self.case.pedigree[0]["father"]
                    self.case.pedigree[1]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case.pedigree[1]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                },
                refseq_gene_id="4",
                ensembl_gene_id="ENSG4",
                variant_set=self.variant_set,
            ),
            SmallVariantFactory(
                chromosome="4",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    # self.case.pedigree[1]["patient"] is self.case.pedigree[0]["father"]
                    self.case.pedigree[1]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[1]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                },
                variant_set=self.variant_set,
                refseq_gene_id="4",
                ensembl_gene_id="ENSG4",
            ),
        ]

    def test_query_index_compound_het_prefetch_filter(self):
        res = self.run_query(
            CasePrefetchQuery,
            {"compound_recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            2,
        )
        self.assertEqual(res[0].start, self.small_vars[0].start)
        self.assertEqual(res[1].start, self.small_vars[1].start)

    def test_query_index_compound_het_prefetch_export_tsv(self):
        res = self.run_query(
            CaseExportTableQuery,
            {"compound_recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            2,
        )
        self.assertEqual(res[0].start, self.small_vars[0].start)
        self.assertEqual(res[1].start, self.small_vars[1].start)

    def test_query_index_compound_het_prefetch_export_vcf(self):
        res = self.run_query(
            CaseExportVcfQuery,
            {"compound_recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            2,
        )
        self.assertEqual(res[0].start, self.small_vars[0].start)
        self.assertEqual(res[1].start, self.small_vars[1].start)

    def test_query_index_compound_het_load_prefetched_filter(self):
        # Generate results
        res = self.run_query(
            CasePrefetchQuery,
            {"compound_recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            2,
        )
        # Add results to variant query
        query = SmallVariantQueryFactory(case=self.case)
        query.query_results.add(*[r.id for r in res])
        # Load Prefetched results
        res = self.run_query(
            CaseLoadPrefetchedQuery,
            {
                "compound_recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]},
                "filter_job_id": query.id,
            },
            2,
        )
        self.assertEqual(res[0].start, self.small_vars[0].start)
        self.assertEqual(res[1].start, self.small_vars[1].start)

    def test_query_father_compound_het_prefetch_filter(self):
        res = self.run_query(
            CasePrefetchQuery,
            {"compound_recessive_indices": {self.case.name: self.case.pedigree[1]["patient"]}},
            2,
        )
        self.assertEqual(res[0].start, self.small_vars[2].start)
        self.assertEqual(res[1].start, self.small_vars[3].start)

    def test_query_father_compound_het_prefetch_export_tsv(self):
        res = self.run_query(
            CaseExportTableQuery,
            {"compound_recessive_indices": {self.case.name: self.case.pedigree[1]["patient"]}},
            2,
        )
        self.assertEqual(res[0].start, self.small_vars[2].start)
        self.assertEqual(res[1].start, self.small_vars[3].start)

    def test_query_father_compound_het_prefetch_export_vcf(self):
        res = self.run_query(
            CaseExportVcfQuery,
            {"compound_recessive_indices": {self.case.name: self.case.pedigree[1]["patient"]}},
            2,
        )
        self.assertEqual(res[0].start, self.small_vars[2].start)
        self.assertEqual(res[1].start, self.small_vars[3].start)

    def test_query_father_compound_het_load_prefetched_filter(self):
        # Generate results
        res = self.run_query(
            CasePrefetchQuery,
            {"compound_recessive_indices": {self.case.name: self.case.pedigree[1]["patient"]}},
            2,
        )
        # Add results to variant query
        query = SmallVariantQueryFactory(case=self.case)
        query.query_results.add(*[r.id for r in res])
        # Load Prefetched results
        res = self.run_query(
            CaseLoadPrefetchedQuery,
            {
                "compound_recessive_indices": {self.case.name: self.case.pedigree[1]["patient"]},
                "filter_job_id": query.id,
            },
            2,
        )
        self.assertEqual(res[0].start, self.small_vars[2].start)
        self.assertEqual(res[1].start, self.small_vars[3].start)


class TestCaseTwoCompHetOneParentQuery(SupportQueryTestBase):
    """Test the queries for compound recessive heterozygous hypothesis"""

    def setUp(self):
        """Create an index + parent case with 4 variants and make sure the coordinates in the same gene are on the same chromosome."""
        super().setUp()
        self.variant_set = SmallVariantSetFactory(case__structure="duo")
        self.case = self.variant_set.case
        self.small_vars = [
            SmallVariantFactory(
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                },
                ensembl_gene_id="ENSG1",
                variant_set=self.variant_set,
            ),
            SmallVariantFactory(
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "1/1"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                },
                refseq_gene_id="2",
                ensembl_gene_id="ENSG2",
                variant_set=self.variant_set,
            ),
            SmallVariantFactory(
                chromosome="3",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                },
                refseq_gene_id="3",
                ensembl_gene_id="ENSG3",
                variant_set=self.variant_set,
            ),
            SmallVariantFactory(
                chromosome="3",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                },
                variant_set=self.variant_set,
                refseq_gene_id="3",
                ensembl_gene_id="ENSG3",
            ),
        ]

    def test_query_compound_het_prefetch_filter(self):
        res = self.run_query(
            CasePrefetchQuery,
            {"compound_recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            2,
        )
        self.assertEqual(res[0].start, self.small_vars[2].start)
        self.assertEqual(res[1].start, self.small_vars[3].start)

    def test_query_compound_het_export_tsv(self):
        res = self.run_query(
            CaseExportTableQuery,
            {"compound_recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            2,
        )
        self.assertEqual(res[0].start, self.small_vars[2].start)
        self.assertEqual(res[1].start, self.small_vars[3].start)

    def test_query_compound_het_export_vcf(self):
        res = self.run_query(
            CaseExportVcfQuery,
            {"compound_recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            2,
        )
        self.assertEqual(res[0].start, self.small_vars[2].start)
        self.assertEqual(res[1].start, self.small_vars[3].start)

    def test_query_compound_het_load_prefetched_filter(self):
        # Generate results
        res = self.run_query(
            CasePrefetchQuery,
            {"compound_recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            2,
        )
        # Add results to variant query
        query = SmallVariantQueryFactory(case=self.case)
        query.query_results.add(*[r.id for r in res])
        # Load Prefetched results
        res = self.run_query(
            CaseLoadPrefetchedQuery,
            {
                "compound_recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]},
                "filter_job_id": query.id,
            },
            2,
        )
        self.assertEqual(res[0].start, self.small_vars[2].start)
        self.assertEqual(res[1].start, self.small_vars[3].start)


class TestCaseTwoCompHetSingletonQuery(SupportQueryTestBase):
    """Test the queries for compound recessive heterozygous hypothesis"""

    def setUp(self):
        """Create a singleton case with 4 variants and make sure the coordinates in the same gene are on the same chromosome."""
        super().setUp()
        self.variant_set = SmallVariantSetFactory(case__structure="singleton")
        self.case = self.variant_set.case
        self.small_vars = [
            SmallVariantFactory(
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"}
                },
                ensembl_gene_id="ENSG1",
                variant_set=self.variant_set,
            ),
            SmallVariantFactory(
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "1/1"}
                },
                refseq_gene_id="2",
                ensembl_gene_id="ENSG2",
                variant_set=self.variant_set,
            ),
            SmallVariantFactory(
                chromosome="3",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"}
                },
                refseq_gene_id="3",
                ensembl_gene_id="ENSG3",
                variant_set=self.variant_set,
            ),
            SmallVariantFactory(
                chromosome="3",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"}
                },
                variant_set=self.variant_set,
                refseq_gene_id="3",
                ensembl_gene_id="ENSG3",
            ),
        ]

    def test_query_compound_het_prefetch_filter(self):
        res = self.run_query(
            CasePrefetchQuery,
            {"compound_recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            2,
        )
        self.assertEqual(res[0].start, self.small_vars[2].start)
        self.assertEqual(res[1].start, self.small_vars[3].start)

    def test_query_compound_het_export_tsv(self):
        res = self.run_query(
            CaseExportTableQuery,
            {"compound_recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            2,
        )
        self.assertEqual(res[0].start, self.small_vars[2].start)
        self.assertEqual(res[1].start, self.small_vars[3].start)

    def test_query_compound_het_export_vcf(self):
        res = self.run_query(
            CaseExportVcfQuery,
            {"compound_recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            2,
        )
        self.assertEqual(res[0].start, self.small_vars[2].start)
        self.assertEqual(res[1].start, self.small_vars[3].start)

    def test_query_compound_het_load_prefetched_filter(self):
        # Generate results
        res = self.run_query(
            CasePrefetchQuery,
            {"compound_recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            2,
        )
        # Add results to variant query
        query = SmallVariantQueryFactory(case=self.case)
        query.query_results.add(*[r.id for r in res])
        # Load Prefetched results
        res = self.run_query(
            CaseLoadPrefetchedQuery,
            {
                "compound_recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]},
                "filter_job_id": query.id,
            },
            2,
        )
        self.assertEqual(res[0].start, self.small_vars[2].start)
        self.assertEqual(res[1].start, self.small_vars[3].start)


class TestCaseTwoRecessiveQuery(SupportQueryTestBase):
    """Test the queries for recessive hypothesis"""

    def setUp(self):
        """Create a trio case with 4 variants and make sure the coordinates in the same gene are on the same chromosome."""
        super().setUp()
        self.variant_set = SmallVariantSetFactory(case__structure="trio")
        self.case = self.variant_set.case
        self.small_vars = [
            SmallVariantFactory(
                chromosome="1",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                },
                ensembl_gene_id="ENSG1",
                variant_set=self.variant_set,
            ),
            SmallVariantFactory(
                chromosome="2",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "1/1"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                },
                refseq_gene_id="2",
                ensembl_gene_id="ENSG2",
                variant_set=self.variant_set,
            ),
            SmallVariantFactory(
                chromosome="3",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                },
                refseq_gene_id="3",
                ensembl_gene_id="ENSG3",
                variant_set=self.variant_set,
            ),
            SmallVariantFactory(
                chromosome="3",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                },
                variant_set=self.variant_set,
                refseq_gene_id="3",
                ensembl_gene_id="ENSG3",
            ),
        ]

    def test_query_recessive_prefetch_filter(self):
        res = self.run_query(
            CasePrefetchQuery,
            {"recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            3,
        )
        self.assertEqual(res[0].start, self.small_vars[1].start)
        self.assertEqual(res[1].start, self.small_vars[2].start)
        self.assertEqual(res[2].start, self.small_vars[3].start)

    def test_query_recessive_export_tsv(self):
        res = self.run_query(
            CaseExportTableQuery,
            {"recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            3,
        )
        self.assertEqual(res[0].start, self.small_vars[1].start)
        self.assertEqual(res[1].start, self.small_vars[2].start)
        self.assertEqual(res[2].start, self.small_vars[3].start)

    def test_query_recessive_export_vcf(self):
        res = self.run_query(
            CaseExportVcfQuery,
            {"recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            3,
        )
        self.assertEqual(res[0].start, self.small_vars[1].start)
        self.assertEqual(res[1].start, self.small_vars[2].start)
        self.assertEqual(res[2].start, self.small_vars[3].start)

    def test_query_recessive_load_prefetched_filter(self):
        # Generate results
        res = self.run_query(
            CasePrefetchQuery,
            {"recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            3,
        )
        # Add results to variant query
        query = SmallVariantQueryFactory(case=self.case)
        query.query_results.add(*[r.id for r in res])
        # Load Prefetched results
        res = self.run_query(
            CaseLoadPrefetchedQuery,
            {
                "recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]},
                "filter_job_id": query.id,
            },
            3,
        )
        self.assertEqual(res[0].start, self.small_vars[1].start)
        self.assertEqual(res[1].start, self.small_vars[2].start)
        self.assertEqual(res[2].start, self.small_vars[3].start)


class TestCaseTwoRecessiveQuartetQuery(SupportQueryTestBase):
    """Test the queries for compound recessive heterozygous hypothesis with siblings."""

    def setUp(self):
        """Create a quartet case with 4 variants and make sure the coordinates in the same gene are on the same chromosome."""
        super().setUp()
        self.variant_set = SmallVariantSetFactory(case__structure="quartet")
        self.case = self.variant_set.case
        self.small_vars = [
            SmallVariantFactory(
                chromosome="1",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[1]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                },
                ensembl_gene_id="ENSG1",
                variant_set=self.variant_set,
            ),
            SmallVariantFactory(
                chromosome="2",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "1/1"},
                    self.case.pedigree[1]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "1/1"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                },
                refseq_gene_id="2",
                ensembl_gene_id="ENSG2",
                variant_set=self.variant_set,
            ),
            SmallVariantFactory(
                chromosome="3",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[1]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                },
                refseq_gene_id="3",
                ensembl_gene_id="ENSG3",
                variant_set=self.variant_set,
            ),
            SmallVariantFactory(
                chromosome="3",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[1]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                },
                variant_set=self.variant_set,
                refseq_gene_id="3",
                ensembl_gene_id="ENSG3",
            ),
            SmallVariantFactory(
                chromosome="4",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case.pedigree[1]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                },
                refseq_gene_id="4",
                ensembl_gene_id="ENSG4",
                variant_set=self.variant_set,
            ),
            SmallVariantFactory(
                chromosome="4",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case.pedigree[1]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                },
                variant_set=self.variant_set,
                refseq_gene_id="4",
                ensembl_gene_id="ENSG4",
            ),
        ]

    def test_query_index_recessive_prefetch_filter(self):
        res = self.run_query(
            CasePrefetchQuery,
            {"recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            3,
        )
        self.assertEqual(res[0].start, self.small_vars[1].start)
        self.assertEqual(res[1].start, self.small_vars[2].start)
        self.assertEqual(res[2].start, self.small_vars[3].start)

    def test_query_index_recessive_prefetch_export_tsv(self):
        res = self.run_query(
            CaseExportTableQuery,
            {"recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            3,
        )
        self.assertEqual(res[0].start, self.small_vars[1].start)
        self.assertEqual(res[1].start, self.small_vars[2].start)
        self.assertEqual(res[2].start, self.small_vars[3].start)

    def test_query_index_recessive_prefetch_export_vcf(self):
        res = self.run_query(
            CaseExportVcfQuery,
            {"recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            3,
        )
        self.assertEqual(res[0].start, self.small_vars[1].start)
        self.assertEqual(res[1].start, self.small_vars[2].start)
        self.assertEqual(res[2].start, self.small_vars[3].start)

    def test_query_index_recessive_load_prefetched_filter(self):
        # Generate results
        res = self.run_query(
            CasePrefetchQuery,
            {"recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            3,
        )
        # Add results to variant query
        query = SmallVariantQueryFactory(case=self.case)
        query.query_results.add(*[r.id for r in res])
        # Load Prefetched results
        res = self.run_query(
            CaseLoadPrefetchedQuery,
            {
                "recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]},
                "filter_job_id": query.id,
            },
            3,
        )
        self.assertEqual(res[0].start, self.small_vars[1].start)
        self.assertEqual(res[1].start, self.small_vars[2].start)
        self.assertEqual(res[2].start, self.small_vars[3].start)

    def test_query_sibling_recessive_prefetch_filter(self):
        res = self.run_query(
            CasePrefetchQuery,
            {"recessive_indices": {self.case.name: self.case.pedigree[1]["patient"]}},
            3,
        )
        self.assertEqual(res[0].start, self.small_vars[1].start)
        self.assertEqual(res[1].start, self.small_vars[4].start)
        self.assertEqual(res[2].start, self.small_vars[5].start)

    def test_query_sibling_recessive_prefetch_export_tsv(self):
        res = self.run_query(
            CaseExportTableQuery,
            {"recessive_indices": {self.case.name: self.case.pedigree[1]["patient"]}},
            3,
        )
        self.assertEqual(res[0].start, self.small_vars[1].start)
        self.assertEqual(res[1].start, self.small_vars[4].start)
        self.assertEqual(res[2].start, self.small_vars[5].start)

    def test_query_sibling_recessive_prefetch_export_vcf(self):
        res = self.run_query(
            CaseExportVcfQuery,
            {"recessive_indices": {self.case.name: self.case.pedigree[1]["patient"]}},
            3,
        )
        self.assertEqual(res[0].start, self.small_vars[1].start)
        self.assertEqual(res[1].start, self.small_vars[4].start)
        self.assertEqual(res[2].start, self.small_vars[5].start)

    def test_query_sibling_recessive_load_prefetched_filter(self):
        # Generate results
        res = self.run_query(
            CasePrefetchQuery,
            {"recessive_indices": {self.case.name: self.case.pedigree[1]["patient"]}},
            3,
        )
        # Add results to variant query
        query = SmallVariantQueryFactory(case=self.case)
        query.query_results.add(*[r.id for r in res])
        # Load Prefetched results
        res = self.run_query(
            CaseLoadPrefetchedQuery,
            {
                "recessive_indices": {self.case.name: self.case.pedigree[1]["patient"]},
                "filter_job_id": query.id,
            },
            3,
        )
        self.assertEqual(res[0].start, self.small_vars[1].start)
        self.assertEqual(res[1].start, self.small_vars[4].start)
        self.assertEqual(res[2].start, self.small_vars[5].start)


class TestCaseTwoRecessiveQuintetQuery(SupportQueryTestBase):
    """Test the queries for compound recessive heterozygous hypothesis with grandparents."""

    def setUp(self):
        """Create a quartet case with 4 variants and make sure the coordinates in the same gene are on the same chromosome."""
        super().setUp()
        self.variant_set = SmallVariantSetFactory(case__structure="quintet")
        self.case = self.variant_set.case
        self.small_vars = [
            SmallVariantFactory(
                chromosome="1",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "1/1"},
                    self.case.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    # self.case.pedigree[1]["patient"] is self.case.pedigree[0]["father"]
                    self.case.pedigree[1]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[1]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                },
                refseq_gene_id="1",
                ensembl_gene_id="ENSG1",
                variant_set=self.variant_set,
            ),
            SmallVariantFactory(
                chromosome="2",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "1/1"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    # self.case.pedigree[1]["patient"] is self.case.pedigree[0]["father"]
                    self.case.pedigree[1]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case.pedigree[1]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                },
                refseq_gene_id="2",
                ensembl_gene_id="ENSG2",
                variant_set=self.variant_set,
            ),
            SmallVariantFactory(
                chromosome="3",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    # self.case.pedigree[1]["patient"] is self.case.pedigree[0]["father"]
                    self.case.pedigree[1]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case.pedigree[1]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                },
                refseq_gene_id="3",
                ensembl_gene_id="ENSG3",
                variant_set=self.variant_set,
            ),
            SmallVariantFactory(
                chromosome="3",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    # self.case.pedigree[1]["patient"] is self.case.pedigree[0]["father"]
                    self.case.pedigree[1]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case.pedigree[1]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                },
                variant_set=self.variant_set,
                refseq_gene_id="3",
                ensembl_gene_id="ENSG3",
            ),
            SmallVariantFactory(
                chromosome="4",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    # self.case.pedigree[1]["patient"] is self.case.pedigree[0]["father"]
                    self.case.pedigree[1]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case.pedigree[1]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                },
                refseq_gene_id="4",
                ensembl_gene_id="ENSG4",
                variant_set=self.variant_set,
            ),
            SmallVariantFactory(
                chromosome="4",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    # self.case.pedigree[1]["patient"] is self.case.pedigree[0]["father"]
                    self.case.pedigree[1]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[1]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                },
                variant_set=self.variant_set,
                refseq_gene_id="4",
                ensembl_gene_id="ENSG4",
            ),
        ]

    def test_query_index_recessive_prefetch_filter(self):
        res = self.run_query(
            CasePrefetchQuery,
            {"recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            3,
        )
        self.assertEqual(res[0].start, self.small_vars[1].start)
        self.assertEqual(res[1].start, self.small_vars[2].start)
        self.assertEqual(res[2].start, self.small_vars[3].start)

    def test_query_index_recessive_prefetch_export_tsv(self):
        res = self.run_query(
            CaseExportTableQuery,
            {"recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            3,
        )
        self.assertEqual(res[0].start, self.small_vars[1].start)
        self.assertEqual(res[1].start, self.small_vars[2].start)
        self.assertEqual(res[2].start, self.small_vars[3].start)

    def test_query_index_recessive_prefetch_export_vcf(self):
        res = self.run_query(
            CaseExportVcfQuery,
            {"recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            3,
        )
        self.assertEqual(res[0].start, self.small_vars[1].start)
        self.assertEqual(res[1].start, self.small_vars[2].start)
        self.assertEqual(res[2].start, self.small_vars[3].start)

    def test_query_index_recessive_load_prefetched_filter(self):
        # Generate results
        res = self.run_query(
            CasePrefetchQuery,
            {"recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            3,
        )
        # Add results to variant query
        query = SmallVariantQueryFactory(case=self.case)
        query.query_results.add(*[r.id for r in res])
        # Load Prefetched results
        res = self.run_query(
            CaseLoadPrefetchedQuery,
            {
                "recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]},
                "filter_job_id": query.id,
            },
            3,
        )
        self.assertEqual(res[0].start, self.small_vars[1].start)
        self.assertEqual(res[1].start, self.small_vars[2].start)
        self.assertEqual(res[2].start, self.small_vars[3].start)

    def test_query_father_recessive_prefetch_filter(self):
        res = self.run_query(
            CasePrefetchQuery,
            {"recessive_indices": {self.case.name: self.case.pedigree[1]["patient"]}},
            3,
        )
        self.assertEqual(res[0].start, self.small_vars[0].start)
        self.assertEqual(res[1].start, self.small_vars[4].start)
        self.assertEqual(res[2].start, self.small_vars[5].start)

    def test_query_father_recessive_prefetch_export_tsv(self):
        res = self.run_query(
            CaseExportTableQuery,
            {"recessive_indices": {self.case.name: self.case.pedigree[1]["patient"]}},
            3,
        )
        self.assertEqual(res[0].start, self.small_vars[0].start)
        self.assertEqual(res[1].start, self.small_vars[4].start)
        self.assertEqual(res[2].start, self.small_vars[5].start)


def test_query_father_recessive_prefetch_export_vcf(self):
    res = self.run_query(
        CaseExportVcfQuery,
        {"recessive_indices": {self.case.name: self.case.pedigree[1]["patient"]}},
        3,
    )
    self.assertEqual(res[0].start, self.small_vars[0].start)
    self.assertEqual(res[1].start, self.small_vars[4].start)
    self.assertEqual(res[2].start, self.small_vars[5].start)


def test_query_father_recessive_load_prefetched_filter(self):
    # Generate results
    res = self.run_query(
        CasePrefetchQuery,
        {"recessive_indices": {self.case.name: self.case.pedigree[1]["patient"]}},
        3,
    )
    # Add results to variant query
    query = SmallVariantQueryFactory(case=self.case)
    query.query_results.add(*[r.id for r in res])
    # Load Prefetched results
    res = self.run_query(
        CaseLoadPrefetchedQuery,
        {
            "recessive_indices": {self.case.name: self.case.pedigree[1]["patient"]},
            "filter_job_id": query.id,
        },
        3,
    )
    self.assertEqual(res[0].start, self.small_vars[0].start)
    self.assertEqual(res[1].start, self.small_vars[4].start)
    self.assertEqual(res[2].start, self.small_vars[5].start)


class TestCaseTwoRecessiveOneParentQuery(SupportQueryTestBase):
    """Test the queries for compound recessive heterozygous hypothesis"""

    def setUp(self):
        """Create an index + parent case with 4 variants and make sure the coordinates in the same gene are on the same chromosome."""
        super().setUp()
        self.variant_set = SmallVariantSetFactory(case__structure="duo")
        self.case = self.variant_set.case
        self.small_vars = [
            SmallVariantFactory(
                chromosome="1",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                },
                ensembl_gene_id="ENSG1",
                variant_set=self.variant_set,
            ),
            SmallVariantFactory(
                chromosome="2",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "1/1"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                },
                refseq_gene_id="2",
                ensembl_gene_id="ENSG2",
                variant_set=self.variant_set,
            ),
            SmallVariantFactory(
                chromosome="3",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                },
                refseq_gene_id="3",
                ensembl_gene_id="ENSG3",
                variant_set=self.variant_set,
            ),
            SmallVariantFactory(
                chromosome="3",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                },
                variant_set=self.variant_set,
                refseq_gene_id="3",
                ensembl_gene_id="ENSG3",
            ),
        ]

    def test_query_recessive_prefetch_filter(self):
        res = self.run_query(
            CasePrefetchQuery,
            {"recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            3,
        )
        self.assertEqual(res[0].start, self.small_vars[1].start)
        self.assertEqual(res[1].start, self.small_vars[2].start)
        self.assertEqual(res[2].start, self.small_vars[3].start)

    def test_query_recessive_export_tsv(self):
        res = self.run_query(
            CaseExportTableQuery,
            {"recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            3,
        )
        self.assertEqual(res[0].start, self.small_vars[1].start)
        self.assertEqual(res[1].start, self.small_vars[2].start)
        self.assertEqual(res[2].start, self.small_vars[3].start)

    def test_query_recessive_export_vcf(self):
        res = self.run_query(
            CaseExportVcfQuery,
            {"recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            3,
        )
        self.assertEqual(res[0].start, self.small_vars[1].start)
        self.assertEqual(res[1].start, self.small_vars[2].start)
        self.assertEqual(res[2].start, self.small_vars[3].start)

    def test_query_recessive_load_prefetched_filter(self):
        # Generate results
        res = self.run_query(
            CasePrefetchQuery,
            {"recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            3,
        )
        # Add results to variant query
        query = SmallVariantQueryFactory(case=self.case)
        query.query_results.add(*[r.id for r in res])
        # Load Prefetched results
        res = self.run_query(
            CaseLoadPrefetchedQuery,
            {
                "recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]},
                "filter_job_id": query.id,
            },
            3,
        )
        self.assertEqual(res[0].start, self.small_vars[1].start)
        self.assertEqual(res[1].start, self.small_vars[2].start)
        self.assertEqual(res[2].start, self.small_vars[3].start)


class TestCaseTwoRecessiveSingletonQuery(SupportQueryTestBase):
    """Test the queries for compound recessive heterozygous hypothesis"""

    def setUp(self):
        """Create a singleton case with 4 variants and make sure the coordinates in the same gene are on the same chromosome."""
        super().setUp()
        self.variant_set = SmallVariantSetFactory(case__structure="singleton")
        self.case = self.variant_set.case
        self.small_vars = [
            SmallVariantFactory(
                chromosome="1",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"}
                },
                ensembl_gene_id="ENSG1",
                variant_set=self.variant_set,
            ),
            SmallVariantFactory(
                chromosome="2",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "1/1"}
                },
                refseq_gene_id="2",
                ensembl_gene_id="ENSG2",
                variant_set=self.variant_set,
            ),
            SmallVariantFactory(
                chromosome="3",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"}
                },
                refseq_gene_id="3",
                ensembl_gene_id="ENSG3",
                variant_set=self.variant_set,
            ),
            SmallVariantFactory(
                chromosome="3",
                genotype={
                    self.case.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"}
                },
                variant_set=self.variant_set,
                refseq_gene_id="3",
                ensembl_gene_id="ENSG3",
            ),
        ]

    def test_query_recessive_prefetch_filter(self):
        res = self.run_query(
            CasePrefetchQuery,
            {"recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            3,
        )
        self.assertEqual(res[0].start, self.small_vars[1].start)
        self.assertEqual(res[1].start, self.small_vars[2].start)
        self.assertEqual(res[2].start, self.small_vars[3].start)

    def test_query_recessive_export_tsv(self):
        res = self.run_query(
            CaseExportTableQuery,
            {"recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            3,
        )
        self.assertEqual(res[0].start, self.small_vars[1].start)
        self.assertEqual(res[1].start, self.small_vars[2].start)
        self.assertEqual(res[2].start, self.small_vars[3].start)

    def test_query_recessive_export_vcf(self):
        res = self.run_query(
            CaseExportVcfQuery,
            {"recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            3,
        )
        self.assertEqual(res[0].start, self.small_vars[1].start)
        self.assertEqual(res[1].start, self.small_vars[2].start)
        self.assertEqual(res[2].start, self.small_vars[3].start)

    def test_query_recessive_load_prefetched_filter(self):
        # Generate results
        res = self.run_query(
            CasePrefetchQuery,
            {"recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]}},
            3,
        )
        # Add results to variant query
        query = SmallVariantQueryFactory(case=self.case)
        query.query_results.add(*[r.id for r in res])
        # Load Prefetched results
        res = self.run_query(
            CaseLoadPrefetchedQuery,
            {
                "recessive_indices": {self.case.name: self.case.pedigree[0]["patient"]},
                "filter_job_id": query.id,
            },
            3,
        )
        self.assertEqual(res[0].start, self.small_vars[1].start)
        self.assertEqual(res[1].start, self.small_vars[2].start)
        self.assertEqual(res[2].start, self.small_vars[3].start)


# ---------------------------------------------------------------------------
# Tests for Case 3
# ---------------------------------------------------------------------------

# Case 3 is a singleton test case and meant for testing the Clinvar
# membership queries. We create a new test case for this as we might be able
# to allow the user to filter out benign variants or variants of unknown
# significance.


class CaseThreeClinvarFilterTestMixin:
    """Base class for testing query with Clinvar filter."""

    query_class = None

    def setUp(self):
        super().setUp()
        variant_set = SmallVariantSetFactory(case__structure="trio")
        self.small_vars = [
            SmallVariantFactory(chromosome="1", in_clinvar=False, variant_set=variant_set),
            SmallVariantFactory(chromosome="2", in_clinvar=True, variant_set=variant_set),
        ]
        # Create two entries for first variant that is in clinvar (second variant in total)
        ClinvarFactory(
            release=self.small_vars[-1].release,
            chromosome=self.small_vars[-1].chromosome,
            start=self.small_vars[-1].start,
            end=self.small_vars[-1].end,
            bin=self.small_vars[-1].bin,
            reference=self.small_vars[-1].reference,
            alternative=self.small_vars[-1].alternative,
            clinical_significance="pathogenic",
            clinical_significance_ordered=["pathogenic"],
            origin=["somatic"],
            pathogenic=1,
        )
        ClinvarFactory(
            release=self.small_vars[-1].release,
            chromosome=self.small_vars[-1].chromosome,
            start=self.small_vars[-1].start,
            end=self.small_vars[-1].end,
            bin=self.small_vars[-1].bin,
            reference=self.small_vars[-1].reference,
            alternative=self.small_vars[-1].alternative,
            clinical_significance="likely_pathogenic",
            clinical_significance_ordered=["likely_pathogenic"],
            origin=["germline"],
            likely_pathogenic=1,
        )
        patho_keys = (
            ("pathogenic", ["germline"]),
            ("likely_pathogenic", ["germline"]),
            ("uncertain_significance", ["germline", "somatic"]),
            ("likely_benign", ["somatic"]),
            ("benign", ["something_else"]),
        )
        # Start chromosomes from "3" on
        for pos, (key, origin) in enumerate(patho_keys):
            self.small_vars.append(
                SmallVariantFactory(
                    chromosome=str(pos + 3), in_clinvar=True, variant_set=variant_set
                )
            )
            ClinvarFactory(
                release=self.small_vars[-1].release,
                chromosome=self.small_vars[-1].chromosome,
                start=self.small_vars[-1].start,
                end=self.small_vars[-1].end,
                bin=self.small_vars[-1].bin,
                reference=self.small_vars[-1].reference,
                alternative=self.small_vars[-1].alternative,
                clinical_significance=key,
                clinical_significance_ordered=[key],
                origin=origin,
                **{key: 1},
            )
        DbsnpFactory(
            release=self.small_vars[0].release,
            chromosome=self.small_vars[0].chromosome,
            start=self.small_vars[0].start,
            end=self.small_vars[0].end,
            bin=self.small_vars[0].bin,
            reference=self.small_vars[0].reference,
            alternative=self.small_vars[0].alternative,
        )

    def test_render_query_do_not_require_membership(self):
        self.run_query(self.query_class, {}, 6)

    def test_render_query_require_membership_include_none(self):
        self.run_query(self.query_class, {"require_in_clinvar": True}, 6)

    def test_render_query_remove_if_in_dbsnp_sanity(self):
        self.run_query(self.query_class, {"remove_if_in_dbsnp": True}, 5)

    def test_render_query_require_membership_ignore_remove_if_in_dbsnp(self):
        self.run_query(
            self.query_class, {"require_in_clinvar": True, "remove_if_in_dbsnp": True}, 6
        )

    def test_render_query_require_membership_include_pathogenic(self):
        res = self.run_query(
            self.query_class, {"require_in_clinvar": True, "clinvar_include_pathogenic": True}, 2
        )
        self.assertEqual(res[0].start, self.small_vars[1].start)
        self.assertEqual(res[1].start, self.small_vars[2].start)

    def test_render_query_require_membership_include_likely_pathogenic(self):
        res = self.run_query(
            self.query_class,
            {"require_in_clinvar": True, "clinvar_include_likely_pathogenic": True},
            2,
        )
        self.assertEqual(res[0].start, self.small_vars[1].start)
        self.assertEqual(res[1].start, self.small_vars[3].start)

    def test_render_query_require_membership_include_pathogenic_and_likely_pathogenic(self):
        res = self.run_query(
            self.query_class,
            {
                "require_in_clinvar": True,
                "clinvar_include_pathogenic": True,
                "clinvar_include_likely_pathogenic": True,
            },
            3,
        )
        self.assertEqual(res[0].start, self.small_vars[1].start)
        self.assertEqual(res[1].start, self.small_vars[2].start)
        self.assertEqual(res[2].start, self.small_vars[3].start)

    def test_render_query_require_membership_include_uncertain_significance(self):
        res = self.run_query(
            self.query_class,
            {"require_in_clinvar": True, "clinvar_include_uncertain_significance": True},
            1,
        )
        self.assertEqual(res[0].start, self.small_vars[4].start)

    def test_render_query_require_membership_include_likely_benign(self):
        res = self.run_query(
            self.query_class, {"require_in_clinvar": True, "clinvar_include_likely_benign": True}, 1
        )
        self.assertEqual(res[0].start, self.small_vars[5].start)

    def test_render_query_require_membership_include_benign(self):
        res = self.run_query(
            self.query_class, {"require_in_clinvar": True, "clinvar_include_benign": True}, 1
        )
        self.assertEqual(res[0].start, self.small_vars[6].start)

    def test_render_query_require_membership_origin_both(self):
        self.run_query(
            self.query_class,
            {
                "require_in_clinvar": True,
                "clinvar_origin_germline": True,
                "clinvar_origin_somatic": True,
            },
            5,
        )

    def test_render_query_require_membership_origin_germline(self):
        self.run_query(
            self.query_class,
            {
                "require_in_clinvar": True,
                "clinvar_origin_germline": True,
                "clinvar_origin_somatic": False,
            },
            4,
        )

    def test_render_query_require_membership_origin_somatic(self):
        self.run_query(
            self.query_class,
            {
                "require_in_clinvar": True,
                "clinvar_origin_germline": False,
                "clinvar_origin_somatic": True,
            },
            3,
        )

    def test_render_query_require_membership_no_origin(self):
        self.run_query(
            self.query_class,
            {
                "require_in_clinvar": True,
                "clinvar_origin_germline": False,
                "clinvar_origin_somatic": False,
            },
            6,
        )

    def test_render_query_not_required_and_significance(self):
        self.run_query(
            self.query_class,
            {
                "require_in_clinvar": False,
                "clinvar_origin_germline": True,
                "clinvar_origin_somatic": True,
                "clinvar_include_pathogenic": True,
            },
            6,
        )

    def test_render_query_not_required_and_origin(self):
        self.run_query(
            self.query_class,
            {
                "require_in_clinvar": False,
                "clinvar_origin_germline": True,
                "clinvar_origin_somatic": False,
            },
            6,
        )


class RenderQueryTestCaseThreeClinvarFilter(CaseThreeClinvarFilterTestMixin, SupportQueryTestBase):
    """Test clinvar membership using RenderFilterQuery."""

    query_class = CasePrefetchQuery


class ExportFileFilterQueryTestCaseThreeClinvarFilter(
    CaseThreeClinvarFilterTestMixin, SupportQueryTestBase
):
    """Test clinvar membership using ExportFileFilterQuery."""

    query_class = CaseExportTableQuery


class ExportVcfFilterQueryTestCaseThreeClinvarFilter(
    CaseThreeClinvarFilterTestMixin, SupportQueryTestBase
):
    """Test clinvar membership using ExportFileFilterQuery."""

    query_class = CaseExportVcfQuery


# TODO exports are missing
class TestHgmdMembershipQuery(SupportQueryTestBase):
    """Tests for the HGMD membership query."""

    def setUp(self):
        """Create a case and two variants: one in HGMD, the other not."""
        super().setUp()
        variant_set = SmallVariantSetFactory()
        self.small_vars = [
            SmallVariantFactory(variant_set=variant_set, chromosome="1", start=100, end=100),
            SmallVariantFactory(variant_set=variant_set, chromosome="2", start=200, end=200),
        ]
        self.hgmd = HgmdPublicLocusFactory(
            chromosome=self.small_vars[1].chromosome,
            start=self.small_vars[1].start - 1,
            end=self.small_vars[1].start,
        )

    def test_no_hgmd_query(self):
        self.run_query(
            CasePrefetchQuery,
            {"require_in_hgmd_public": False, "display_hgmd_public_membership": False},
            2,
        )

    def test_require_in_hgmd_query(self):
        self.run_query(
            CasePrefetchQuery,
            {"require_in_hgmd_public": True, "display_hgmd_public_membership": False},
            1,
        )

    def test_display_hgmd_membership_query(self):
        res = self.run_query(
            CasePrefetchQuery,
            {"require_in_hgmd_public": False, "display_hgmd_public_membership": True},
            2,
        )
        self.assertEqual(res[1].hgmd_accession, self.hgmd.variation_name)

    def test_require_in_hgmd_and_display_membership_query(self):
        res = self.run_query(
            CasePrefetchQuery,
            {"require_in_hgmd_public": True, "display_hgmd_public_membership": True},
            1,
        )
        self.assertEqual(res[0].hgmd_accession, self.hgmd.variation_name)


class TestProjectCompHetQuery(SupportQueryTestBase):
    def setUp(self):
        super().setUp()
        self.project = ProjectFactory()
        self.variant_sets = [
            SmallVariantSetFactory(case__project=self.project),
            SmallVariantSetFactory(case__project=self.project),
        ]
        self.case1 = self.variant_sets[0].case
        self.case2 = self.variant_sets[1].case
        self.small_vars = [
            SmallVariantFactory(
                chromosome="1",
                genotype={
                    self.case1.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case1.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case1.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                },
                ensembl_gene_id="ENSG1",
                variant_set=self.variant_sets[0],
            ),
            SmallVariantFactory(
                chromosome="2",
                genotype={
                    self.case1.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "1/1"},
                    self.case1.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case1.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                },
                refseq_gene_id="2",
                ensembl_gene_id="ENSG2",
                variant_set=self.variant_sets[0],
            ),
            SmallVariantFactory(
                chromosome="3",
                genotype={
                    self.case1.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case1.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case1.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                },
                refseq_gene_id="3",
                ensembl_gene_id="ENSG3",
                variant_set=self.variant_sets[0],
            ),
            SmallVariantFactory(
                chromosome="3",
                genotype={
                    self.case1.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case1.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case1.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                },
                variant_set=self.variant_sets[0],
                refseq_gene_id="3",
                ensembl_gene_id="ENSG3",
            ),
            SmallVariantFactory(
                chromosome="4",
                genotype={
                    self.case2.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case2.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case2.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                },
                ensembl_gene_id="ENSG4",
                variant_set=self.variant_sets[1],
            ),
            SmallVariantFactory(
                chromosome="5",
                genotype={
                    self.case2.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "1/1"},
                    self.case2.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case2.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                },
                refseq_gene_id="5",
                ensembl_gene_id="ENSG5",
                variant_set=self.variant_sets[1],
            ),
            SmallVariantFactory(
                chromosome="6",
                genotype={
                    self.case2.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case2.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case2.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                },
                refseq_gene_id="6",
                ensembl_gene_id="ENSG6",
                variant_set=self.variant_sets[1],
            ),
            SmallVariantFactory(
                chromosome="6",
                genotype={
                    self.case2.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case2.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case2.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                },
                variant_set=self.variant_sets[1],
                refseq_gene_id="6",
                ensembl_gene_id="ENSG6",
            ),
        ]

    def test_query_project_comp_het_with_two_cases_both_comp_het(self):
        res = self.run_query(
            ProjectPrefetchQuery,
            {
                "compound_recessive_indices": {
                    self.case1.name: self.case1.pedigree[0]["patient"],
                    self.case2.name: self.case2.pedigree[0]["patient"],
                }
            },
            4,
            query_type="project",
        )
        self.assertEqual(res[0].start, self.small_vars[2].start)
        self.assertEqual(res[1].start, self.small_vars[3].start)
        self.assertEqual(res[2].start, self.small_vars[6].start)
        self.assertEqual(res[3].start, self.small_vars[7].start)

    def test_query_project_comp_het_with_two_cases_only_one_comp_het(self):
        res = self.run_query(
            ProjectPrefetchQuery,
            {"compound_recessive_indices": {self.case1.name: self.case1.pedigree[0]["patient"]}},
            6,
            query_type="project",
        )
        self.assertEqual(res[0].start, self.small_vars[2].start)
        self.assertEqual(res[1].start, self.small_vars[3].start)
        self.assertEqual(res[2].start, self.small_vars[4].start)
        self.assertEqual(res[3].start, self.small_vars[5].start)
        self.assertEqual(res[4].start, self.small_vars[6].start)
        self.assertEqual(res[5].start, self.small_vars[7].start)

    def test_load_project_prefetched_comp_het_with_two_cases_both_comp_het(self):
        res = self.run_query(
            ProjectPrefetchQuery,
            {
                "compound_recessive_indices": {
                    self.case1.name: self.case1.pedigree[0]["patient"],
                    self.case2.name: self.case2.pedigree[0]["patient"],
                }
            },
            4,
            query_type="project",
        )
        query = ProjectCasesSmallVariantQueryFactory(project=self.project)
        query.query_results.add(*[r.id for r in res])
        res = self.run_query(
            ProjectLoadPrefetchedQuery,
            {
                "filter_job_id": query.id,
                "compound_recessive_indices": {
                    self.case1.name: self.case1.pedigree[0]["patient"],
                    self.case2.name: self.case2.pedigree[0]["patient"],
                },
            },
            4,
            query_type="project",
        )
        self.assertEqual(res[0].start, self.small_vars[2].start)
        self.assertEqual(res[1].start, self.small_vars[3].start)
        self.assertEqual(res[2].start, self.small_vars[6].start)
        self.assertEqual(res[3].start, self.small_vars[7].start)

    def test_load_project_prefetched_comp_het_with_two_cases_only_one_comp_het(self):
        res = self.run_query(
            ProjectPrefetchQuery,
            {"compound_recessive_indices": {self.case1.name: self.case1.pedigree[0]["patient"]}},
            6,
            query_type="project",
        )
        query = ProjectCasesSmallVariantQueryFactory(project=self.project)
        query.query_results.add(*[r.id for r in res])
        res = self.run_query(
            ProjectLoadPrefetchedQuery,
            {
                "filter_job_id": query.id,
                "compound_recessive_indices": {self.case1.name: self.case1.pedigree[0]["patient"]},
            },
            6,
            query_type="project",
        )
        self.assertEqual(res[0].start, self.small_vars[2].start)
        self.assertEqual(res[1].start, self.small_vars[3].start)
        self.assertEqual(res[2].start, self.small_vars[4].start)
        self.assertEqual(res[3].start, self.small_vars[5].start)
        self.assertEqual(res[4].start, self.small_vars[6].start)
        self.assertEqual(res[5].start, self.small_vars[7].start)

    # A combination of recessive and comp het is tested in "TestProjectRecessiveQuery"


class TestProjectRecessiveQuery(SupportQueryTestBase):
    def setUp(self):
        super().setUp()
        self.project = ProjectFactory()
        self.variant_sets = [
            SmallVariantSetFactory(case__project=self.project),
            SmallVariantSetFactory(case__project=self.project),
        ]
        self.case1 = self.variant_sets[0].case
        self.case2 = self.variant_sets[1].case
        self.small_vars = [
            SmallVariantFactory(
                chromosome="1",
                genotype={
                    self.case1.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case1.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case1.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                },
                ensembl_gene_id="ENSG1",
                variant_set=self.variant_sets[0],
            ),
            SmallVariantFactory(
                chromosome="2",
                genotype={
                    self.case1.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "1/1"},
                    self.case1.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case1.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                },
                refseq_gene_id="2",
                ensembl_gene_id="ENSG2",
                variant_set=self.variant_sets[0],
            ),
            SmallVariantFactory(
                chromosome="3",
                genotype={
                    self.case1.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case1.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case1.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                },
                refseq_gene_id="3",
                ensembl_gene_id="ENSG3",
                variant_set=self.variant_sets[0],
            ),
            SmallVariantFactory(
                chromosome="3",
                genotype={
                    self.case1.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case1.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case1.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                },
                variant_set=self.variant_sets[0],
                refseq_gene_id="3",
                ensembl_gene_id="ENSG3",
            ),
            SmallVariantFactory(
                chromosome="4",
                genotype={
                    self.case2.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case2.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case2.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                },
                ensembl_gene_id="ENSG4",
                variant_set=self.variant_sets[1],
            ),
            SmallVariantFactory(
                chromosome="5",
                genotype={
                    self.case2.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "1/1"},
                    self.case2.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case2.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                },
                refseq_gene_id="5",
                ensembl_gene_id="ENSG5",
                variant_set=self.variant_sets[1],
            ),
            SmallVariantFactory(
                chromosome="6",
                genotype={
                    self.case2.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case2.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                    self.case2.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                },
                refseq_gene_id="6",
                ensembl_gene_id="ENSG6",
                variant_set=self.variant_sets[1],
            ),
            SmallVariantFactory(
                chromosome="6",
                genotype={
                    self.case2.pedigree[0]["patient"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case2.pedigree[0]["father"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/1"},
                    self.case2.pedigree[0]["mother"]: {"ad": 15, "dp": 30, "gq": 99, "gt": "0/0"},
                },
                variant_set=self.variant_sets[1],
                refseq_gene_id="6",
                ensembl_gene_id="ENSG6",
            ),
        ]

    def test_query_project_recessive_with_two_cases_both_recessive(self):
        res = self.run_query(
            ProjectPrefetchQuery,
            {
                "recessive_indices": {
                    self.case1.name: self.case1.pedigree[0]["patient"],
                    self.case2.name: self.case2.pedigree[0]["patient"],
                }
            },
            6,
            query_type="project",
        )
        self.assertEqual(res[0].start, self.small_vars[1].start)
        self.assertEqual(res[1].start, self.small_vars[2].start)
        self.assertEqual(res[2].start, self.small_vars[3].start)
        self.assertEqual(res[3].start, self.small_vars[5].start)
        self.assertEqual(res[4].start, self.small_vars[6].start)
        self.assertEqual(res[5].start, self.small_vars[7].start)

    def test_query_project_recessive_with_two_cases_only_one_recessive(self):
        res = self.run_query(
            ProjectPrefetchQuery,
            {"recessive_indices": {self.case1.name: self.case1.pedigree[0]["patient"]}},
            7,
            query_type="project",
        )
        self.assertEqual(res[0].start, self.small_vars[1].start)
        self.assertEqual(res[1].start, self.small_vars[2].start)
        self.assertEqual(res[2].start, self.small_vars[3].start)
        self.assertEqual(res[3].start, self.small_vars[4].start)
        self.assertEqual(res[4].start, self.small_vars[5].start)
        self.assertEqual(res[5].start, self.small_vars[6].start)
        self.assertEqual(res[6].start, self.small_vars[7].start)

    def test_load_project_prefetched_recessive_with_two_cases_both_recessive(self):
        res = self.run_query(
            ProjectPrefetchQuery,
            {
                "recessive_indices": {
                    self.case1.name: self.case1.pedigree[0]["patient"],
                    self.case2.name: self.case2.pedigree[0]["patient"],
                }
            },
            6,
            query_type="project",
        )
        query = ProjectCasesSmallVariantQueryFactory(project=self.project)
        query.query_results.add(*[r.id for r in res])
        res = self.run_query(
            ProjectLoadPrefetchedQuery,
            {
                "filter_job_id": query.id,
                "recessive_indices": {
                    self.case1.name: self.case1.pedigree[0]["patient"],
                    self.case2.name: self.case2.pedigree[0]["patient"],
                },
            },
            6,
            query_type="project",
        )
        self.assertEqual(res[0].start, self.small_vars[1].start)
        self.assertEqual(res[1].start, self.small_vars[2].start)
        self.assertEqual(res[2].start, self.small_vars[3].start)
        self.assertEqual(res[3].start, self.small_vars[5].start)
        self.assertEqual(res[4].start, self.small_vars[6].start)
        self.assertEqual(res[5].start, self.small_vars[7].start)

    def test_load_project_prefetched_recessive_with_two_cases_only_one_recessive(self):
        res = self.run_query(
            ProjectPrefetchQuery,
            {"recessive_indices": {self.case1.name: self.case1.pedigree[0]["patient"]}},
            7,
            query_type="project",
        )
        query = ProjectCasesSmallVariantQueryFactory(project=self.project)
        query.query_results.add(*[r.id for r in res])
        res = self.run_query(
            ProjectLoadPrefetchedQuery,
            {
                "filter_job_id": query.id,
                "recessive_indices": {self.case1.name: self.case1.pedigree[0]["patient"]},
            },
            7,
            query_type="project",
        )
        self.assertEqual(res[0].start, self.small_vars[1].start)
        self.assertEqual(res[1].start, self.small_vars[2].start)
        self.assertEqual(res[2].start, self.small_vars[3].start)
        self.assertEqual(res[3].start, self.small_vars[4].start)
        self.assertEqual(res[4].start, self.small_vars[5].start)
        self.assertEqual(res[5].start, self.small_vars[6].start)
        self.assertEqual(res[6].start, self.small_vars[7].start)

    def test_query_project_recessive_with_two_cases_one_recessive_one_comphet(self):
        res = self.run_query(
            ProjectPrefetchQuery,
            {
                "compound_recessive_indices": {self.case1.name: self.case1.pedigree[0]["patient"]},
                "recessive_indices": {self.case2.name: self.case2.pedigree[0]["patient"]},
            },
            5,
            query_type="project",
        )
        self.assertEqual(res[0].start, self.small_vars[2].start)
        self.assertEqual(res[1].start, self.small_vars[3].start)
        self.assertEqual(res[2].start, self.small_vars[5].start)
        self.assertEqual(res[3].start, self.small_vars[6].start)
        self.assertEqual(res[4].start, self.small_vars[7].start)


class TestCaseFiveQueryProject(SupportQueryTestBase):
    def setUp(self):
        super().setUp()
        project = ProjectFactory()
        variant_sets = [
            SmallVariantSetFactory(case__project=project),
            SmallVariantSetFactory(case__project=project),
        ]
        small_vars = [
            SmallVariantFactory(variant_set=variant_sets[0]),
            SmallVariantFactory(variant_set=variant_sets[1]),
            SmallVariantFactory(variant_set=variant_sets[1]),
        ]
        self.projectcasessmallvariantquery = ProjectCasesSmallVariantQueryFactory(project=project)
        self.projectcasessmallvariantquery.query_results.add(small_vars[0], small_vars[2])

    def test_query_project_with_two_cases(self):
        self.run_query(ProjectPrefetchQuery, {}, 3, query_type="project")

    def test_load_project_prefetched_two_cases(self):
        self.run_query(
            ProjectLoadPrefetchedQuery,
            {"filter_job_id": self.projectcasessmallvariantquery.id},
            2,
            query_type="project",
        )


class TestKnownGeneAAQuery(TestBase):
    """Test the knowngeneaa query."""

    def run_query(self, query_class, kwargs, length):
        query = query_class(SQLALCHEMY_ENGINE)
        results = list(query.run(kwargs))
        self.assertEqual(len(results), length)

    def setUp(self):
        super().setUp()
        self.knowngene = KnownGeneAAFactory(chromosome="1", start=100)

    def test_query_pre_triplet(self):
        self.run_query(
            KnownGeneAAQuery,
            {
                "release": self.knowngene.release,
                "chromosome": self.knowngene.chromosome,
                "start": self.knowngene.start - 1,
                "end": self.knowngene.end - 1,
                "reference": "A",
            },
            0,
        )

    def test_query_first_triplet(self):
        self.run_query(
            KnownGeneAAQuery,
            {
                "release": self.knowngene.release,
                "chromosome": self.knowngene.chromosome,
                "start": self.knowngene.start,
                "end": self.knowngene.start,
                "reference": "A",
            },
            1,
        )

    def test_query_second_triplet(self):
        self.run_query(
            KnownGeneAAQuery,
            {
                "release": self.knowngene.release,
                "chromosome": self.knowngene.chromosome,
                "start": self.knowngene.start + 1,
                "end": self.knowngene.end + 1,
                "reference": "A",
            },
            1,
        )

    def test_query_third_triplet(self):
        self.run_query(
            KnownGeneAAQuery,
            {
                "release": self.knowngene.release,
                "chromosome": self.knowngene.chromosome,
                "start": self.knowngene.start + 2,
                "end": self.knowngene.start + 2,
                "reference": "A",
            },
            1,
        )

    def test_query_post_triplet(self):
        self.run_query(
            KnownGeneAAQuery,
            {
                "release": self.knowngene.release,
                "chromosome": self.knowngene.chromosome,
                "start": self.knowngene.start + 3,
                "end": self.knowngene.end + 3,
                "reference": "A",
            },
            0,
        )
