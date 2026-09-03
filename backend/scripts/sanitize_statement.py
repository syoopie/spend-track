"""Turn a real bank statement into one that can be shared with developers.

Why this exists
---------------
Every parser in this project needs a real statement to be built against, and
nobody can hand one over: it carries a name, a home address, an account number
and a year of spending. UOB got parsed because the author had UOB statements;
DBS and OCBC had to be written against their published layouts instead (see
`app/parsing/columnar.py`). This closes that gap.

What it keeps, and why that is all a parser needs
-------------------------------------------------
It keeps the statement's *geometry* and the *bank's own wording*, and replaces
everything else with its shape:

    FAST Payment / Receipt PayNow    ->  XXXX Xxxxxxx / Xxxxxxx XxXxx
    Transfer To: TAN WEI MING            Xxxxxxxx Xx: XXX XXX XXXX
    01 Feb   BALANCE B/F  5,000.00   ->  01 Feb   BALANCE B/F  5,000.00

That is enough because a parser never reads a transaction description. It keys
on the bank name, the column headings, the BALANCE B/F and Total rows and the
statement date - all of which are printed identically on every statement the
bank issues and belong to nobody - then uses each word's position to work out
which column it is in. Replacing every description across this project's whole
fixture set leaves all three parsers returning identical dates, amounts and
balances, which `test_structure_only_costs_the_parsers_nothing` pins.

Geometry alone is not enough, though: strip the bank's wording too and no
parser can even tell which bank it is looking at.

So the rule is default-deny. A word is kept only if it is positively
recognized as template, a date, or a figure; anything else - anything nobody
anticipated - is replaced rather than published. That means no judgement calls
for you, and no list of maybe-personal words to review.

What it does not protect
------------------------
The figures. Amounts and balances survive, because they are what a parser has
to read correctly and what its reconciliation checks are written against. The
output still shows what you spent, just not who you are or who you paid.
--redact-amounts replaces them too, at the cost of those checks.

How it works, and why not a black box
-------------------------------------
Drawing a black rectangle over text in a PDF does not remove the text. It is
still in the content stream, still selectable, still there for anyone who runs
`pdftotext`. Redaction tools that get this wrong have leaked real documents.

So this does not edit your PDF. It reads the position and content of every
word and draws a *new* PDF containing only the surviving ones. The original
text, images, annotations, attachments, metadata and any earlier revision left
in the file do not exist in the output, because the output was built empty.

Using it
--------
    uv run python scripts/sanitize_statement.py statement.pdf --check-parse

If the result does not parse, this script did not recognize one of your bank's
headings - pass `--keep "THAT HEADING"` and try again. That failure is loud;
it is never a silent leak.

Before finishing it re-reads its own output and refuses the file unless every
surviving word is one it can account for - including the output's *name*,
since "JaneWong-Jan2024.pdf" identifies its owner as well as its contents do.
Use --output to name the result something neutral.

The rules themselves live in `app/sanitize.py`, so the in-app Contribute page
runs exactly this and not a second copy of it. Everything below is the CLI:
argument handling, where the files land, and what gets printed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# A contributor runs this straight from a clone, with nothing installed, so
# the package has to be put on the path by hand. Executed once at import
# rather than per call, which is what it used to be.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.parsing.pdf_io import EncryptedPdfError, IncorrectPasswordError  # noqa: E402
from app.sanitize import (  # noqa: E402
    ParseCheck,
    Word,
    _literal_matches,
    check_parse,
    group_lines,
    redact_line,
    sanitize,
    verify,
)

#: Re-exported so `import sanitize_statement` still reaches the redaction rules
#: it used to own - the tests exercise them through this name.
__all__ = [
    "ParseCheck",
    "Word",
    "_literal_matches",
    "check_parse",
    "group_lines",
    "main",
    "redact_line",
    "sanitize",
    "verify",
]


def write_review(path: Path, kept: list[str], source_name: str) -> None:
    """Write the kept-words list to a text file beside the output.

    Its own step, and its own vocabulary: this prose talks about `--redact`
    and `--redact-amounts`, which mean nothing to someone who clicked a button
    in the app. The list itself comes from `app.sanitize.kept_words`.
    """
    path.write_text(
        "\n".join(
            [
                f"Words kept verbatim from {source_name}",
                "",
                "Everything else was replaced with its shape. These survived because",
                "this script recognizes them as your bank's own template wording, which",
                "is what a parser reads. Skim it: if your name or your street happens to",
                "be a banking word (someone called May, a merchant called Trust), it is",
                "in here, and --redact removes it.",
                "",
                "Amounts and balances were kept too, and are not listed. They are what a",
                "parser has to read correctly. Use --redact-amounts to replace them.",
                "",
                f"--- {len(kept)} words ---",
                *kept,
                "",
            ]
        ),
        encoding="utf-8",
    )


def describe_parse(check: ParseCheck) -> str:
    if check.parsed:
        counts = ", ".join(f"{a.account_type} ({a.transaction_count} transactions)" for a in check.account_summaries)
        return f"parses as {check.bank_name}: {counts}"
    if check.failure_kind == "parser_error":
        return f"parser raised {check.detail}"
    return f"does not parse yet: {check.detail}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Strip personal data from a bank statement PDF, keeping the layout a parser needs.",
    )
    parser.add_argument("pdf", type=Path, help="the statement to sanitize")
    parser.add_argument("-o", "--output", type=Path, help="output path (default: <name>.sanitized.pdf)")
    parser.add_argument("--password", help="password, if the statement is protected (never stored)")
    parser.add_argument(
        "--keep",
        action="append",
        default=[],
        metavar="TEXT",
        help="wording to preserve that this script doesn't recognize as your bank's template. "
        "Reach for it when --check-parse says the result doesn't parse. Repeatable.",
    )
    parser.add_argument(
        "--redact",
        action="append",
        default=[],
        metavar="TEXT",
        help="text to remove even though it looks like template - a person called May, "
        "a merchant called Trust. Repeatable.",
    )
    parser.add_argument(
        "--redact-amounts",
        action="store_true",
        help="replace the figures too. Shares the structure only, and defeats the reconciliation "
        "checks a parser is tested against - prefer leaving it off.",
    )
    parser.add_argument("--check-parse", action="store_true", help="try parsing the result with this app's parsers")
    args = parser.parse_args(argv)

    if not args.pdf.is_file():
        raise SystemExit(f"No such file: {args.pdf}")

    out_path = args.output or args.pdf.with_name(args.pdf.stem + ".sanitized.pdf")
    review_path = out_path.with_suffix(".review.txt")

    try:
        result = sanitize(
            args.pdf.read_bytes(),
            password=args.password,
            redact=args.redact,
            keep=args.keep,
            redact_amounts=args.redact_amounts,
            output_name=out_path.name,
        )
    except EncryptedPdfError:
        raise SystemExit(
            f"{args.pdf.name} is password-protected. Re-run with --password (it is used only "
            "to decrypt in memory and is never written anywhere)."
        ) from None
    except IncorrectPasswordError:
        raise SystemExit(f"The password given does not decrypt {args.pdf.name}.") from None

    # Written before the verdict, and written even when the verdict is a
    # refusal, so a maintainer can open the file and see what leaked.
    out_path.write_bytes(result.pdf)
    write_review(review_path, result.kept, args.pdf.name)

    print(f"Wrote {out_path}")
    print(f"Wrote {review_path}")
    if result.rotated_dropped:
        print(
            f"  dropped {result.rotated_dropped} rotated/vertical words "
            "(sidebars and watermarks, never transactions)"
        )

    if result.problems:
        print("\nVERIFICATION FAILED - do not share this file:")
        for problem in result.problems[:20]:
            print(f"  - {problem}")
        if len(result.problems) > 20:
            print(f"  ... and {len(result.problems) - 20} more")
        return 1

    print(
        "  checked: every word in the output is template, a date, a figure, or replaced "
        f"({len(result.kept)} kept verbatim)"
    )
    if args.check_parse:
        print(f"  parse check: {describe_parse(check_parse(result.pdf))}")
    print(f"\nSkim {review_path.name} before sharing - it lists what was kept.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
