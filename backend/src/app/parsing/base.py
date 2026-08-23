from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ParsedTransaction:
    transaction_date: str  # ISO YYYY-MM-DD
    raw_description: str
    amount: float  # signed: negative = outflow, positive = inflow
    balance: float | None = None


@dataclass
class ParsedAccount:
    bank_name: str
    account_number: str  # full/unmasked - used only to derive a stable account id
    account_number_masked: str
    account_type: str
    transactions: list[ParsedTransaction] = field(default_factory=list)
    is_card: bool = False  # True for credit card statements, False for deposit/current accounts


@dataclass
class ParsedStatement:
    bank_name: str
    accounts: list[ParsedAccount]


class UnparseableStatementError(Exception):
    """Raised when no registered parser recognizes the statement.

    Maps to HTTP 422 UNPARSEABLE_STATEMENT_FORMAT per docs/technical-spec.md - no
    manual column-mapping fallback is offered.
    """


class BankParser(ABC):
    bank_name: str

    @abstractmethod
    def detect(self, pages: list) -> bool:
        """Cheap anchor-text check: does this look like our bank's statement?"""

    @abstractmethod
    def parse(self, pages: list) -> ParsedStatement:
        """Full spatial extraction. Only called after detect() returns True."""
