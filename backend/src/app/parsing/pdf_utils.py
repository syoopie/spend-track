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
        Word(w["text"], w["x0"], w["x1"], w["top"], w["bottom"])
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
