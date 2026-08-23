from backend import datalayer


def test_seed_world_complete():
    w = datalayer.get_world("seed")
    assert len(w.invoices) == 14
    assert len(w.history_invoices) >= 60
    assert len(w.transactions) >= 60
    assert w.balance == 148200.0
    assert all(v == "seed" for v in w.sources.values())


def test_fraud_invoice_present_exactly_once():
    w = datalayer.get_world("seed")
    fraud = [i for i in w.invoices if i.account_norm == "SE9160000000000944411"]
    assert len(fraud) == 1
    assert fraud[0].supplier_orgnr == "556677-8899"


def test_stadgrossisten_bank_history_is_31_payments_one_account():
    w = datalayer.get_world("seed")
    sg = [t for t in w.transactions if t.creditor_orgnr == "556677-8899"]
    assert len(sg) == 31
    assert {t.account_norm for t in sg} == {"SE4550000000005839825"}
