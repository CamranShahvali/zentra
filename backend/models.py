"""Zentra domain models — plain dataclasses, no ORM."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Literal


def _norm_account(acc: str | None) -> str:
    """Normalise an account id: strip spaces/dashes, uppercase.

    'SE45 5000-0000 0583 9825' == 'se4550000000005839825'
    """
    if not acc:
        return ""
    return "".join(ch for ch in str(acc) if ch.isalnum()).upper()


@dataclass
class Invoice:
    id: str
    supplier_name: str
    supplier_orgnr: str | None
    amount: float
    currency: str
    issue_date: str  # yyyy-mm-dd
    due_date: str
    account_id: str  # payee bank account as printed on the invoice
    institution: str | None = None
    reference: str | None = None
    source: Literal["live", "seed"] = "seed"

    @property
    def account_norm(self) -> str:
        return _norm_account(self.account_id)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["account_norm"] = self.account_norm
        return d


@dataclass
class Transaction:
    """An outgoing bank payment (what actually happened)."""
    id: str
    booking_date: str
    amount: float
    currency: str
    creditor_name: str | None
    creditor_account: str
    creditor_orgnr: str | None = None
    source: Literal["live", "seed"] = "seed"

    @property
    def account_norm(self) -> str:
        return _norm_account(self.creditor_account)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["account_norm"] = self.account_norm
        return d


@dataclass
class Receivable:
    """A sales invoice we are owed, plus how the customer actually pays."""
    id: str
    customer_name: str
    amount: float
    currency: str
    due_date: str
    paid_date: str | None = None  # None = still outstanding
    source: Literal["live", "seed"] = "seed"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Obligation:
    """A fixed outflow that is not a supplier invoice (VAT, salaries)."""
    name: str
    amount: float
    due_date: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Verdict:
    invoice_id: str
    status: Literal["CLEAR", "HOLD", "REVIEW"]
    reason: str
    evidence: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PlanItem:
    invoice_id: str
    pay_date: str
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)
