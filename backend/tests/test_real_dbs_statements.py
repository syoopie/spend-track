"""Runs the DBS parser against real statements in the gitignored
`PDF Examples/DBS/` folder, if any are present.

The committed `PDF Examples (Sanitized)/DBS/` fixtures already exercise the
real layout (they were sanitized from two of these). This is the same guard
UOB has: drop more months into the local folder and they are checked the day
they land, against each statement's own printed total, with no filename
hardcoded. Skipped, not failed, on a fresh clone.
"""

import glob
import re

import pdfplumber
import pytest

from app.parsing.registry import detect_and_parse

SAMPLES = sorted(glob.glob("../PDF Examples/DBS/**/*.pdf", recursive=True))

pytestmark = pytest.mark.skipif(
    not SAMPLES,
    reason="No real DBS statements found locally (optional, gitignored PDF Examples/ folder)",
)


def _printed_section_totals(pdf) -> list[tuple[float, float, float]]:
    """Each `Total Balance Carried Forward in SGD: <out> <in> <balance>` row a
    consolidated statement prints for one of its accounts."""
    text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    totals = []
    for line in text.splitlines():
        if "Total Balance Carried Forward in SGD" in line:
            nums = [float(n.replace(",", "")) for n in re.findall(r"[\d,]+\.\d{2}", line)]
            if len(nums) == 3:
                totals.append(tuple(nums))
    return totals


@pytest.mark.parametrize("path", SAMPLES, ids=[p.replace("\\", "/").split("/")[-1] for p in SAMPLES])
def test_real_dbs_statement_parses_and_reconciles(path):
    with pdfplumber.open(path) as pdf:
        result = detect_and_parse(pdf.pages)
        printed = _printed_section_totals(pdf)

    assert result.bank_name == "DBS"
    assert result.accounts
    transactions = [t for acc in result.accounts for t in acc.transactions]
    assert transactions, "a real statement with no parsed transactions is a parser failure"

    # detect_and_parse already raises StatementReconciliationError on a
    # mismatch; this pins the totals explicitly against the printed rows.
    if printed:
        withdrawals = round(sum(-t.amount for t in transactions if t.amount < 0), 2)
        deposits = round(sum(t.amount for t in transactions if t.amount > 0), 2)
        assert withdrawals == round(sum(row[0] for row in printed), 2)
        assert deposits == round(sum(row[1] for row in printed), 2)
