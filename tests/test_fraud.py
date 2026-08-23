import pytest

from backend.fraud import verify, screen_all
from backend.models import Invoice, Transaction


def inv(id="I1", org: str | None = "556677-8899", acc="SE4550000000005839825", name="Städgrossisten AB",
        issue="2026-08-22", due="2026-08-27", amount=48000.0):
    return Invoice(id=id, supplier_name=name, supplier_orgnr=org, amount=amount,
                   currency="SEK", issue_date=issue, due_date=due, account_id=acc)


def tx(id="T1", org="556677-8899", acc="SE4550000000005839825", when="2026-07-28"):
    return Transaction(id=id, booking_date=when, amount=-38000.0, currency="SEK",
                       creditor_name="Städgrossisten AB", creditor_account=acc,
                       creditor_orgnr=org)


def history_31():
    return [tx(id=f"T{i}", when=f"202{4 + i // 12}-{(i % 12) + 1:02d}-28") for i in range(31)]


def test_known_account_clears():
    v = verify(inv(), history=[], transactions=history_31())
    assert v.status == "CLEAR"
    assert "31 times" in v.reason


def test_new_account_holds_with_evidence():
    v = verify(inv(acc="SE9160000000000944411"), history=[], transactions=history_31())
    assert v.status == "HOLD"
    assert v.evidence["new_account"] == "SE9160000000000944411"
    assert v.evidence["known_accounts"][0]["times_paid"] == 31
    assert v.evidence["bank_confirmed_payments"] == 31


def test_first_supplier_is_baseline_clear():
    v = verify(inv(org="559999-0001", name="Ny Leverantör AB"), history=[], transactions=history_31())
    assert v.status == "CLEAR"
    assert v.evidence.get("baseline") is True


def test_missing_orgnr_is_review():
    v = verify(inv(org=None), history=[], transactions=history_31())
    assert v.status == "REVIEW"


def test_account_formatting_differences_clear():
    # same account with spaces + lowercase must match
    v = verify(inv(acc="se45 5000 0000 0058 3982 5"), history=[], transactions=history_31())
    assert v.status == "CLEAR"


def test_screen_all_screens_every_invoice():
    invoices = [inv(id="A"), inv(id="B", acc="SE9160000000000944411")]
    verdicts = screen_all(invoices, history=[], transactions=history_31())
    assert [v.status for v in verdicts] == ["CLEAR", "HOLD"]
