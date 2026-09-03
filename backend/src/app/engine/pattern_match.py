"""How a categorization rule's `match_pattern` is tested against a bank
description - shared by the engine (engine/rules.py) and the "matches N
transactions" preview count (routers/rules.py) so the count can never be
optimistic about what a real rule would match.

A pattern matches by case-insensitive substring, with one exception: a
*short* pattern (<= SHORT_PATTERN_MAX_LEN characters, letters/digits only)
must fall on alphanumeric word boundaries. "NUS" is an Education rule; as a
bare substring it fires inside "VENUS BEAUTY" and inside "NTUC FAIRPRICE",
and "ESSO" fires inside "ESPRESSO". Every short acronym in the default bank
had this problem, and two of them ("GV ", "CHEERS ") carried a trailing
space to dodge it by hand.

The boundary is alphanumeric-only, not a full `\\b`: a UOB NETS line glues
the terminal id straight onto the surviving merchant text ("THRIVE
FOOD18399883"), so a pattern that ends where the digits begin still has to
match. What it must not match is a *letter* on either side - that's what
separates "GV PLAZA" (matches) from "LOGVIEW SYSTEMS" (does not).

Long patterns keep plain substring matching on purpose. Several default
entries are deliberate truncations that rely on it: "MCDONALD" catches both
"MCDONALD'S" and the apostrophe-less "MCDONALDS", "SWENSEN" catches
"SWENSENS".
"""

import re

SHORT_PATTERN_MAX_LEN = 6

_boundary_cache: dict[str, re.Pattern[str]] = {}


def _boundary_re(pattern_upper: str) -> re.Pattern[str]:
    cached = _boundary_cache.get(pattern_upper)
    if cached is None:
        cached = re.compile(r"(?<![A-Z0-9])" + re.escape(pattern_upper) + r"(?![A-Z0-9])")
        _boundary_cache[pattern_upper] = cached
    return cached


def uses_word_boundary(pattern: str) -> bool:
    p = pattern.strip().upper()
    return 0 < len(p) <= SHORT_PATTERN_MAX_LEN and p.isalnum()


def pattern_matches(pattern: str, description_upper: str) -> bool:
    """`description_upper` must already be upper-cased (call sites hold it as
    `desc_upper`)."""
    p = pattern.strip().upper()
    if not p:
        return False
    if uses_word_boundary(p):
        return _boundary_re(p).search(description_upper) is not None
    return p in description_upper
