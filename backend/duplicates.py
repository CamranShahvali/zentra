"""Duplicate payment detection — the second thing the ledger/bank gap reveals.

The fraud rule asks "has this account ever been paid before?". This asks the
opposite question of the same join: "has this invoice been paid MORE THAN ONCE?"

One invoice in the books, two matching debits at the bank. Nothing looks wrong
from either side on its own — both payments are real, authorised and correctly
booked. Only the join shows the second one. Industry loss runs at roughly
0.1–0.5% of total spend, and it is silent because nobody reconciles a payment
that succeeded.

Deterministic, like the fraud rule: no scoring, no ML, every hit is a list of
bank transaction ids a person can open in their own bank.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date

from .models import Invoice, Transaction

# Two debits for the same invoice land days apart — a re-sent reminder, a second
# approver, a re-import of the same payment file. The window is deliberately
# shorter than a month: salary, rent and subscriptions are the same account and
# the same amount every 30 days, and a naive detector reports every one of them
# as a duplicate. Anything on a monthly cadence is a standing charge, not a
# double payment.
WINDOW_DAYS = 14


def _days_between(a: str, b: str) -> int:
    try:
        return abs((date.fromisoformat(a) - date.fromisoformat(b)).days)
    except ValueError:
        return 10**6


def _amount_key(x: float) -> int:
    """Match on öre, not float identity."""
    return int(round(float(x) * 100))


def find_duplicate_payments(
    transactions: list[Transaction],
    history: list[Invoice] | None = None,
    window_days: int = WINDOW_DAYS,
    exclude_accounts: set[str] | None = None,
) -> list[dict]:
    """Return groups of bank payments that look like the same invoice paid twice.

    A group is (creditor account, exact amount) seen more than once inside the
    window. Grouping on the ACCOUNT rather than the name because a supplier can
    appear under several spellings in bank data — the account is the stable key,
    and it is the same normalisation the fraud rule trusts.

    `exclude_accounts` takes salary accounts out of scope: payroll is the same
    account for the same amount every month by design, and reporting it as a
    duplicate would be the detector crying wolf on the one pattern that is
    guaranteed to be intentional.
    """
    skip = exclude_accounts or set()
    buckets: dict[tuple[str, int], list[Transaction]] = defaultdict(list)
    for t in transactions:
        if t.amount >= 0 or not t.account_norm:
            continue                      # only outgoing money can be paid twice
        if t.account_norm in skip:
            continue
        buckets[(t.account_norm, _amount_key(-t.amount))].append(t)

    by_id = {inv.id: inv for inv in (history or [])}
    findings: list[dict] = []

    for (account, cents), txs in buckets.items():
        if len(txs) < 2:
            continue
        txs.sort(key=lambda t: t.booking_date)

        # Walk the run and only keep debits that sit close together: a monthly
        # rent to the same account for the same amount is not a duplicate.
        run: list[Transaction] = [txs[0]]
        for t in txs[1:]:
            if _days_between(run[-1].booking_date, t.booking_date) <= window_days:
                run.append(t)
                continue
            if len(run) > 1:
                findings.append(_finding(run, account, cents, by_id))
            run = [t]
        if len(run) > 1:
            findings.append(_finding(run, account, cents, by_id))

    findings.sort(key=lambda f: -f["amount_recoverable"])
    return findings


def _finding(run: list[Transaction], account: str, cents: int,
             by_id: dict[str, Invoice]) -> dict:
    amount = cents / 100
    extra = len(run) - 1                     # the first payment was legitimate
    supplier = next((t.creditor_name for t in run if t.creditor_name), None)

    # Try to name the invoice this was settling, so the owner can check it.
    matched = [
        inv.id for inv in by_id.values()
        if inv.account_norm == account and _amount_key(inv.amount) == cents
    ]

    return {
        "supplier_name": supplier or "unknown supplier",
        "account": account,
        "amount": amount,
        "times_paid": len(run),
        "amount_recoverable": round(amount * extra, 2),
        "first_paid": run[0].booking_date,
        "last_paid": run[-1].booking_date,
        "days_apart": _days_between(run[0].booking_date, run[-1].booking_date),
        "transaction_ids": [t.id for t in run],
        "matched_invoice_ids": matched[:5],
        "reason": (
            f"{supplier or 'This supplier'} was paid {amount:,.0f} SEK "
            f"{len(run)} times to the same account between {run[0].booking_date} "
            f"and {run[-1].booking_date} — {extra} payment(s) beyond the first. "
            f"The books record this charge once."
        ).replace(",", " "),
    }


def salary_accounts(employees) -> set[str]:
    """Normalised salary accounts, so payroll never reads as a duplicate."""
    out = set()
    for e in employees or []:
        a = getattr(e, "account_norm", None) or ""
        if a:
            out.add(a)
    return out


def summarise(findings: list[dict]) -> dict:
    return {
        "count": len(findings),
        "total_recoverable": round(sum(f["amount_recoverable"] for f in findings), 2),
        "findings": findings,
    }
