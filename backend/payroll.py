"""Zentra payroll guard — the supplier fraud rule, applied to salaries.

Payroll diversion: an attacker (or the employee's compromised email) changes the
salary account in the HR system right before payroll runs. Same shape as invoice
fraud: trusted name, new account. Same cure: compare the on-file account against
where salary has ACTUALLY been paid (bank transactions).
"""
from __future__ import annotations

from .models import Employee, Transaction, Verdict


def verify_employee(
    emp: Employee,
    transactions: list[Transaction],
    trusted: frozenset[tuple[str, str]] = frozenset(),
) -> Verdict:
    if (emp.id_norm, emp.account_norm) in trusted:
        return Verdict(
            invoice_id=emp.id,
            status="CLEAR",
            reason="Account change manually verified by you — confirmed with the "
                   "employee in person or by phone.",
            evidence={"account": emp.account_norm, "trusted_by_owner": True},
        )

    paid = {}
    for t in transactions:
        if t.orgnr_norm == emp.id_norm and t.account_norm:
            e = paid.setdefault(t.account_norm, {"times_paid": 0, "first_seen": None, "last_seen": None})
            e["times_paid"] += 1
            e["first_seen"] = min(e["first_seen"] or t.booking_date, t.booking_date)
            e["last_seen"] = max(e["last_seen"] or t.booking_date, t.booking_date)

    if not paid:
        return Verdict(
            invoice_id=emp.id, status="REVIEW",
            reason="No salary history for this employee yet — first payroll run "
                   "establishes the baseline. Verify the account at onboarding.",
            evidence={"baseline": True, "account": emp.account_norm},
        )

    if emp.account_norm in paid:
        ev = paid[emp.account_norm]
        return Verdict(
            invoice_id=emp.id, status="CLEAR",
            reason=f"Salary account matches history — paid {ev['times_paid']} times "
                   f"({ev['first_seen']} → {ev['last_seen']}).",
            evidence={"account": emp.account_norm, **ev},
        )

    total = sum(e["times_paid"] for e in paid.values())
    return Verdict(
        invoice_id=emp.id, status="HOLD",
        reason=(
            f"{emp.name}'s salary has been paid {total} times to the same account. "
            f"The account on file changed"
            + (f" on {emp.account_changed_at}" if emp.account_changed_at else "")
            + " and has never received a salary payment. Confirm with "
            f"{emp.name.split()[0]} in person or by phone — not by replying to the "
            "email that requested the change."
        ),
        evidence={
            "new_account": emp.account_norm,
            "new_account_display": emp.account_id,
            "changed_at": emp.account_changed_at,
            "known_accounts": [
                {"account": a, **e} for a, e in sorted(paid.items(), key=lambda kv: -kv[1]["times_paid"])
            ],
            "bank_confirmed_payments": total,
        },
    )


def screen_payroll(
    employees: list[Employee],
    transactions: list[Transaction],
    trusted: frozenset[tuple[str, str]] = frozenset(),
) -> list[Verdict]:
    return [verify_employee(e, transactions, trusted) for e in employees]
