"""Zentra fraud screen — deterministic, auditable. No ML, on purpose.

Rule: a supplier's set of known-good payment accounts is derived from
  (a) that supplier's own past invoices, and
  (b) actual outgoing bank payments to that supplier (the ground truth).
A new invoice whose payee account is outside that set => HOLD.
A supplier we have never dealt with => CLEAR (baseline) — you cannot diff nothing.
An invoice whose supplier cannot be identified (no orgnr) => REVIEW.
"""
from __future__ import annotations

from collections import defaultdict

from .models import Invoice, Transaction, Verdict, _norm_account


def _known_accounts(
    orgnr: str,
    history: list[Invoice],
    transactions: list[Transaction],
) -> tuple[dict[str, dict], int]:
    """Map normalised account -> evidence {times_paid, first_seen, last_seen}."""
    acc: dict[str, dict] = defaultdict(lambda: {"times_paid": 0, "first_seen": None, "last_seen": None})

    def bump(a: str, when: str, weight: int = 1):
        e = acc[a]
        e["times_paid"] += weight
        e["first_seen"] = min(e["first_seen"] or when, when)
        e["last_seen"] = max(e["last_seen"] or when, when)

    bank_hits = 0
    for t in transactions:
        if t.creditor_orgnr == orgnr and t.account_norm:
            bump(t.account_norm, t.booking_date)
            bank_hits += 1
    for inv in history:
        if inv.supplier_orgnr == orgnr and inv.account_norm:
            # history invoices corroborate but only count as payments when the
            # bank never saw them (weight 0 if account already bank-confirmed)
            if inv.account_norm not in acc:
                bump(inv.account_norm, inv.issue_date, weight=0)
    return dict(acc), bank_hits


def verify(
    invoice: Invoice,
    history: list[Invoice],
    transactions: list[Transaction],
) -> Verdict:
    if not invoice.supplier_orgnr:
        return Verdict(
            invoice_id=invoice.id,
            status="REVIEW",
            reason="Supplier has no organisation number on the invoice — "
                   "payment account cannot be verified against history.",
            evidence={"supplier_name": invoice.supplier_name},
        )

    known, bank_hits = _known_accounts(invoice.supplier_orgnr, history, transactions)

    if not known:
        return Verdict(
            invoice_id=invoice.id,
            status="CLEAR",
            reason="First invoice from this supplier — establishes the baseline account.",
            evidence={"baseline": True, "account": invoice.account_norm},
        )

    if invoice.account_norm in known:
        ev = known[invoice.account_norm]
        return Verdict(
            invoice_id=invoice.id,
            status="CLEAR",
            reason=f"Account matches history — paid {ev['times_paid']} times before "
                   f"({ev['first_seen']} → {ev['last_seen']}).",
            evidence={"account": invoice.account_norm, **ev},
        )

    total_paid = sum(e["times_paid"] for e in known.values())
    return Verdict(
        invoice_id=invoice.id,
        status="HOLD",
        reason=(
            f"{invoice.supplier_name} has been paid {total_paid} times to "
            f"{len(known)} known account(s). This invoice names an account "
            f"never seen for this supplier."
        ),
        evidence={
            "new_account": invoice.account_norm,
            "new_account_display": invoice.account_id,
            "institution": invoice.institution,
            "known_accounts": [
                {"account": a, **e} for a, e in sorted(known.items(), key=lambda kv: -kv[1]["times_paid"])
            ],
            "bank_confirmed_payments": bank_hits,
        },
    )


def screen_all(
    invoices: list[Invoice],
    history: list[Invoice],
    transactions: list[Transaction],
) -> list[Verdict]:
    return [verify(inv, history, transactions) for inv in invoices]
