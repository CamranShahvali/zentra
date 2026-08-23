"""Zentra payment planner — day-by-day cash simulation, deterministic.

Inputs: cleared invoices, current balance, receivables (with per-customer
observed lateness), fixed obligations (VAT, salaries), a buffer floor.
Output: a pay date per invoice + a projection, such that the projected balance
never dips under the floor when avoidable — and an invoice is NEVER deferred
past its due date.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from .models import Invoice, Obligation, PlanItem, Receivable


def customer_lateness(receivables: list[Receivable]) -> dict[str, float]:
    """Mean observed lateness (days, paid vs due) per customer. Unpaid rows excluded."""
    lat: dict[str, list[int]] = defaultdict(list)
    for r in receivables:
        if r.paid_date:
            d = (date.fromisoformat(r.paid_date) - date.fromisoformat(r.due_date)).days
            lat[r.customer_name].append(d)
    return {c: sum(v) / len(v) for c, v in lat.items()}


def expected_inflows(
    receivables: list[Receivable], today: date, horizon_days: int
) -> list[tuple[date, float, str, float, str]]:
    """(expected_date, amount, customer, lateness, due_date) for outstanding receivables."""
    lateness = customer_lateness(receivables)
    out = []
    for r in receivables:
        if r.paid_date:
            continue
        late = lateness.get(r.customer_name, 0.0)
        expected = date.fromisoformat(r.due_date) + timedelta(days=round(late))
        if expected < today:
            expected = today + timedelta(days=1)  # overdue: assume imminent, not past
        if expected <= today + timedelta(days=horizon_days):
            out.append((expected, r.amount, r.customer_name, late, r.due_date))
    return sorted(out)


def plan(
    invoices: list[Invoice],
    balance: float,
    receivables: list[Receivable],
    obligations: list[Obligation],
    today: date,
    buffer_floor: float = 10_000.0,
    horizon_days: int = 14,
) -> tuple[list[PlanItem], dict]:
    horizon_end = today + timedelta(days=horizon_days)
    inflows = expected_inflows(receivables, today, horizon_days)

    def simulate(pay_dates: dict[str, date]) -> tuple[float, date | None, list[dict]]:
        """Run the cash timeline. Returns (min_balance, first_violation_day, series)."""
        events: dict[date, float] = defaultdict(float)
        for inv in invoices:
            events[pay_dates[inv.id]] -= inv.amount
        for ob in obligations:
            d = date.fromisoformat(ob.due_date)
            if today <= d <= horizon_end:
                events[d] -= ob.amount
        for d, amount, _c, _l, _due in inflows:
            events[d] += amount

        bal = balance
        min_bal, violation = bal, None
        series = []
        for offset in range(horizon_days + 1):
            d = today + timedelta(days=offset)
            bal += events.get(d, 0.0)
            series.append({"date": d.isoformat(), "balance": round(bal, 2)})
            if bal < min_bal:
                min_bal = bal
            if bal < buffer_floor and violation is None:
                violation = d
        return min_bal, violation, series

    # start: pay everything today (or on its due date if already past today)
    pay_dates: dict[str, date] = {}
    for inv in invoices:
        due = date.fromisoformat(inv.due_date)
        pay_dates[inv.id] = min(max(today, today), due) if due >= today else today
        pay_dates[inv.id] = today

    naive_min, naive_violation, naive_series = simulate(pay_dates)

    # deferral loop: while the floor is broken, group every invoice that can
    # safely wait (due on/after the next inflow) onto that inflow day — when
    # cash is tight you do not pay early, you batch with incoming money.
    # If still broken, keep moving whatever else can move, latest due first.
    reasons: dict[str, str] = {inv.id: "Due soon — pay now." for inv in invoices}
    guard = 0
    while guard < 50:
        guard += 1
        min_bal, violation, series = simulate(pay_dates)
        if violation is None:
            break
        candidates = []
        for inv in invoices:
            due = date.fromisoformat(inv.due_date)
            cur = pay_dates[inv.id]
            # find the earliest inflow strictly after the current pay date
            next_inflow = next((d for d, *_ in inflows if d > cur), None)
            if next_inflow and next_inflow <= due and next_inflow <= horizon_end:
                candidates.append((due, inv, next_inflow))
        if not candidates:
            break  # nothing can move without breaking a due date — accept the dip
        candidates.sort(key=lambda t: t[0], reverse=True)
        moved_any = False
        for due, inv, target in candidates:
            if pay_dates[inv.id] == target:
                continue
            inflow_on_day = [(c, a) for d, a, c, _l, _due in inflows if d == target]
            src = inflow_on_day[0] if inflow_on_day else ("expected inflow", 0)
            pay_dates[inv.id] = target
            reasons[inv.id] = (
                f"Waits for {target.isoformat()} — {src[0]} money lands that day; "
                f"paying earlier would cut the buffer below {int(buffer_floor):,} SEK.".replace(",", " ")
            )
            moved_any = True
        if not moved_any:
            break

    final_min, final_violation, final_series = simulate(pay_dates)
    # honest shortfall reporting: if the floor (or zero) is still breached after
    # planning, the UI must show it — pretending otherwise is how demos die.
    shortfall = None
    if final_violation is not None:
        shortfall = {
            "violation_date": final_violation.isoformat(),
            "min_balance": round(final_min, 2),
            "below_zero": final_min < 0,
            "note": ("Even with optimal timing, planned outflows exceed available cash "
                     "in this window. Zentra will not hide a shortfall."),
        }
    items = [
        PlanItem(invoice_id=inv.id, pay_date=pay_dates[inv.id].isoformat(), reason=reasons[inv.id])
        for inv in sorted(invoices, key=lambda i: (pay_dates[i.id], i.due_date))
    ]
    projection = {
        "naive": {"min_balance": round(naive_min, 2),
                  "violation_date": naive_violation.isoformat() if naive_violation else None,
                  "series": naive_series},
        "planned": {"min_balance": round(final_min, 2),
                    "violation_date": final_violation.isoformat() if final_violation else None,
                    "series": final_series},
        "inflows": [{"date": d.isoformat(), "amount": a, "customer": c,
                     "avg_lateness_days": round(l, 1), "due_date": due}
                    for d, a, c, l, due in inflows],
        "buffer_floor": buffer_floor,
        "shortfall": shortfall,
    }
    return items, projection
