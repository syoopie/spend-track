"""Sanitize a statement in the app, so contributing one needs no terminal.

Every parser here was written against a real statement, and the only way to
produce a shareable one used to be `scripts/sanitize_statement.py`: clone,
install uv, run a command with flags, read a text file. That gate is why DBS
and OCBC were written blind and why OCBC still has no real sample. This
endpoint is the same rules (`app/sanitize.py`) behind a page.

It holds nothing between calls, and that is a privacy decision rather than a
simplicity one. The obvious optimization is to cache the parsed pages so that
striking one more word off the list does not re-read the PDF - but those pages
are the *un-redacted* `Word` list, every name, address and account number in
the statement, and caching them means holding all of it in process memory for
as long as a contributor keeps the tab open. Recomputing from the uploaded
bytes on every edit is the cheaper risk.

The uploaded file name never appears in a response. It identifies its owner as
well as the contents do ("JaneWong-Jan2024.pdf"), so `suggested_filename` is
built from the bank the contributor typed plus a hash of the bytes, and no
error message here echoes what was sent.
"""

import base64
import hashlib
import re

import pypdf.errors
from fastapi import APIRouter, File, Form, UploadFile

from app import sanitize
from app.errors import api_error
from app.models import ParsedAccountSummary, SanitizeResultOut

router = APIRouter(prefix="/api/contribute", tags=["contribute"])

#: A statement is a few hundred KB. The cap exists so a mistaken pick (a video,
#: a disk image) fails with a sentence rather than being read, rebuilt and
#: base64'd back into a JSON body - upload_statement has no equivalent because
#: it hands nothing back.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def _suggested_filename(bank: str, data: bytes) -> str:
    """A neutral name for the download, from the typed bank and the content.

    Hashed on the *input* bytes rather than the output's, so striking another
    word off the list does not rename the file mid-session. It is passed to
    `verify` as the output name, which is what makes the "the output file name
    contains a word you asked to remove" check fire on the name the browser
    will actually save - a contributor who types their own name into the bank
    box gets told.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", bank.lower()).strip("-")[:24]
    return f"sample-{slug or 'statement'}-{hashlib.sha256(data).hexdigest()[:8]}.pdf"


@router.post("/sanitize", response_model=SanitizeResultOut)
def sanitize_statement(
    file: UploadFile = File(...),
    password: str | None = Form(default=None),
    bank: str = Form(default=""),
    redact: list[str] = Form(default=[]),
    keep: list[str] = Form(default=[]),
    redact_amounts: bool = Form(default=False),
) -> SanitizeResultOut:
    """Read, redact, rebuild and re-check, keeping nothing.

    Deliberately `def` and not `async def`: pdfplumber and reportlab are CPU
    work with no await in them, so FastAPI running this in its threadpool is
    what keeps a multi-page statement from stalling the event loop for every
    other request in the app.
    """
    if not (file.filename or "").lower().endswith(".pdf"):
        raise api_error(422, "UNPARSEABLE_STATEMENT_FORMAT", "That file is not a PDF e-statement.")
    data = file.file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise api_error(
            422,
            "STATEMENT_TOO_LARGE",
            f"That file is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB. "
            "A bank statement is normally well under a megabyte - check you picked the right file.",
        )

    suggested = _suggested_filename(bank, data)
    try:
        result = sanitize.sanitize(
            data,
            password=password,
            redact=redact,
            keep=keep,
            redact_amounts=redact_amounts,
            output_name=suggested,
        )
    except sanitize.EncryptedPdfError:
        # The same codes upload uses, so the frontend's existing password
        # prompt works here unchanged. open_pdf already tries the empty
        # password first (DBS's consolidated eStatement is owner-locked with
        # one), so this only fires on a statement that really wants a password.
        raise api_error(422, "ENCRYPTED_PDF_PASSWORD_REQUIRED", "This statement is password-protected.")
    except sanitize.IncorrectPasswordError:
        raise api_error(422, "INCORRECT_PDF_PASSWORD", "The supplied password did not unlock this statement.")
    except pypdf.errors.PdfReadError:
        raise api_error(422, "UNPARSEABLE_STATEMENT_FORMAT", "That file is not a PDF e-statement.")

    check = sanitize.check_parse(result.pdf)
    parse_status = "parsed" if check.parsed else "error" if check.failure_kind == "parser_error" else "unsupported"

    # A PDF with no text is a scan or a photo. Sanitizing it produces a blank
    # page that passes verification vacuously, which a contributor reads as
    # "it removed everything, working correctly". Withholding the file is the
    # only honest answer; it is not a `problems` entry, because nothing leaked
    # - it is the wrong kind of file. A failed verification, by contrast, still
    # ships the download alongside the warning.
    refused = result.word_count == 0

    return SanitizeResultOut(
        problems=result.problems,
        kept_words=result.kept,
        oddities=result.oddities,
        page_count=result.page_count,
        word_count=result.word_count,
        parse_status=parse_status,
        parse_detail=check.detail,
        detected_bank=check.bank_name,
        account_summaries=[
            ParsedAccountSummary(account_type=a.account_type, transaction_count=a.transaction_count)
            for a in check.account_summaries
        ],
        suggested_filename=suggested,
        pdf_base64=None if refused else base64.b64encode(result.pdf).decode("ascii"),
        refusal_reason="no_text" if refused else None,
    )
