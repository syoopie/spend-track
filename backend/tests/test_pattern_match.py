import pytest

from app.engine.pattern_match import SHORT_PATTERN_MAX_LEN, pattern_matches, uses_word_boundary


@pytest.mark.parametrize(
    "pattern, description, expected",
    [
        # Short pattern: alphanumeric word boundaries on both sides.
        ("NUS", "PAYMENT TO NUS BURSAR", True),
        ("NUS", "VENUS BEAUTY EAS SINGAPORE SGP", False),
        ("NTU", "NTUC FP HARBOURFRONT SINGAPORE", False),
        ("NTU", "NTU HALL 5 CANTEEN", True),
        ("ESSO", "ESSO STATION AMK", True),
        ("ESSO", "ESPRESSO BAR SINGAPORE", False),
        ("GV", "0236145 GV PLAZA SINGAPURA", True),
        ("GV", "NETS LOGVIEW SYSTEMS 12345678", False),
        ("CHEERS", "CHEERS - COLLEGE AVE WEST", True),
        ("CHEERS", "CHEERSFUL HOLDINGS PTE LTD", False),
        # A digit glued straight onto the pattern is still a boundary - a UOB
        # NETS line does exactly this with the terminal id.
        ("GV", "GV BUGIS18399883", True),
        ("M1", "M1 LIMITED GIRO", True),
        ("M1", "GYM1 FITNESS", False),
        # Long pattern: plain substring, so deliberate truncations still work.
        ("MCDONALD", "MCDONALDS AMK HUB", True),
        ("SWENSEN", "SWENSENS VIVOCITY", True),
        ("THRIVE FOOD", "THRIVE FOOD18399883", True),
    ],
)
def test_pattern_matches(pattern, description, expected):
    assert pattern_matches(pattern, description.upper()) is expected


def test_case_insensitive_and_strips_pattern():
    assert pattern_matches("  nus  ", "REGISTER AT NUS")
    assert not pattern_matches("   ", "ANYTHING")


def test_uses_word_boundary_only_for_short_alphanumeric_patterns():
    assert uses_word_boundary("NUS")
    assert uses_word_boundary("CHEERS")  # exactly SHORT_PATTERN_MAX_LEN
    assert not uses_word_boundary("MCDONALD")
    assert not uses_word_boundary("7-ELEVEN")  # punctuation -> substring
    assert not uses_word_boundary("YA KUN")  # space -> substring
    assert len("CHEERS") == SHORT_PATTERN_MAX_LEN
