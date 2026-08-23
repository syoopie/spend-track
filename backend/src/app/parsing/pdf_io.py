import io

import pdfplumber
import pypdf


class EncryptedPdfError(Exception):
    """Raised when a PDF is encrypted and no password was supplied."""


class IncorrectPasswordError(Exception):
    """Raised when the supplied password fails to decrypt the PDF."""


def open_pdf(data: bytes, password: str | None = None) -> pdfplumber.PDF:
    """Open a PDF, transparently decrypting in-memory if needed.

    The password (if any) is used only to decrypt the byte stream held in
    memory for this request - it is never written to disk or the database,
    per docs/technical-spec.md's "In-Memory Password Decryption" requirement.
    """
    reader = pypdf.PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        if not password:
            raise EncryptedPdfError()
        if reader.decrypt(password) == 0:
            raise IncorrectPasswordError()
        writer = pypdf.PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        buf = io.BytesIO()
        writer.write(buf)
        data = buf.getvalue()
    return pdfplumber.open(io.BytesIO(data))
