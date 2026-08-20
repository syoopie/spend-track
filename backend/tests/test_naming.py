from app.engine.naming import extract_display_name


def test_strips_paynow_reference_noise():
    raw = "PAYNOW-FAST PIB2605050213183371 BOON HENG PTE. LTD. OTHR QL0TbuzeBASv00000002Sj"
    assert extract_display_name(raw) == "BOON HENG PTE. LTD."


def test_strips_nets_reference_noise():
    raw = "NETS Debit-Consumer HENG LI12306400 xxxxxx5678"
    assert "NETS" not in extract_display_name(raw)
    assert "HENG LI12306400" not in extract_display_name(raw)


def test_falls_back_to_original_when_everything_is_noise():
    assert extract_display_name("PAYNOW-FAST OTHR") == "PAYNOW-FAST OTHR"


def test_leaves_simple_merchant_names_untouched():
    assert extract_display_name("Zalora") == "Zalora"
    assert extract_display_name("Starbucks") == "Starbucks"
