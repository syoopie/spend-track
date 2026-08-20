from app.engine.fingerprint import (
    clean_description,
    compute_daily_sequence_indices,
    compute_fingerprint,
)
from app.parsing.base import ParsedTransaction


def test_clean_description_normalizes_whitespace_and_case():
    assert clean_description("  Grab   Ride \n Home  ") == "GRAB RIDE HOME"


def test_daily_sequence_indices_disambiguate_identical_rows():
    txs = [
        ParsedTransaction("2026-05-05", "BUS/MRT", -1.59),
        ParsedTransaction("2026-05-05", "BUS/MRT", -1.59),  # identical -> seq 1
        ParsedTransaction("2026-05-05", "BUS/MRT", -1.60),  # different amount -> seq 0
        ParsedTransaction("2026-05-06", "BUS/MRT", -1.59),  # different date -> seq 0
    ]
    assert compute_daily_sequence_indices(txs) == [0, 1, 0, 0]


def test_fingerprint_deterministic_and_sensitive_to_each_component():
    base = compute_fingerprint("acc1", "2026-05-05", -1.59, "BUS/MRT", 0)
    assert base == compute_fingerprint("acc1", "2026-05-05", -1.59, "BUS/MRT", 0)
    assert base != compute_fingerprint("acc2", "2026-05-05", -1.59, "BUS/MRT", 0)
    assert base != compute_fingerprint("acc1", "2026-05-06", -1.59, "BUS/MRT", 0)
    assert base != compute_fingerprint("acc1", "2026-05-05", -1.60, "BUS/MRT", 0)
    assert base != compute_fingerprint("acc1", "2026-05-05", -1.59, "GRAB", 0)
    assert base != compute_fingerprint("acc1", "2026-05-05", -1.59, "BUS/MRT", 1)


def test_reuploading_same_statement_produces_identical_fingerprints():
    """Duplicate detection depends on this: re-parsing the same file twice
    must yield the exact same fingerprint sequence."""
    txs = [
        ParsedTransaction("2026-05-05", "Grab", -24.80),
        ParsedTransaction("2026-05-05", "Grab", -24.80),
    ]
    seq_a = compute_daily_sequence_indices(txs)
    seq_b = compute_daily_sequence_indices(txs)
    assert seq_a == seq_b
    fps_a = [
        compute_fingerprint("acc1", t.transaction_date, t.amount, clean_description(t.raw_description), i)
        for t, i in zip(txs, seq_a)
    ]
    fps_b = [
        compute_fingerprint("acc1", t.transaction_date, t.amount, clean_description(t.raw_description), i)
        for t, i in zip(txs, seq_b)
    ]
    assert fps_a == fps_b
    assert len(set(fps_a)) == 2  # the two identical rows still get distinct fingerprints
