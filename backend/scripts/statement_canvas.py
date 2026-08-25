"""The bit of sample-statement drawing that isn't bank-specific.

`generate_sample_pdfs.py` (UOB) and `generate_dbs_ocbc_samples.py` both draw
text at pdfplumber-style `top` coordinates onto a reportlab canvas, and both
need a repeated per-page footer. That's all this holds - the column positions,
the table furniture and the transaction data stay with each bank's generator,
because that's the part that has to match a real statement.

Coordinate systems differ between the two libraries and this is where the
conversion lives: pdfplumber's `top` is distance from the top of the page
(what the parsers' column ranges and footer cutoffs are expressed in),
reportlab's `y` is distance from the bottom, ascending.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

PAGE_W, PAGE_H = A4  # 595.295 x 841.895, matches the real statements
FONT = "Helvetica"
FONT_BOLD = "Helvetica-Bold"

#: Text below this `top` is page footer. Must match the parsers' own cutoff
#: (`columnar.TableSpec.footer_top_cutoff`, `uob/*.py`'s FOOTER_TOP_CUTOFF):
#: a real statement's disclaimer footer lands inside the description column's
#: x-range, so it has to be dropped by y-coordinate before line grouping.
FOOTER_TOP_CUTOFF = 780


def y_for_top(top: float, font_size: float = 9) -> float:
    """Convert a pdfplumber-style `top` to a reportlab baseline `y`.

    The `font_size * 0.8` approximates the baseline offset within the line
    box. Exact pixel alignment doesn't matter - what matters is that words on
    one logical row land within the parsers' 3pt line-grouping tolerance of
    each other, and that each column's x falls inside the right bucket.
    """
    return PAGE_H - top - font_size * 0.8


class Doc:
    """A multi-page statement being drawn, with a footer stamped on each page."""

    def __init__(self, path: Path, footer_lines: list[tuple[float, str]]):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.c = canvas.Canvas(str(path), pagesize=A4)
        self.page_num = 1
        self.footer_lines = footer_lines

    def text(self, x: float, top: float, s: str, size: float = 9, font: str = FONT):
        self.c.setFont(font, size)
        self.c.drawString(x, y_for_top(top, size), s)

    def text_right(self, x_right: float, top: float, s: str, size: float = 9, font: str = FONT):
        self.c.setFont(font, size)
        self.c.drawRightString(x_right, y_for_top(top, size), s)

    def footer(self):
        for top, line in self.footer_lines:
            self.text(36, top, line.replace("{page}", str(self.page_num)), size=7)

    def new_page(self):
        self.footer()
        self.c.showPage()
        self.page_num += 1

    def save(self):
        self.footer()
        self.c.save()
