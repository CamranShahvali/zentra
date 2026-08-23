from datetime import date

from backend.models import Invoice, Obligation, Receivable
from backend.planner import customer_lateness, plan

TODAY = date(2026, 8, 25)


def mk_invoice(id, amount, due):
    return Invoice(id=id, supplier_name=f"S-{id}", supplier_orgnr=f"55{id}",
                   amount=float(amount), currency="SEK", issue_date="2026-08-18",
                   due_date=due, account_id=f"SE00{id}")


def elgiganten_history():
    """9 paid receivables, mean lateness 22 days, + 1 outstanding 96k due Aug 6."""
    lateness = [20, 21, 22, 23, 24, 22, 21, 23, 22]
    recs = []
    y, m = 2025, 11
    for k, late in enumerate(lateness, start=1):
        due = date(y, m, 6)
        paid = date(due.year, due.month, 6 + late) if 6 + late <= 28 else date(due.year, due.month + 1 if due.month < 12 else 1, (6 + late) % 28)
        # simpler: add timedelta
        from datetime import timedelta
        paid = due + timedelta(days=late)
        recs.append(Receivable(id=f"R{k}", customer_name="Elgiganten AB", amount=89000.0,
                               currency="SEK", due_date=due.isoformat(), paid_date=paid.isoformat()))
        m += 1
        if m > 12:
            m, y = 1, y + 1
    recs.append(Receivable(id="R10", customer_name="Elgiganten AB", amount=96000.0,
                           currency="SEK", due_date="2026-08-06", paid_date=None))
    return recs


def test_lateness_mean():
    lat = customer_lateness(elgiganten_history())
    assert lat["Elgiganten AB"] == 22.0


def test_all_fit_today_when_cash_is_plentiful():
    invoices = [mk_invoice("A", 1000, "2026-08-27"), mk_invoice("B", 2000, "2026-08-30")]
    items, proj = plan(invoices, balance=1_000_000, receivables=[], obligations=[],
                       today=TODAY, buffer_floor=10_000)
    assert all(i.pay_date == "2026-08-25" for i in items)
    assert proj["planned"]["violation_date"] is None


def test_seeded_story_reproduces_9_now_4_friday():
    """The demo scenario: 13 invoices, 42k due <=Wed, 18k due Fri+, VAT 84k Thu,
    balance 148.2k, Elgiganten 96k expected Fri Aug 28 (due Aug 6 + 22d late).
    Paying all today dips to 4,200; planner must defer the 4 later invoices to Aug 28."""
    early = [mk_invoice(f"E{i}", 42000 / 9, "2026-08-2%d" % (5 + i % 3)) for i in range(9)]
    late = [mk_invoice(f"L{i}", 4500, d) for i, d in
            enumerate(["2026-08-28", "2026-08-29", "2026-08-30", "2026-08-31"])]
    obligations = [Obligation(name="VAT", amount=84000.0, due_date="2026-08-27")]
    items, proj = plan(early + late, balance=148200.0, receivables=elgiganten_history(),
                       obligations=obligations, today=TODAY, buffer_floor=10_000)
    assert proj["naive"]["min_balance"] == 4200.0
    assert proj["naive"]["violation_date"] is not None
    by_id = {i.invoice_id: i for i in items}
    for e in early:
        assert by_id[e.id].pay_date == "2026-08-25"
    for l in late:
        assert by_id[l.id].pay_date == "2026-08-28", by_id[l.id]
    assert proj["planned"]["violation_date"] is None
    assert proj["planned"]["min_balance"] >= 10_000
    # inflow used is Elgiganten on the 28th
    assert proj["inflows"][0]["date"] == "2026-08-28"
    assert proj["inflows"][0]["avg_lateness_days"] == 22.0


def test_never_deferred_past_due_date():
    # invoice due tomorrow cannot move to the inflow on the 28th even under pressure
    tight = mk_invoice("T", 90000, "2026-08-26")
    obligations = [Obligation(name="VAT", amount=84000.0, due_date="2026-08-27")]
    items, proj = plan([tight], balance=100000.0, receivables=elgiganten_history(),
                       obligations=obligations, today=TODAY, buffer_floor=10_000)
    assert items[0].pay_date <= "2026-08-26"
