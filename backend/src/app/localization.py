"""Every country-specific constant this app depends on, gathered into one
profile - currency, contact-identifier format, the local instant-transfer
scheme's name, and which bank parsers apply.

Only Singapore is populated: there are no real (or even reliably-fake)
sample statements for a second country to build and validate a second
profile against, so this stays a one-country registry rather than a
speculative multi-country abstraction. What it buys today is that the
values scattered across parsing/registry.py, engine/paynow.py's category
naming, and the frontend's currency formatting all trace back to one
source instead of being independently hardcoded "SGD"/"$"/"+65" literals -
so a second country's constants have exactly one place to land, and the
bank-parser list (parsing/registry.py) stops being a second copy of the
same list this module already holds.
"""

from dataclasses import dataclass

from app.parsing.base import BankParser
from app.parsing.dbs import DBSParser
from app.parsing.ocbc import OCBCParser
from app.parsing.uob import UOBParser


@dataclass(frozen=True)
class CountryProfile:
    code: str
    name: str
    currency_code: str
    currency_symbol: str
    phone_calling_code: str
    contact_identifier_hint: str
    transfer_scheme_name: str
    bank_parsers: list[BankParser]


SINGAPORE = CountryProfile(
    code="SG",
    name="Singapore",
    currency_code="SGD",
    currency_symbol="$",
    phone_calling_code="+65",
    # No phone number example - real UOB PayNow lines almost never carry the
    # payer's actual phone number in the raw description, so hinting one was
    # actively misleading (see frontend/src/lib/localization.ts's mirror of
    # this constant).
    contact_identifier_hint="UEN, account no., or payee name",
    transfer_scheme_name="PayNow",
    bank_parsers=[UOBParser(), DBSParser(), OCBCParser()],
)

# The one active profile. A second populated profile would make this a
# settings-driven selector instead of a constant - there's nothing to
# select between yet.
ACTIVE_COUNTRY = SINGAPORE
