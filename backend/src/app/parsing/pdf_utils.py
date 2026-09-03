"""Shared spatial line-buffer extraction helpers.

Bank statement PDFs in this app have no visible table gridlines - columns are
purely whitespace-aligned. Rather than rely on pdfplumber's automatic table
detection (which needs ruling lines), we cluster words into physical lines by
vertical (`top`) proximity, then bucket each line's words into columns by
horizontal position against a per-statement-type column spec.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Word:
    text: str
    x0: float
    x1: float
    top: float
    bottom: float
    upright: bool = True


@dataclass(frozen=True)
class Column:
    name: str
    lo: float
    hi: float
    align: str = "left"  # "left" buckets by x0, "right" buckets by x1


@dataclass
class Line:
    top: float
    words: list[Word]

    def text(self) -> str:
        return " ".join(w.text for w in self.words)


def extract_words(page) -> list[Word]:
    return [
        Word(w["text"], w["x0"], w["x1"], w["top"], w["bottom"], w.get("upright", True))
        for w in page.extract_words(use_text_flow=False, keep_blank_chars=False)
    ]


def group_into_lines(words: list[Word], y_tol: float = 3.0) -> list[Line]:
    """Cluster words into physical lines by proximity of their `top` coordinate."""
    ordered = sorted(words, key=lambda w: (w.top, w.x0))
    lines: list[Line] = []
    current: list[Word] = []
    anchor_top = None
    for w in ordered:
        if anchor_top is None or abs(w.top - anchor_top) <= y_tol:
            current.append(w)
            anchor_top = w.top if anchor_top is None else anchor_top
        else:
            lines.append(Line(top=anchor_top, words=sorted(current, key=lambda x: x.x0)))
            current = [w]
            anchor_top = w.top
    if current:
        lines.append(Line(top=anchor_top, words=sorted(current, key=lambda x: x.x0)))
    return lines


def bucket_line(line: Line, columns: list[Column]) -> dict[str, str]:
    """Assign each word in a physical line to a column, join text per column."""
    buckets: dict[str, list[Word]] = {c.name: [] for c in columns}
    for w in line.words:
        for c in columns:
            key = w.x1 if c.align == "right" else w.x0
            if c.lo <= key < c.hi:
                buckets[c.name].append(w)
                break
    return {name: " ".join(w.text for w in ws) for name, ws in buckets.items()}


@dataclass(frozen=True)
class HeaderColumn:
    """One column of a table, described by the header word(s) printed above it."""

    name: str
    keywords: tuple[str, ...]
    align: str = "left"
    #: An optional column may be missing from a given statement template
    #: (OCBC prints a "Value Date" column on some statements and not others).
    #: Its absence shifts its neighbours' boundaries together rather than
    #: failing the whole header match.
    optional: bool = False


def columns_from_header(
    header: Line,
    spec: list[HeaderColumn],
    page_width: float,
) -> list[Column] | None:
    """Derive column x-ranges from the header row's own word positions.

    The UOB parsers hardcode their `Column` ranges, calibrated by hand against
    real statements. That is only possible for a bank whose real statements we
    have. For DBS and OCBC we have the *layout* (which columns exist, in which
    order, printed under which words) but no real PDF to measure, so the ranges
    are read off the header line at parse time instead: each column runs from
    the left edge of its own header word to the left edge of the next one's.

    That boundary is the left edge and not the midpoint of the gap for a
    reason worth keeping. A description column is left-aligned and wide, and
    the amount column to its right is right-aligned and narrow, so the gap
    between their *header* words is nothing like the gap between their
    *contents*: descriptions legitimately run on well past the midpoint, while
    amounts, right-aligned under the tail of a header like "WITHDRAWAL", never
    begin before that header does. A midpoint boundary therefore truncates
    long descriptions and reads their tail as an amount - which the first run
    of this against a fixture did, silently turning "... PTE LTD" into a
    withdrawal. Anchoring on the left edge gives each column exactly the span
    its own header claims.

    That is strictly more robust than hardcoding - it survives a bank nudging
    its column positions between statement revisions, which a hardcoded range
    does not - and it is what the header row is there to tell us anyway.

    `spec` is ordered left-to-right. Header words are matched
    case-insensitively; a multi-word header ("Value Date") is matched as
    consecutive words. Returns None when a required column's header word is
    absent, which is how a caller tells "this line is not the header" from
    "this is the header".
    """
    found: list[tuple[HeaderColumn, float, float]] = []
    search_from = 0
    for column in spec:
        span = _find_header_words(header.words, column.keywords, search_from)
        if span is None:
            if column.optional:
                continue
            return None
        start_idx, end_idx = span
        found.append((column, header.words[start_idx].x0, header.words[end_idx].x1))
        search_from = end_idx + 1

    columns: list[Column] = []
    for i, (column, x0, _x1) in enumerate(found):
        # The first column reaches to the page's left edge and the last to its
        # right, so a date printed a shade left of its header, or an amount
        # right-aligned past the page's last header, still lands in-column.
        lo = 0.0 if i == 0 else _left_bound(found[i - 1], found[i])
        hi = page_width if i == len(found) - 1 else _left_bound(found[i], found[i + 1])
        columns.append(Column(column.name, lo, hi, align=column.align))
    return columns


def _left_bound(left: tuple[HeaderColumn, float, float], right: tuple[HeaderColumn, float, float]) -> float:
    """The x that divides two adjacent columns.

    For a right-aligned column (an amount) the divider is that column's own
    header left edge: an amount right-aligned under "WITHDRAWAL" never starts
    before the "W", while the left-aligned description beside it legitimately
    runs on past the midpoint of the header gap - anchoring on the header's
    left edge is what stops a long "... PTE LTD" being read as a withdrawal.

    For a left-aligned column the opposite holds: its content can begin a hair
    left of its header word (font hinting, a slightly wider glyph), so the
    divider sits in the middle of the empty gap between the two header words
    instead. A DBS row's "Advice ..." description starts at the exact same x
    as the "Description" header, and floating-point equality is not a boundary
    to bet a parse on.
    """
    right_column, right_x0, _ = right
    if right_column.align == "right":
        return right_x0
    _, _, left_x1 = left
    return (left_x1 + right_x0) / 2


def _find_header_words(words: list[Word], keywords: tuple[str, ...], search_from: int) -> tuple[int, int] | None:
    """Locate any of `keywords` (each possibly multi-word) in `words`, at or
    after index `search_from`. Returns the (first, last) word index it spans."""
    for keyword in keywords:
        parts = keyword.lower().split()
        for start in range(search_from, len(words) - len(parts) + 1):
            if all(words[start + n].text.lower() == part for n, part in enumerate(parts)):
                return start, start + len(parts) - 1
    return None
