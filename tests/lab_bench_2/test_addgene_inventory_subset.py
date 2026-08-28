from lab_bench_2.addgene_inventory_subset import (
    ALLOWED_GOTCHA_KINDS,
    Gotcha,
    SubsetPlasmid,
    annotate_inventory_with_subset,
    plasmid_ids,
    subset_plasmids,
    validate_subset,
)


def test_catalog_covers_hosts_and_cited_gotchas() -> None:
    catalog = subset_plasmids()
    ids = plasmid_ids(catalog)
    assert len(ids) == len(set(ids))
    assert 10878 in ids
    assert 26973 in ids
    assert 128034 in ids
    assert 105539 in ids
    assert 28306 in ids
    assert 195714 in ids
    assert 42335 in ids
    hosts = {host for entry in catalog for host in entry.hosts}
    for required in (
        "mammalian",
        "bacterial",
        "yeast",
        "plant",
        "worm",
        "insect",
        "viral",
    ):
        assert required in hosts
    kinds = {gotcha.kind for entry in catalog for gotcha in entry.gotchas}
    for required_kind in (
        "itr_deletion",
        "multiple_full_maps",
        "paper_vs_sequence_typo",
        "splice_motif",
        "flex_leak",
        "enzyme_site_mixup",
        "nickase_vs_nuclease",
        "stuffer_vs_empty",
        "leftover_type_iis",
        "inverted_orf",
    ):
        assert required_kind in kinds
    assert kinds <= ALLOWED_GOTCHA_KINDS
    dual_map = next(entry for entry in catalog if entry.plasmid_id == 26973)
    assert dual_map.sequence_source == "all"
    fragments = {entry.assembly_fragments for entry in catalog}
    assert 2 in fragments
    assert 8 in fragments
    assert 24 in fragments
    methods = {entry.assembly_method for entry in catalog}
    assert methods == {
        "restriction",
        "gibson",
        "oligo_gg",
        "golden_gate",
        "hierarchical_gg",
    }


def test_validate_subset_rejects_duplicate_ids() -> None:
    entry = SubsetPlasmid(
        1,
        "demo",
        "role",
        ("bacterial",),
        "gibson",
        2,
        "2-fragment Gibson",
        gotchas=(Gotcha("itr_deletion", "summary", "citation", "https://example.com"),),
    )
    try:
        validate_subset((entry, entry))
    except ValueError as exc:
        assert "duplicate plasmid id" in str(exc)
    else:
        raise AssertionError("expected duplicate catalog ids to fail")


def test_annotate_inventory_flags_conflicting_full_maps() -> None:
    inventory = {
        "summary": {
            "files_with_no_part_features": [],
            "files_with_no_primers": ["a.gbk"],
        },
        "indexes": {"duplicate_sequences": {}},
    }
    records = [
        {
            "plasmid_id": 26973,
            "filename": "addgene-plasmid-26973-sequence-1.gbk",
            "sequence_id": "1",
            "source_bucket": "public_addgene_full_sequences",
            "sha256": "aaa",
        },
        {
            "plasmid_id": 26973,
            "filename": "addgene-plasmid-26973-sequence-2.gbk",
            "sequence_id": "2",
            "source_bucket": "public_user_full_sequences",
            "sha256": "bbb",
        },
        {
            "plasmid_id": 10878,
            "filename": "addgene-plasmid-10878-sequence-3.gbk",
            "sequence_id": "3",
            "source_bucket": "public_addgene_full_sequences",
            "sha256": "ccc",
        },
    ]
    combined = annotate_inventory_with_subset(inventory, records)
    conflicts = combined["gotcha_index"]["conflicting_full_maps"]
    assert len(conflicts) == 1
    assert conflicts[0]["plasmid_id"] == 26973
    assert combined["gotcha_index"]["files_with_no_primers"] == ["a.gbk"]
