"""Best-effort merchant/payee name extraction for the staging screen's
"save as rule" / "save as contact" quick-apply shortcuts.

The mockup's popover has no name/pattern input field, so those actions must
derive a sensible default straight from raw_description. Real UOB PayNow
lines look like "PAYNOW-FAST PIB2605050213183371 BOON HENG PTE. LTD. OTHR
QL0TbuzeBASv00000002Sj" - the reference-number tokens are noise; this strips
them so the default is "BOON HENG PTE. LTD." instead of the full string.
"""

import re

NOISE_TOKENS = {
    "PAYNOW-FAST", "PAYNOW", "OTHR", "NETS", "DEBIT-CONSUMER", "TRANSFER",
    "GIRO", "INWARD", "DR", "CR", "FAST", "-",
}
REFCODE_RE = re.compile(r"^[A-Za-z0-9]{8,}$")


def extract_display_name(raw_description: str) -> str:
    kept = []
    for token in raw_description.split():
        upper = token.upper()
        if upper in NOISE_TOKENS:
            continue
        if REFCODE_RE.match(token) and any(c.isdigit() for c in token):
            continue
        kept.append(token)
    name = " ".join(kept).strip()
    return name or raw_description.strip()
