from backend.duplicates import find_duplicate_payments, salary_accounts, summarise
from backend.models import Transaction


def tx(id, date, amount, acc="SE6980000000123400112233", name="Fordonsleasing Stockholm AB"):
    return Transaction(id=id, booking_date=date, amount=-abs(amount), currency="SEK",
                       creditor_name=name, creditor_account=acc, creditor_orgnr="556520-1188")


def test_same_invoice_paid_twice_is_found():
    f = find_duplicate_payments([tx("A", "2026-07-08", 12400), tx("B", "2026-07-14", 12400)])
    assert len(f) == 1
    assert f[0]["times_paid"] == 2
    # only the SECOND payment is recoverable — the first one was owed
    assert f[0]["amount_recoverable"] == 12400
    assert f[0]["transaction_ids"] == ["A", "B"]


def test_single_payment_is_not_a_duplicate():
    assert find_duplicate_payments([tx("A", "2026-07-08", 12400)]) == []


def test_monthly_standing_charge_is_not_a_duplicate():
    """Rent/subscription: same account, same amount, every month. Not a duplicate."""
    monthly = [tx(f"M{i}", f"2026-{m:02d}-20", 7300) for i, m in enumerate(range(1, 8), 1)]
    assert find_duplicate_payments(monthly) == []


def test_salary_accounts_are_excluded():
    """Payroll is the same account and amount every month by design."""
    acc = "SE4550000000058300007301"
    pay = [tx("S1", "2026-07-25", 35000, acc=acc, name="Anna Lindqvist"),
           tx("S2", "2026-07-27", 35000, acc=acc, name="Anna Lindqvist")]
    assert len(find_duplicate_payments(pay)) == 1          # would fire...
    assert find_duplicate_payments(pay, exclude_accounts={acc}) == []   # ...but is excluded


def test_different_amounts_never_group():
    f = find_duplicate_payments([tx("A", "2026-07-08", 12400), tx("B", "2026-07-10", 12401)])
    assert f == []


def test_incoming_money_is_ignored():
    """Only outgoing payments can be paid twice."""
    incoming = [Transaction(id="I1", booking_date="2026-07-08", amount=5000.0, currency="SEK",
                            creditor_name="Customer", creditor_account="SE1", creditor_orgnr=None),
                Transaction(id="I2", booking_date="2026-07-10", amount=5000.0, currency="SEK",
                            creditor_name="Customer", creditor_account="SE1", creditor_orgnr=None)]
    assert find_duplicate_payments(incoming) == []


def test_three_payments_recover_two():
    f = find_duplicate_payments([tx("A", "2026-07-01", 5000),
                                 tx("B", "2026-07-04", 5000),
                                 tx("C", "2026-07-09", 5000)])
    assert f[0]["times_paid"] == 3
    assert f[0]["amount_recoverable"] == 10000


def test_seed_world_contains_the_planted_duplicate():
    from backend import datalayer
    w = datalayer.get_world("seed")
    s = summarise(find_duplicate_payments(
        w.transactions, w.history_invoices,
        exclude_accounts=salary_accounts(w.employees)))
    assert s["count"] == 1
    assert s["total_recoverable"] == 12400.0
    assert s["findings"][0]["supplier_name"] == "Fordonsleasing Stockholm AB"
