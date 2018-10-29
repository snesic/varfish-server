"""This module contains the code for file export"""

import datetime
import json

from datetime import timedelta
from tempfile import NamedTemporaryFile

from django.utils import timezone
import xlsxwriter
import vcfpy

from .models import ExportFileJobResult
from .views import FilterQueryRunner

#: Constant that determines how many days generated files should stay.  Note for the actual removal, a separate
#: Celery job must be ran.
EXPIRY_DAYS = 14


def to_str(val):
    if val is None:
        return "."
    elif isinstance(val, set):
        return ";".join(sorted(map(to_str, val)))
    elif isinstance(val, list):
        return ";".join(map(to_str, val))
    else:
        return str(val)


#: Names of the fixed header columns: ``(id/name, title, type)``.
HEADER_FIXED = (
    ("chromosome", "Chromosome", str),
    ("position", "Position", int),
    ("reference", "Reference bases", str),
    ("alternative", "Alternative bases", str),
    ("var_type", "Variant types", list),
    ("rsid", "dbSNP ID", str),
    ("in_clinvar", "In Clinvar?", bool),
    ("exac_frequency", "Max. freq. in ExAC", float),
    ("gnomad_exomes_frequency", "Max. freq. in gnomAD exomes", float),
    ("gnomad_genomes_frequency", "Max. freq. in gnomAD gnomes", float),
    ("thousand_genomes_frequency", "Freq. in thousand genomes", float),
    ("exac_homozygous", "Homozygous counts in ExAC", int),
    ("gnomad_exomes_homozygous", "Homozygous counts in gnomAD exomes", int),
    ("gnomad_genomes_homozygous", "Homozygous counts in gnomAD genomes", int),
    ("thousand_genomes_homozygous", "Homozygous counts in Thousand Genomes", int),
    # TODO: heterozygous counts
    ("symbol", "Gene Symbol", str),
    ("gene_id", "Gene ID", str),
    ("effect", "Most pathogenic variant effect", str),
    ("hgvs_p", "Protein HGVS change", str),
    ("hgvs_c", "Nucleotide HGVS change", str),
    ("known_gene_aa", "100 Vertebrate AA conservation", str),
)


#: Per-sample headers.
HEADER_FORMAT = (
    ("gt", "Genotype", str),
    ("gq", "Gt. Quality", str),
    ("ad", "Alternative depth", int),
    ("dp", "Total depth", int),
    ("aaf", "Alternate allele fraction", float),
)

#: Contig lenghts for GRCh37
CONTIGS_GRCH37 = (
    ("1", 249250621),
    ("2", 243199373),
    ("3", 198022430),
    ("4", 191154276),
    ("5", 180915260),
    ("6", 171115067),
    ("7", 159138663),
    ("8", 146364022),
    ("9", 141213431),
    ("10", 135534747),
    ("11", 135006516),
    ("12", 133851895),
    ("13", 115169878),
    ("14", 107349540),
    ("15", 102531392),
    ("16", 90354753),
    ("17", 81195210),
    ("18", 78077248),
    ("19", 59128983),
    ("20", 63025520),
    ("21", 48129895),
    ("22", 51304566),
    ("X", 155270560),
    ("Y", 59373566),
    ("MT", 16569),
)


class CaseExporterBase:
    """Base class for export of (filtered) case data.
    """

    def __init__(self, job):
        #: The ``ExportFileBgJob`` to use for obtaining case and query arguments.
        self.job = job
        #: The query arguments.
        self.query_args = json.loads(job.query_args)
        #: The named temporary file object to use for file handling.
        self.tmp_file = None
        #: The wrapper for running queries.
        self.query_runner = FilterQueryRunner(job.case, self.query_args, include_conservation=True)
        #: The name of the selected members.
        self.members = list(self._yield_members())
        #: The column information.
        self.columns = list(self._yield_columns(self.members))

    def _yield_members(self):
        """Get list of selected members."""
        for m in self.query_runner.pedigree:
            if self.query_args.get("%s_export" % m["patient"], False):
                yield m["patient"]

    def _yield_columns(self, members):
        """Yield column information."""
        for lst in HEADER_FIXED:
            yield dict(zip(("name", "title", "type", "fixed"), list(lst) + [True]))
        for member in members:
            for name, title, type_ in HEADER_FORMAT:
                yield {
                    "name": "%s.%s" % (member, name),
                    "title": "%s %s" % (member, title),
                    "type": type_,
                    "fixed": False,
                }

    def _yield_smallvars(self):
        """Use this for yielding the resulting small variants one-by-one."""
        prev_chrom = None
        self.job.add_log_entry("Executing database query...")
        result = self.query_runner.run()
        self.job.add_log_entry("Writing output file...")
        for small_var in result:
            if small_var.chromosome != prev_chrom:
                self.job.add_log_entry("Now on chromosome chr{}".format(small_var.chromosome))
                prev_chrom = small_var.chromosome
            yield small_var

    def _get_named_temporary_file_args(self):
        return {}

    def __enter__(self):
        self.tmp_file = NamedTemporaryFile(**self._get_named_temporary_file_args())
        self.tmp_file.__enter__()
        self._open()
        return self

    def __exit__(self, exc, value, tb):
        result = self.tmp_file.__exit__(exc, value, tb)
        self._close()
        self.tmp_file = None
        return result

    def generate(self):
        """Perform data generation and return all data."""
        self._write_leading()
        self._write_variants()
        self._write_trailing()
        #: Rewind temporary file to beginning, read everything and return it.
        self.tmp_file.seek(0)
        return self.tmp_file.read()

    def _open(self):
        """Override with action on opening the file."""

    def _close(self):
        """Override with action on closing the file."""

    def _write_leading(self):
        """Write out anything before the the per-variant data.

        Override in sub class.
        """

    def _write_variants(self):
        """Write out the actual data, override called functions rather than this one.
        """
        self._begin_write_variants()
        self._write_variants_header()
        self._write_variants_data()
        self._end_write_variants()

    def _begin_write_variants(self):
        """Fill with actions to execute before writing variants."""

    def _write_variants_header(self):
        """Fill with actions to write the variant header."""

    def _write_variants_data(self):
        """Fill with actions to write the variant data."""

    def _end_write_variants(self):
        """Fill with actions to execute after writing variants."""

    def _write_trailing(self):
        """Write out anything after the per-variant data.

        Override in sub class.
        """


class CaseExporterTsv(CaseExporterBase):
    """Export a case to TSV format."""

    def _write_variants_header(self):
        """Fill with actions to write the variant header."""
        line = "\t".join([x["title"] for x in self.columns]) + "\n"
        self.tmp_file.write(line.encode("utf-8"))

    def _write_variants_data(self):
        """Fill with actions to write the variant data."""
        for small_var in self._yield_smallvars():
            row = []
            for column in self.columns:
                if column["name"] == "chromosome":
                    row.append("chr" + getattr(small_var, "chromosome"))
                elif column["fixed"]:
                    row.append(getattr(small_var, column["name"]))
                else:
                    member, field = column["name"].rsplit(".", 1)
                    if field == "aaf":
                        ad = small_var.ad.get(member, 0)
                        dp = small_var.dp.get(member, 0)
                        aaf = ad / dp if dp != 0 else 0
                        row.append(str(aaf))
                    else:
                        row.append(to_str(getattr(small_var, field, {}).get(member, ".")))
            line = "\t".join(map(lambda s: to_str(s), row)) + "\n"
            self.tmp_file.write(line.encode("utf-8"))


class CaseExporterXlsx(CaseExporterBase):
    """Export a case to Excel (XLSX) format."""

    def __init__(self, job):
        super().__init__(job)
        #: The ``Workbook`` object to use for writing.
        self.workbook = None
        #: The sheet with the variants.
        self.variant_sheet = None
        #: The sheet with the meta data.
        self.meta_data_sheet = None

    def _get_named_temporary_file_args(self):
        return {"suffix": ".xlsx"}

    def _open(self):
        self.workbook = xlsxwriter.Workbook(self.tmp_file.name)
        # setup formats
        self.header_format = self.workbook.add_format({"bold": True})
        # setup sheets
        self.variant_sheet = self.workbook.add_worksheet("Variants")
        self.meta_data_sheet = self.workbook.add_worksheet("Metadata")

    def _end_write_variants(self):
        self.workbook.close()

    @staticmethod
    def _unblank(x):
        if x is None:
            return "None"
        elif x is True:
            return "True"
        elif x is False:
            return "False"
        elif isinstance(x, str) and not x:
            return "."
        else:
            return x

    def _write_leading(self):
        # Write out meta data sheet.
        self.meta_data_sheet.write_column(
            0,
            0,
            ["Case", "", "Date", "", "Versions", "", "Settings"] + list(self.query_args.keys()),
            self.header_format,
        )
        self.meta_data_sheet.write_column(
            0,
            1,
            [
                "TODO: URL to case",
                "",
                str(datetime.datetime.now()),
                "",
                "TODO: Write out software and all database versions etc." "",
                "",
                "",
            ]
            + list(map(self.__class__._unblank, self.query_args.values())),
        )

    def _write_variants_header(self):
        """Fill with actions to write the variant header."""
        self.variant_sheet.write_row(0, 0, [x["title"] for x in self.columns], self.header_format)

    def _write_variants_data(self):
        """Fill with actions to write the variant data."""
        # Write data to Excel sheet
        for num_rows, small_var in enumerate(self._yield_smallvars()):
            row = []
            for column in self.columns:
                if column["name"] == "chromosome":
                    row.append("chr" + getattr(small_var, "chromosome"))
                elif column["fixed"]:
                    row.append(getattr(small_var, column["name"]))
                else:
                    member, field = column["name"].rsplit(".", 1)
                    if field == "aaf":
                        ad = small_var.ad.get(member, 0)
                        dp = small_var.dp.get(member, 0)
                        aaf = ad / dp if dp != 0 else 0.0
                        row.append(aaf)
                    else:
                        row.append(getattr(small_var, field, {}).get(member, "."))
                if isinstance(row[-1], set):
                    row[-1] = to_str(row[-1])
            self.variant_sheet.write_row(1 + num_rows, 0, row)
        # Freeze first row and first four columns and setup auto-filter.
        self.variant_sheet.freeze_panes(1, 4)
        self.variant_sheet.autofilter(0, 0, num_rows + 1, len(self.columns))


class CaseExporterVcf(CaseExporterBase):
    """Export a case to VCF format."""

    def __init__(self, job):
        super().__init__(job)
        #: The ``vcfpy.Writer`` to use for writing the VCF file.
        self.vcf_writer = None

    def _get_named_temporary_file_args(self):
        return {"suffix": ".vcf.gz"}

    def _open(self):
        # Setup header
        lines = [
            vcfpy.HeaderLine("fileformat", "VCFv4.2"),
            vcfpy.FormatHeaderLine.from_mapping(
                {
                    "ID": "AD",
                    "Number": "R",
                    "Type": "Integer",
                    "Description": "Allelic depths for the ref and alt alleles in the order listed",
                }
            ),
            vcfpy.FormatHeaderLine.from_mapping(
                {
                    "ID": "DP",
                    "Number": "1",
                    "Type": "Integer",
                    "Description": "Approximate read depth at the locus",
                }
            ),
            vcfpy.FormatHeaderLine.from_mapping(
                {
                    "ID": "GQ",
                    "Number": "1",
                    "Type": "Integer",
                    "Description": "Phred-scaled genotype quality",
                }
            ),
            vcfpy.FormatHeaderLine.from_mapping(
                {"ID": "GT", "Number": "1", "Type": "String", "Description": "Genotype"}
            ),
        ]
        # Add header lines for contigs.
        # TODO: switch based on release in case
        for name, length in CONTIGS_GRCH37:
            lines.append(vcfpy.ContigHeaderLine.from_mapping({"ID": name, "length": length}))
        header = vcfpy.Header(lines=lines, samples=vcfpy.SamplesInfos(self.members))
        # Open VCF writer
        self.vcf_writer = vcfpy.Writer.from_path(self.tmp_file.name, header)

    def _end_write_variants(self):
        self.vcf_writer.close()

    def _write_variants_data(self):
        for small_var in self._yield_smallvars():
            # Get variant type
            if len(small_var.reference) == 1 and len(small_var.alternative) == 1:
                var_type = vcfpy.SNV
            elif len(small_var.reference) == len(small_var.alternative):
                var_type = vcfpy.MNV
            else:
                var_type = vcfpy.INDEL
            # Build list of calls
            calls = [
                vcfpy.Call(
                    member,
                    {
                        "GT": small_var.gt.get(member, "./."),
                        "GQ": small_var.gq.get(member, None),
                        "AD": [small_var.ad.get(member, None)],
                        "DP": small_var.dp.get(member, None),
                    },
                )
                for member in self.members
            ]
            # Construct and write out the VCF ``Record`` object
            self.vcf_writer.write_record(
                vcfpy.Record(
                    small_var.chromosome,
                    small_var.position,
                    [],
                    small_var.reference,
                    [vcfpy.Substitution(var_type, small_var.alternative)],
                    None,
                    [],
                    {},
                    ["GT", "GQ", "AD", "DP"],
                    calls,
                )
            )


#: Dict mapping file type to writer class.
EXPORTERS = {"tsv": CaseExporterTsv, "vcf": CaseExporterVcf, "xlsx": CaseExporterXlsx}


def export_case(job):
    """Export a ``Case`` object, store result in a new ``ExportFileJobResult``."""
    job.mark_start()
    try:
        klass = EXPORTERS[job.file_type]
        with klass(job) as exporter:
            ExportFileJobResult.objects.create(
                job=job,
                expiry_time=timezone.now() + timedelta(days=EXPIRY_DAYS),
                payload=exporter.generate(),
            )
    except Exception as e:
        job.mark_error(e)
        raise
    else:
        job.mark_success()