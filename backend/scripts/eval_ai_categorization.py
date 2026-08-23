"""Live quality evaluation for the AI-categorization prompt/pipeline
(engine/ai_providers/) against a real local Ollama model.

This is deliberately NOT a pytest test. tests/test_ai_providers.py already
covers parse_suggestions()/each adapter's HTTP handling deterministically
via monkeypatched httpx - that answers "does the plumbing work", not "are
the model's actual categorization/label/rule_pattern picks any good", which
needs a real model and is inherently non-deterministic (a small local model
can flip an answer between runs). This script answers the second question:
it sends a large, hand-curated set of realistic Singapore bank/card
transaction descriptions through the real prompt -> real Ollama call ->
real parse_suggestions() pipeline (engine/ai_providers/ollama.py, unmodified)
and scores what comes back, so prompt changes can be judged by a number
instead of eyeballing a handful of manual uploads.

Run with: uv run python scripts/eval_ai_categorization.py
Options:
  --model NAME       Ollama model tag to use (default: first model `ollama list` reports)
  --base-url URL     Ollama base URL (default: http://localhost:11434)
  --mode single|batch|both   how candidates are grouped into categorize() calls (default: both)
  --chunk-size N      when --mode batch, split into chunks of N candidates instead of one giant call
  --verbose            print every case's raw suggestion, not just failures
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from app import db, repo  # noqa: E402
from app.engine.ai_providers.base import AiCandidate, AiProviderResponseError, AiProviderUnavailableError  # noqa: E402
from app.engine.ai_providers.ollama import OllamaProvider  # noqa: E402

# --- test cases --------------------------------------------------------------
#
# The prompt text itself lives in app/engine/ai_providers/prompts.py.
#
# raw_description strings mirror the actual joined-column format the UOB
# parser produces (see parsing/uob/{account,card}_statement.py - multiple
# physical description lines get " ".join()'d into one string), not
# hand-cleaned merchant names. PayNow-marked rows are deliberately excluded:
# routers/statements.py::_ai_candidates only sends rows where matched_label
# is None, and every PayNow row gets a non-None matched_label from
# engine/paynow.py regardless of whether it resolved to a contact - so a
# PayNow line is never actually a candidate in production, and including one
# here would test a code path the AI never sees.


@dataclass
class Case:
    raw_description: str
    amount: float
    direction: str  # "outflow" | "inflow"
    expect: str  # "categorize" | "abstain" | "either"
    expect_category: str | None = None  # only checked when expect == "categorize"
    label_contains: str | None = None  # case-insensitive substring expected in display_label
    notes: str = ""


# Noise tokens that must never survive into a display_label - see
# ai_providers/base.py::build_prompt's own worked example.
_LABEL_NOISE_RE = re.compile(
    r"\b(NETS|DEBIT-CONSUMER|POS|PAYNOW|GIRO|OTHR|INWARD|OUTWARD|PURCHASE|TRANSFER)\b|"
    r"x{4,}\d*|\d{4,}",
    re.IGNORECASE,
)

CASES: list[Case] = [
    # --- Food & Drink (outflow), clean single-line noise ----------------
    Case('NETS Debit-Consumer STARBUCKS 00000011 xxxxxx0000', -7.80, "outflow", "categorize",
         "Food & Drink", label_contains="Starbucks"),
    Case('NETS Debit-Consumer MCDONALDS JURONG PT 00000022 xxxxxx0000', -11.20, "outflow", "categorize",
         "Food & Drink", label_contains="Mcdonald"),
    Case('NETS Debit-Consumer KOI THE ORCHARD 00000033 xxxxxx0000', -5.40, "outflow", "categorize",
         "Food & Drink", label_contains="Koi"),
    Case('NETS Debit-Consumer DIN TAI FUNG PARAGON 00000044 xxxxxx0000', -68.00, "outflow", "categorize",
         "Food & Drink", label_contains="Din Tai Fung"),
    Case('NETS Debit-Consumer TOAST BOX AMK HUB 00000055 xxxxxx0000', -6.20, "outflow", "categorize",
         "Food & Drink", label_contains="Toast Box"),
    # digit glued directly onto the name, no space - the CLAUDE.md worked example
    Case('NETS Debit-Consumer HENG LI12306400 xxxxxx5678', -4.50, "outflow", "either",
         label_contains="Heng Li", notes="digit-glued name, from prompts.py::build_prompt's own worked example"),
    Case('NETS Debit-Consumer OLD CHANG KEE TAMPINES98123 xxxxxx1122', -3.20, "outflow", "either",
         label_contains="Old Chang Kee", notes="digit-glued name"),

    # --- Groceries (outflow) ---------------------------------------------
    Case('NETS Debit-Consumer NTUC FAIRPRICE 00000010 xxxxxx0000', -32.50, "outflow", "categorize",
         "Groceries", label_contains="Fairprice"),
    Case('NETS Debit-Consumer SHENG SIONG 00000014 xxxxxx0000', -41.20, "outflow", "categorize",
         "Groceries", label_contains="Sheng Siong"),
    Case('NETS Debit-Consumer COLD STORAGE 00000013 xxxxxx0000', -58.40, "outflow", "categorize",
         "Groceries", label_contains="Cold Storage"),
    Case('NETS Debit-Consumer GIANT HYPERMARKET TAMPINES 00000099 xxxxxx0000', -76.10, "outflow", "categorize",
         "Groceries", label_contains="Giant"),

    # --- Shopping (outflow) -------------------------------------------------
    Case('NETS Debit-Consumer UNIQLO ION ORCHARD 00000066 xxxxxx0000', -49.90, "outflow", "categorize",
         "Shopping", label_contains="Uniqlo"),
    Case('SHOPEE *ORDER 2401011234567 SINGAPORE SG', -25.00, "outflow", "categorize",
         "Shopping", label_contains="Shopee"),
    Case('LAZADA.SG SINGAPORE SG', -33.40, "outflow", "categorize", "Shopping", label_contains="Lazada"),
    Case('TAOBAO.COM HANGZHOU CN', -18.60, "outflow", "categorize", "Shopping", label_contains="Taobao"),
    Case('ZALORA SINGAPORE PTE LTD SG', -55.00, "outflow", "categorize", "Shopping", label_contains="Zalora"),

    # --- Transport (outflow) -------------------------------------------------
    Case('GRAB* A-1234567890AB SINGAPORE SG', -14.30, "outflow", "categorize", "Transport", label_contains="Grab"),
    Case('NETS Debit-Consumer COMFORTDELGRO TAXI 00000077 xxxxxx0000', -16.80, "outflow", "categorize",
         "Transport", label_contains="Comfortdelgro"),
    Case('GOJEK SINGAPORE SG', -9.90, "outflow", "categorize", "Transport", label_contains="Gojek"),
    Case('NETS Debit-Consumer SMRT EZ-LINK TOPUP 00000088 xxxxxx0000', -30.00, "outflow", "categorize",
         "Transport", label_contains="Ez-Link", notes="acceptable if model says SMRT instead"),

    # --- Entertainment (outflow) ---------------------------------------------
    Case('NETFLIX.COM SINGAPORE SG', -20.98, "outflow", "categorize", "Entertainment", label_contains="Netflix"),
    Case('SPOTIFY SG SINGAPORE SG', -11.98, "outflow", "categorize", "Entertainment", label_contains="Spotify"),
    Case('GOLDEN VILLAGE VIVOCITY SG', -32.00, "outflow", "categorize", "Entertainment",
         label_contains="Golden Village"),
    Case('STEAMGAMES.COM 425-1234567 WA', -59.90, "outflow", "categorize", "Entertainment", label_contains="Steam"),

    # --- Healthcare / Beauty (outflow, genuinely ambiguous merchant) --------
    Case('NETS Debit-Consumer GUARDIAN PHARMACY 00000111 xxxxxx0000', -22.50, "outflow", "categorize",
         label_contains="Guardian", notes="Guardian sells both pharmacy + beauty goods; accept either category"),
    Case('NETS Debit-Consumer RAFFLES MEDICAL CLINIC 00000122 xxxxxx0000', -85.00, "outflow", "categorize",
         "Healthcare", label_contains="Raffles Medical"),
    Case('NETS Debit-Consumer SEPHORA ION 00000133 xxxxxx0000', -64.00, "outflow", "categorize",
         "Beauty", label_contains="Sephora"),

    # --- Home (outflow) -------------------------------------------------------
    Case('NETS Debit-Consumer IKEA TAMPINES 00000144 xxxxxx0000', -210.00, "outflow", "categorize",
         "Home", label_contains="Ikea"),
    Case('NETS Debit-Consumer COURTS MEGASTORE 00000155 xxxxxx0000', -899.00, "outflow", "categorize",
         "Home", label_contains="Courts"),

    # --- Bills & Fees (outflow) ------------------------------------------------
    Case('GIRO SINGTEL MOBILE BILL 91234567 00000166', -45.00, "outflow", "categorize",
         "Bills & Fees", label_contains="Singtel"),
    Case('GIRO STARHUB CABLEVISION 00000177', -58.90, "outflow", "categorize",
         "Bills & Fees", label_contains="Starhub"),
    Case('GIRO SP GROUP UTILITIES 00000188', -120.30, "outflow", "categorize",
         "Bills & Fees", label_contains="SP Group"),
    Case('Inward DR - GIRO TAXS S1234567B IRAS Property Tax', -310.00, "outflow", "categorize",
         "Bills & Fees", label_contains="Iras",
         notes="identifiable payee (IRAS) despite generic GIRO/TAXS boilerplate - should NOT abstain"),

    # --- Education (outflow) -----------------------------------------------
    Case('NETS Debit-Consumer NTUC LEARNINGHUB 00000199 xxxxxx0000', -450.00, "outflow", "categorize",
         "Education", label_contains="Learninghub"),
    Case('NETS Debit-Consumer BRITISH COUNCIL SG 00000200 xxxxxx0000', -680.00, "outflow", "categorize",
         "Education", label_contains="British Council"),

    # --- Sports & Hobbies (outflow) -----------------------------------------
    Case('NETS Debit-Consumer DECATHLON SG 00000211 xxxxxx0000', -75.00, "outflow", "categorize",
         "Sports & Hobbies", label_contains="Decathlon"),
    Case('GIRO PURE FITNESS MEMBERSHIP 00000222', -180.00, "outflow", "categorize",
         "Sports & Hobbies", label_contains="Pure Fitness"),

    # --- Investing (outflow) -------------------------------------------------
    Case('TIGER BROKERS SG PTE LTD SINGAPORE SG', -1000.00, "outflow", "categorize",
         "Investing", label_contains="Tiger Brokers"),
    Case('MOOMOO SG FUNDING SINGAPORE SG', -500.00, "outflow", "categorize", "Investing", label_contains="Moomoo"),

    # --- Salary / income (inflow) --------------------------------------------
    Case('Inward CR - GIRO SALA Salary Payment SAMPLE EMPLOYER PTE LTD SALARY', 3200.00, "inflow", "categorize",
         "Salary", label_contains="Sample Employer"),
    Case('Inward CR - GIRO SALA Salary Payment ACME ENGINEERING PTE LTD SALARY', 5400.00, "inflow", "categorize",
         "Salary", label_contains="Acme Engineering"),

    # --- Refunds & Reimbursements (inflow) - same brand as an outflow case,
    # to check the model doesn't just pattern-match "Shopee -> Shopping"
    # regardless of direction ---------------------------------------------
    Case('SHOPEE *REFUND ORDER 2401011234567 SINGAPORE SG', 25.00, "inflow", "categorize",
         "Refunds & Reimbursements", label_contains="Shopee"),
    Case('GRAB* REFUND TRIP CANCELLED SINGAPORE SG', 14.30, "inflow", "categorize",
         "Refunds & Reimbursements", label_contains="Grab"),

    # --- Investment Income (inflow) ------------------------------------------
    Case('DIVIDEND CDP SINGAPORE PTE LTD SG', 88.20, "inflow", "categorize",
         "Investment Income", label_contains="Cdp"),
    Case('TIGER BROKERS SG DIVIDEND CREDIT SINGAPORE SG', 42.10, "inflow", "categorize",
         "Investment Income", label_contains="Tiger Brokers"),

    # --- abstain: generic transfer/bill-payment with no identifiable payee --
    Case('PAYMT THRU E-BANK/HOMEB/CYBERB', -200.00, "outflow", "abstain",
         notes="no payee at all - could be a credit card bill payment; must not guess a spending category"),
    Case('GIRO', -60.00, "outflow", "abstain", notes="bare GIRO, no payee"),
    Case('FAST PAYMENT REF0000000098765', -150.00, "outflow", "abstain", notes="no payee, only a reference number"),
    Case('IBG PAYMENT REF 2024010112345', -75.50, "outflow", "abstain", notes="no payee, only a reference number"),
    Case('FUNDS TRANSFER', -1000.00, "outflow", "abstain", notes="bare funds transfer, no payee"),
    Case('Inward CR - GIRO FAST PAYMENT REF0000000012345', 300.00, "inflow", "abstain",
         notes="inflow-side generic transfer, no payee"),
    Case('INCOMING TELEGRAPHIC TRANSFER REF9988776655', 1500.00, "inflow", "abstain",
         notes="no payee, only a reference number"),

    # --- noisy / adversarial label cases (category is secondary, the point
    # is the label + rule_pattern must be clean) --------------------------
    Case('NETS Debit-Consumer COLD STORAGE12345678 SINGAPORE xxxxxx4321', -19.90, "outflow", "either",
         label_contains="Cold Storage", notes="digit run glued onto the name with no space"),
    Case('POS PURCHASE NTUC FAIRPRICE JURONG POINT SG xxxxxx9988', -44.30, "outflow", "categorize",
         "Groceries", label_contains="Fairprice", notes="POS/PURCHASE boilerplate must not leak into the label"),
    Case('OTHR DEBIT-CONSUMER AMAZON.COM AMZN.COM/BILL WA', -29.99, "outflow", "categorize",
         "Shopping", label_contains="Amazon"),
]


def check_label_clean(label: str) -> str | None:
    m = _LABEL_NOISE_RE.search(label)
    return f"label contains noise token {m.group(0)!r}: {label!r}" if m else None


def check_pattern_sane(pattern: str, raw_description: str) -> str | None:
    if pattern.upper() not in raw_description.upper():
        return f"rule_pattern {pattern!r} is not a substring of the raw description"
    if len(pattern) < 3:
        return f"rule_pattern {pattern!r} is suspiciously short (would over-match)"
    return None


@dataclass
class CaseResult:
    case: Case
    ok: bool
    problems: list[str] = field(default_factory=list)
    got_category: str | None = None
    got_label: str | None = None
    got_pattern: str | None = None


def score(case: Case, suggestion) -> CaseResult:
    problems: list[str] = []
    if suggestion is None:
        if case.expect == "categorize":
            problems.append(f"expected category {case.expect_category!r}, got no suggestion (abstained)")
        return CaseResult(case, ok=not problems, problems=problems)

    if case.expect == "abstain":
        problems.append(f"expected abstain, got category {suggestion.category!r}")

    if case.expect_category and suggestion.category != case.expect_category:
        problems.append(f"expected category {case.expect_category!r}, got {suggestion.category!r}")

    if case.label_contains and case.label_contains.lower() not in suggestion.display_label.lower():
        problems.append(f"expected label to contain {case.label_contains!r}, got {suggestion.display_label!r}")

    label_problem = check_label_clean(suggestion.display_label)
    if label_problem:
        problems.append(label_problem)

    if suggestion.rule_pattern:
        pattern_problem = check_pattern_sane(suggestion.rule_pattern, case.raw_description)
        if pattern_problem:
            problems.append(pattern_problem)

    return CaseResult(
        case, ok=not problems, problems=problems,
        got_category=suggestion.category, got_label=suggestion.display_label, got_pattern=suggestion.rule_pattern,
    )


def run_group(provider: OllamaProvider, categories: list[tuple[str, str]], cases: list[Case], label: str, verbose: bool):
    candidates = [
        AiCandidate(index=i, raw_description=c.raw_description, amount=c.amount, direction=c.direction)
        for i, c in enumerate(cases)
    ]
    start = time.monotonic()
    try:
        suggestions = provider.categorize(candidates, categories)
    except (AiProviderUnavailableError, AiProviderResponseError) as exc:
        print(f"\n[{label}] provider call FAILED for {len(cases)} candidate(s): {exc}")
        return []
    elapsed = time.monotonic() - start
    by_index = {s.index: s for s in suggestions}

    results = [score(c, by_index.get(i)) for i, c in enumerate(cases)]
    n_ok = sum(r.ok for r in results)
    print(f"\n[{label}] {n_ok}/{len(results)} passed in {elapsed:.1f}s ({len(cases)} candidate(s) in this call)")
    for r in results:
        if r.ok and not verbose:
            continue
        status = "PASS" if r.ok else "FAIL"
        print(f"  [{status}] {r.case.raw_description!r}")
        if r.case.notes:
            print(f"           note: {r.case.notes}")
        if r.got_category is not None or r.got_label is not None:
            print(f"           got: category={r.got_category!r} label={r.got_label!r} pattern={r.got_pattern!r}")
        for p in r.problems:
            print(f"           - {p}")
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default=None, help="Ollama model tag (default: first model ollama reports)")
    parser.add_argument("--base-url", default="http://localhost:11434")
    parser.add_argument("--mode", choices=["single", "batch", "both"], default="both")
    parser.add_argument("--chunk-size", type=int, default=None, help="chunk size for --mode batch (default: all at once, matching production)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    probe = OllamaProvider(args.base_url, model="")
    health = probe.check_health()
    if not health.reachable:
        print(f"Ollama not reachable at {args.base_url}: {health.error}")
        sys.exit(1)
    model = args.model or (health.models[0] if health.models else None)
    if not model:
        print("No models installed in Ollama (ollama list is empty) - pull one first, e.g. `ollama pull llama3.1`.")
        sys.exit(1)
    print(f"Using Ollama model {model!r} at {args.base_url} ({len(health.models)} model(s) available: {health.models})")

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "eval.db"
        db.init_db(db_path)
        conn = db._connect(db_path)
        categories = repo.fetch_ai_target_categories(conn)
        conn.close()

    provider = OllamaProvider(args.base_url, model=model)

    all_results: list[CaseResult] = []

    if args.mode in ("single", "both"):
        for c in CASES:
            all_results += run_group(provider, categories, [c], f"single: {c.raw_description[:40]}", args.verbose)

    if args.mode in ("batch", "both"):
        if args.chunk_size:
            for start in range(0, len(CASES), args.chunk_size):
                chunk = CASES[start : start + args.chunk_size]
                all_results += run_group(provider, categories, chunk, f"batch chunk {start}-{start+len(chunk)}", args.verbose)
        else:
            all_results += run_group(provider, categories, CASES, f"batch all {len(CASES)}", args.verbose)

    n = len(all_results)
    n_ok = sum(r.ok for r in all_results)
    print(f"\n{'=' * 60}\nTOTAL: {n_ok}/{n} passed ({100 * n_ok / n:.0f}%)" if n else "No results.")


if __name__ == "__main__":
    main()
