"""Deterministic seed-data generator for the Zentra demo.

SYNTHETIC DATA. Shapes mirror what our API clients return after normalisation
(models.py), not raw DTOs — datalayer merges seed and live through the same models.

Story invariants (asserted at the bottom):
  * balance 148,200; 13 clean invoices total 60,000 (9 due <=Thu total 42,000,
    4 due Fri+ total 18,000); VAT 84,000 on Thu 27th.
  * pay-everything-today => 148,200-60,000-84,000 = 4,200 < 10,000 floor.
  * Elgiganten: 9 paid invoices, mean lateness exactly 22 days; outstanding
    96,000 due Aug 6 => expected Aug 28 (Friday).
  * Städgrossisten: 31 bank payments to ...9825; today's invoice names ...4411.

Run:  python -m backend.seed.generate
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
TODAY = date(2026, 8, 25)

REAL_ACC = "SE4550000000005839825"
FRAUD_ACC = "SE9160000000000944411"

SUPPLIERS = [
    # (name, orgnr, account, amount, due, institution)
    ("Hygienpartner Nord AB", "556811-2340", "SE2880000832790000012345", 6200, "2026-08-25", "Swedbank"),
    ("Lokalhyra Slussen Fastigheter AB", "556455-7811", "SE3550000000054910001003", 5000, "2026-08-25", "SEB"),
    ("Städmaskiner Sverige AB", "556690-4471", "SE7160000000000012377101", 4800, "2026-08-25", "Handelsbanken"),
    ("Arbetskläder Direkt AB", "559012-8834", "SE1412000000012340005678", 3400, "2026-08-26", "Danske Bank"),
    ("Kontorsservice Väst AB", "556733-9022", "SE9350000000005401234567", 2900, "2026-08-26", "SEB"),
    ("Fordonsleasing Stockholm AB", "556520-1188", "SE6980000000123400112233", 7300, "2026-08-26", "Swedbank"),
    ("Försäkringsbolaget Trygg AB", "516401-6770", "SE8160000000000998877665", 5100, "2026-08-27", "Handelsbanken"),
    ("Telefoni & IT Norden AB", "559233-4150", "SE2412000000013579024680", 2600, "2026-08-27", "Danske Bank"),
    ("Bränsle & Energi Sverige AB", "556602-7789", "SE5550000000012345098765", 4700, "2026-08-27", "SEB"),
    ("Marknadsföring Digital AB", "559108-6612", "SE7280000832790112233445", 4500, "2026-08-28", "Swedbank"),
    ("Redovisningsbyrån Siffror AB", "556940-2201", "SE4160000000000112358132", 6000, "2026-08-29", "Handelsbanken"),
    ("Grossist Rengöring AB", "556877-5566", "SE9912000000098765432100", 3500, "2026-08-30", "Danske Bank"),
    ("Kaffe & Kontor Norden AB", "559350-9977", "SE3350000000009876501234", 4000, "2026-08-31", "SEB"),
]

STADGROSSISTEN = ("Städgrossisten AB", "556677-8899")

# --- payroll: 6 employees, sum 182,000/month (matches the salaries obligation) ---
# Jonas changed his on-file account TODAY (after this morning's payroll ran):
# 18 salary payments say ...7301; the new account has never been paid.
EMPLOYEES = [
    # (personnummer-ish id, name, role, salary, hist_account, current_account, changed_at)
    ("19860412-2398", "Anna Lindqvist", "Owner / operations", 35000,
     "SE2850000000054400001111", "SE2850000000054400001111", None),
    ("19910305-4412", "Jonas Bergström", "Team lead", 32000,
     "SE4550000000058300007301", "SE7130000000009944882216", "2026-08-25"),
    ("19880922-1157", "Maria Kowalczyk", "Cleaner", 31500,
     "SE1250000000012340002222", "SE1250000000012340002222", None),
    ("19950714-3388", "Erik Sandberg", "Cleaner", 30000,
     "SE9850000000067890003333", "SE9850000000067890003333", None),
    ("19930228-5501", "Fatima Al-Rashid", "Cleaner", 28500,
     "SE3350000000045670004444", "SE3350000000045670004444", None),
    ("19990106-7724", "Lucas Öberg", "Cleaner (part-time)", 25000,
     "SE6650000000078900005555", "SE6650000000078900005555", None),
]
assert sum(e[3] for e in EMPLOYEES) == 182000


def month_iter(start_y, start_m, n):
    y, m = start_y, start_m
    for _ in range(n):
        yield y, m
        m += 1
        if m > 12:
            m, y = 1, y + 1


def gen_supplier_invoices():
    inv = []
    # -- today's pile: 13 clean + 1 fraud --
    for i, (name, orgnr, acc, amount, due, inst) in enumerate(SUPPLIERS, start=1):
        inv.append({
            "id": f"SI-2026-{1400+i}", "reference": f"{7300+i}",
            "supplier_name": name, "supplier_orgnr": orgnr,
            "amount": float(amount), "currency": "SEK",
            "issue_date": "2026-08-18", "due_date": due,
            "account_id": acc, "institution": inst, "source": "seed",
        })
    inv.append({
        "id": "SI-2026-1499", "reference": "31047",
        "supplier_name": STADGROSSISTEN[0], "supplier_orgnr": STADGROSSISTEN[1],
        "amount": 48000.0, "currency": "SEK",
        "issue_date": "2026-08-22", "due_date": "2026-08-27",
        "account_id": FRAUD_ACC, "institution": "unknown", "source": "seed",
    })
    return inv


def gen_history_invoices():
    """Paid supplier invoices from the past — same accounts as today's clean pile."""
    hist = []
    n = 0
    # 3 recent months per clean supplier
    for name, orgnr, acc, amount, _due, inst in SUPPLIERS:
        for k, (y, m) in enumerate(month_iter(2026, 5, 3)):
            n += 1
            hist.append({
                "id": f"SI-H-{n:04d}", "reference": f"H{n:04d}",
                "supplier_name": name, "supplier_orgnr": orgnr,
                "amount": float(amount), "currency": "SEK",
                "issue_date": f"{y}-{m:02d}-05", "due_date": f"{y}-{m:02d}-20",
                "account_id": acc, "institution": inst, "source": "seed",
            })
    # Städgrossisten: 31 monthly invoices Jan 2024 -> Jul 2026, ALL to the real account
    for k, (y, m) in enumerate(month_iter(2024, 1, 31)):
        n += 1
        hist.append({
            "id": f"SI-SG-{k+1:02d}", "reference": f"3{700+k}",
            "supplier_name": STADGROSSISTEN[0], "supplier_orgnr": STADGROSSISTEN[1],
            "amount": float(38000 + (k * 811) % 14000), "currency": "SEK",
            "issue_date": f"{y}-{m:02d}-20", "due_date": f"{y}-{m:02d}-30" if m != 2 else f"{y}-{m:02d}-28",
            "account_id": REAL_ACC, "institution": "SEB", "source": "seed",
        })
    return hist


def gen_transactions():
    """Outgoing bank payments (the truth). Mirrors history invoices."""
    tx = []
    n = 0
    for name, orgnr, acc, amount, _due, inst in SUPPLIERS:
        for y, m in month_iter(2026, 5, 3):
            n += 1
            tx.append({
                "id": f"TX-{n:05d}", "booking_date": f"{y}-{m:02d}-20",
                "amount": -float(amount), "currency": "SEK",
                "creditor_name": name, "creditor_account": acc,
                "creditor_orgnr": orgnr, "source": "seed",
            })
    for k, (y, m) in enumerate(month_iter(2024, 1, 31)):
        n += 1
        tx.append({
            "id": f"TX-SG-{k+1:02d}", "booking_date": f"{y}-{m:02d}-28" if m != 2 else f"{y}-{m:02d}-26",
            "amount": -float(38000 + (k * 811) % 14000), "currency": "SEK",
            "creditor_name": STADGROSSISTEN[0], "creditor_account": REAL_ACC,
            "creditor_orgnr": STADGROSSISTEN[1], "source": "seed",
        })
    return tx


def gen_receivables():
    rec = []
    # Elgiganten: 9 paid, lateness [20,21,22,23,24,22,21,23,22] => mean 22.0
    lateness = [20, 21, 22, 23, 24, 22, 21, 23, 22]
    for k, ((y, m), late) in enumerate(zip(month_iter(2025, 11, 9), lateness), start=1):
        due = date(y, m, 6)
        rec.append({
            "id": f"SO-EL-{k:02d}", "customer_name": "Elgiganten AB",
            "amount": float(88000 + k * 1000), "currency": "SEK",
            "due_date": due.isoformat(),
            "paid_date": (due + timedelta(days=late)).isoformat(),
            "source": "seed",
        })
    # the outstanding one that funds Friday
    rec.append({
        "id": "SO-EL-10", "customer_name": "Elgiganten AB",
        "amount": 96000.0, "currency": "SEK",
        "due_date": "2026-08-06", "paid_date": None, "source": "seed",
    })
    # a punctual customer for texture (already paid; no effect on plan)
    rec.append({
        "id": "SO-CO-01", "customer_name": "Coor Service Management AB",
        "amount": 54000.0, "currency": "SEK",
        "due_date": "2026-08-10", "paid_date": "2026-08-11", "source": "seed",
    })
    return rec


def gen_obligations():
    return [
        {"name": "Skattekonto: moms + arbetsgivaravgifter", "amount": 84000.0, "due_date": "2026-08-27"},
        {"name": "Salaries (6 employees)", "amount": 182000.0, "due_date": "2026-09-25"},
    ]


def gen_employees():
    return [{
        "id": pid, "name": name, "role": role, "monthly_salary": float(sal),
        "account_id": cur, "account_changed_at": changed, "source": "seed",
    } for pid, name, role, sal, _hist, cur, changed in EMPLOYEES]


def gen_salary_transactions():
    """18 months of salary payments (Feb 2025 → Jul 2026) to HISTORICAL accounts."""
    tx = []
    n = 0
    for k, (y, m) in enumerate(month_iter(2025, 2, 18)):
        for pid, name, _role, sal, hist, _cur, _ch in EMPLOYEES:
            n += 1
            tx.append({
                "id": f"TX-SAL-{n:04d}", "booking_date": f"{y}-{m:02d}-25",
                "amount": -float(sal), "currency": "SEK",
                "creditor_name": name, "creditor_account": hist,
                "creditor_orgnr": pid, "source": "seed",
            })
    return tx


def main():
    balance = {"balance": 148200.0, "currency": "SEK", "account_name": "Företagskonto",
               "iban": "SE3550000000054910000003", "as_of": TODAY.isoformat(), "source": "seed"}
    files = {
        "supplier_invoices.json": gen_supplier_invoices(),
        "history_invoices.json": gen_history_invoices(),
        "transactions.json": gen_transactions() + gen_salary_transactions(),
        "receivables.json": gen_receivables(),
        "obligations.json": gen_obligations(),
        "balance.json": balance,
        "employees.json": gen_employees(),
    }
    for fname, data in files.items():
        (HERE / fname).write_text(json.dumps(data, indent=1, ensure_ascii=False))

    # ---- story invariants ----
    cur = files["supplier_invoices.json"]
    clean = [i for i in cur if i["account_id"] != FRAUD_ACC]
    fraud = [i for i in cur if i["account_id"] == FRAUD_ACC]
    assert len(cur) == 14 and len(fraud) == 1
    assert sum(i["amount"] for i in clean) == 60000
    early = [i for i in clean if i["due_date"] <= "2026-08-27"]
    late = [i for i in clean if i["due_date"] >= "2026-08-28"]
    assert len(early) == 9 and sum(i["amount"] for i in early) == 42000
    assert len(late) == 4 and sum(i["amount"] for i in late) == 18000
    assert 148200 - 60000 - 84000 == 4200
    sg_tx = [t for t in files["transactions.json"] if t["creditor_orgnr"] == STADGROSSISTEN[1]]
    assert len(sg_tx) == 31 and all(t["creditor_account"] == REAL_ACC for t in sg_tx)
    el = [r for r in files["receivables.json"] if r["customer_name"] == "Elgiganten AB" and r["paid_date"]]
    mean_late = sum(
        (date.fromisoformat(r["paid_date"]) - date.fromisoformat(r["due_date"])).days for r in el
    ) / len(el)
    assert mean_late == 22.0, mean_late
    # payroll invariants
    emps = files["employees.json"]
    assert sum(e["monthly_salary"] for e in emps) == 182000
    sal_tx = [t for t in files["transactions.json"] if t["id"].startswith("TX-SAL")]
    assert len(sal_tx) == 18 * 6
    jonas = next(e for e in emps if e["name"].startswith("Jonas"))
    jonas_hist = {t["creditor_account"] for t in sal_tx if t["creditor_orgnr"] == jonas["id"]}
    assert jonas_hist == {"SE4550000000058300007301"} and jonas["account_id"] not in jonas_hist
    print(f"seed OK: {len(cur)} current invoices, {len(files['history_invoices.json'])} history, "
          f"{len(files['transactions.json'])} transactions ({len(sal_tx)} salary), "
          f"{len(emps)} employees, mean Elgiganten lateness {mean_late} days")


if __name__ == "__main__":
    main()
