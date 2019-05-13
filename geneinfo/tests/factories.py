"""Factory Boy factory classes for ``geneinfo``."""

import factory

from ..models import Hgnc, Hpo, Mim2geneMedgen, Acmg, RefseqToHgnc


class RefseqToHgncFactory(factory.django.DjangoModelFactory):
    """Factory for the ``RefseqToHgnc`` model."""

    class Meta:
        model = RefseqToHgnc

    entrez_id = factory.Sequence(lambda n: str(n))
    hgnc_id = factory.Sequence(lambda n: "HGNC:%d" % n)


class HgncFactory(factory.django.DjangoModelFactory):
    """Factory for the ``Hgnc`` model."""

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Create corresponding RefseqToHgnc object to the current Hgnc object."""
        manager = cls._get_manager(model_class)
        RefseqToHgncFactory(entrez_id=kwargs["entrez_id"])
        return manager.create(*args, **kwargs)

    class Meta:
        model = Hgnc

    hgnc_id = factory.Sequence(lambda n: "HGNC:%d" % n)
    symbol = factory.Sequence(lambda n: "SYMBOL%d" % n)
    name = factory.Sequence(lambda n: "Gene name %d" % n)
    ensembl_gene_id = factory.Sequence(lambda n: "ENSG%d" % n)
    entrez_id = factory.Sequence(lambda n: str(n))


class HpoFactory(factory.django.DjangoModelFactory):
    """Factory for the ``Hpo`` model."""

    class Meta:
        model = Hpo

    database_id = factory.Sequence(lambda n: "OMIM:%d" % n)
    hpo_id = factory.Sequence(lambda n: "HP:%07d" % n)


class Mim2geneMedgenFactory(factory.django.DjangoModelFactory):
    """Factory for the ``Mim2geneMedgen`` model."""

    class Meta:
        model = Mim2geneMedgen

    omim_id = factory.Sequence(lambda n: n)
    entrez_id = factory.Sequence(lambda n: str(n))


class AcmgFactory(factory.django.DjangoModelFactory):
    """Factory for the ``Acmg`` model."""

    class Meta:
        model = Acmg

    entrez_id = factory.Sequence(lambda n: str(n))
    ensembl_gene_id = factory.Sequence(lambda n: "ENSG%d" % n)
    symbol = factory.Sequence(lambda n: "SYMBOL%d" % n)
