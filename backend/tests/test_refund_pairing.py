from app.engine.refunds import find_refund_pairs, is_merchant_match, normalize_merchant


def test_normalize_merchant_strips_suffix_tokens_and_case():
    assert normalize_merchant("Zalora Refund") == "ZALORA"
    assert normalize_merchant("ZALORA") == "ZALORA"


def test_is_merchant_match_handles_containment_either_direction():
    assert is_merchant_match("Zalora", "Zalora Refund")
    assert is_merchant_match("Zalora Refund", "Zalora")
    assert not is_merchant_match("Zalora", "Shopee Refund")


def tx(id_, date, amount, desc):
    return {"id": id_, "transaction_date": date, "amount": amount, "raw_description": desc}


def test_finds_dissimilar_but_containing_refund_pair():
    """The real mockup scenario: outflow 'Zalora' -89.90 paired with inflow
    'Zalora Refund' +89.90 a few days later - not identical strings."""
    txs = [
        tx(1, "2026-07-03", -89.90, "Zalora"),
        tx(2, "2026-07-09", 89.90, "Zalora Refund"),
    ]
    assert find_refund_pairs(txs) == [(1, 2)]


def test_does_not_pair_unrelated_transactions_with_matching_amounts():
    """Amount-only matching (the literal spec SQL) would false-positive here;
    merchant similarity must rule this out."""
    txs = [
        tx(1, "2026-05-10", -5.00, "BUS/MRT 865044496"),
        tx(2, "2026-05-11", 5.00, "PAYNOW-FAST Vincent Ang"),
    ]
    assert find_refund_pairs(txs) == []


def test_refund_must_be_on_or_after_original_date():
    txs = [
        tx(1, "2026-07-09", -89.90, "Zalora"),
        tx(2, "2026-07-03", 89.90, "Zalora Refund"),  # earlier than the charge
    ]
    assert find_refund_pairs(txs) == []


def test_already_paired_transactions_are_excluded():
    txs = [
        tx(1, "2026-07-03", -89.90, "Zalora"),
        tx(2, "2026-07-09", 89.90, "Zalora Refund"),
    ]
    assert find_refund_pairs(txs, already_paired_ids=frozenset({1})) == []


def test_picks_nearest_dated_candidate_when_multiple_match():
    txs = [
        tx(1, "2026-07-01", -20.00, "Shopee"),
        tx(2, "2026-07-15", 20.00, "Shopee Refund"),
        tx(3, "2026-07-05", 20.00, "Shopee Refund"),
    ]
    assert find_refund_pairs(txs) == [(1, 3)]
