import pytest

from pipeline.variants import NAME, classify, kind, phenotype_ids


def parse(name):
    m = NAME.match(name)
    return (m.group("c"), m.group("p")) if m else (None, None)


@pytest.mark.parametrize("name,vtype,expected", [
    ("NM_003165.6(STXBP1):c.1631G>A (p.Arg544Gln)", "single nucleotide variant", "missense"),
    ("NM_017547.4(FOXRED1):c.694C>T (p.Gln232Ter)", "single nucleotide variant", "nonsense"),
    ("NM_014855.3(AP5Z1):c.1413_1426del (p.Leu473fs)", "Deletion", "frameshift"),
    ("NM_003165.6(STXBP1):c.1110+1G>A", "single nucleotide variant", "splice"),
    ("NM_003165.6(STXBP1):c.37-12C>T", "single nucleotide variant", "intronic"),
    ("NM_003165.6(STXBP1):c.-1A>G", "single nucleotide variant", "untranslated"),
    ("NM_003165.6(STXBP1):c.30C>T (p.Ala10=)", "single nucleotide variant", "synonymous"),
    ("NM_003165.6(STXBP1):c.2T>C (p.Met1Thr)", "single nucleotide variant", "start"),
    ("NM_003165.6(STXBP1):c.34_36del (p.Met12del)", "Deletion", "inframe"),
    ("NM_003165.6(STXBP1):c.1A>G (p.Met1?)", "single nucleotide variant", "start"),
    ("NM_003165.6(STXBP1):c.100_102del (p.Lys34del)", "Deletion", "inframe"),
    ("NC_012920.1(MT-TL1):m.3243A>G", "single nucleotide variant", "mitochondrial"),
    ("GRCh38/hg38 9q34.11(chr9:127600000-127700000)x1", "copy number loss", "large"),
])
def test_variant_type_from_hgvs(name, vtype, expected):
    c, p = parse(name)
    assert kind(c, p, vtype) == expected


def test_classification_words():
    assert classify("Pathogenic/Likely pathogenic") == "P"
    assert classify("Likely pathogenic") == "LP"
    assert classify("Conflicting classifications of pathogenicity") == "C"
    assert classify("Uncertain significance") == "VUS"
    assert classify("Benign/Likely benign") == "B"
    assert classify("drug response") == "O"


def test_phenotype_ids_keep_alignment_with_names():
    ids = phenotype_ids("MONDO:MONDO:0013342,MedGen:C3150901,OMIM:613647,Orphanet:306511||MedGen:C3661900")
    assert ids == [{"MONDO:0013342", "OMIM:613647", "Orphanet:306511"}, set(), set()]
