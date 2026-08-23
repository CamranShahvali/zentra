"""Zentra data layer — one world, three modes (seed | live | hybrid)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from . import config
from .models import Employee, Invoice, Obligation, Receivable, Transaction


@dataclass
class World:
    invoices: list[Invoice] = field(default_factory=list)          # today's unpaid pile
    history_invoices: list[Invoice] = field(default_factory=list)  # paid, past
    transactions: list[Transaction] = field(default_factory=list)  # bank outgoing
    receivables: list[Receivable] = field(default_factory=list)
    obligations: list[Obligation] = field(default_factory=list)
    employees: list[Employee] = field(default_factory=list)
    balance: float = 0.0
    currency: str = "SEK"
    balance_meta: dict = field(default_factory=dict)
    sources: dict = field(default_factory=dict)  # component -> live|seed

    def to_dict(self) -> dict:
        return {
            "invoices": [i.to_dict() for i in self.invoices],
            "history_count": len(self.history_invoices),
            "transaction_count": len(self.transactions),
            "receivables": [r.to_dict() for r in self.receivables],
            "obligations": [o.to_dict() for o in self.obligations],
            "balance": self.balance,
            "currency": self.currency,
            "balance_meta": self.balance_meta,
            "sources": self.sources,
        }


def _load_json(name: str):
    return json.loads((config.SEED_DIR / name).read_text())


def _seed_world() -> World:
    w = World()
    w.invoices = [Invoice(**d) for d in _load_json("supplier_invoices.json")]
    w.history_invoices = [Invoice(**d) for d in _load_json("history_invoices.json")]
    w.transactions = [Transaction(**d) for d in _load_json("transactions.json")]
    w.receivables = [Receivable(**d) for d in _load_json("receivables.json")]
    w.obligations = [Obligation(**d) for d in _load_json("obligations.json")]
    try:
        w.employees = [Employee(**d) for d in _load_json("employees.json")]
    except FileNotFoundError:
        w.employees = []
    bal = _load_json("balance.json")
    w.balance = float(bal["balance"])
    w.currency = bal.get("currency", "SEK")
    w.balance_meta = bal
    w.sources = {k: "seed" for k in
                 ("invoices", "history", "transactions", "receivables", "obligations", "balance")}
    return w


def _merge_live(w: World) -> World:
    """Overlay live sandbox data where available; keep seed for the story parts.

    Live components are additive (invoices/receivables appended, deduped by id)
    or replacing (balance) — every record keeps its source tag.
    """
    try:
        from . import zwapgrid
        live_inv = zwapgrid.get_supplier_invoices_cached()
        known = {i.id for i in w.invoices} | {i.id for i in w.history_invoices}
        added = [i for i in live_inv if i.id not in known]
        w.invoices.extend(added)
        if added or live_inv:
            w.sources["invoices"] = "live+seed"
    except Exception as e:  # sandbox down / no consent yet — seed carries the demo
        w.sources["invoices_live_error"] = str(e)[:200]

    try:
        from . import openpayments
        live_bal = openpayments.get_balance_cached()
        if live_bal is not None:
            w.balance_meta["live_balance"] = live_bal
            w.sources["balance"] = "seed (live available: %s)" % live_bal.get("amount")
        live_tx = openpayments.get_transactions_cached()
        if live_tx:
            have = {t.id for t in w.transactions}
            w.transactions.extend(t for t in live_tx if t.id not in have)
            w.sources["transactions"] = "live+seed"
    except Exception as e:
        w.sources["op_live_error"] = str(e)[:200]
    return w


def get_world(mode: str | None = None) -> World:
    mode = mode or config.DATA_MODE
    if mode == "seed":
        w = _seed_world()
    elif mode in ("hybrid", "live"):
        w = _merge_live(_seed_world())
    else:
        raise ValueError(f"unknown DATA_MODE {mode!r}")
    # runtime overlay: invoices added through the UI (any mode)
    if config.RUNTIME_INVOICES.exists():
        try:
            extra = [Invoice(**d) for d in json.loads(config.RUNTIME_INVOICES.read_text())]
            have = {i.id for i in w.invoices}
            w.invoices.extend(i for i in extra if i.id not in have)
            if extra:
                w.sources["runtime_invoices"] = f"{len(extra)} added via UI"
        except Exception as e:
            w.sources["runtime_invoices_error"] = str(e)[:150]
    return w


def trusted_pairs() -> frozenset[tuple[str, str]]:
    """Owner-verified (orgnr_norm, account_norm) pairs."""
    from .models import _norm_account, _norm_orgnr
    if not config.TRUSTED_ACCOUNTS.exists():
        return frozenset()
    try:
        rows = json.loads(config.TRUSTED_ACCOUNTS.read_text())
        return frozenset((_norm_orgnr(r["orgnr"]), _norm_account(r["account"])) for r in rows)
    except Exception:
        return frozenset()


def invoice_notes() -> dict[str, list[dict]]:
    """invoice_id -> [{ts, text}] notes added by the owner."""
    if not config.INVOICE_NOTES.exists():
        return {}
    try:
        return json.loads(config.INVOICE_NOTES.read_text())
    except Exception:
        return {}


def add_invoice_note(invoice_id: str, text: str) -> dict:
    import time as _t
    notes = invoice_notes()
    entry = {"ts": _t.strftime("%Y-%m-%dT%H:%M:%S"), "text": text[:500]}
    notes.setdefault(invoice_id, []).append(entry)
    config.INVOICE_NOTES.write_text(json.dumps(notes, indent=1, ensure_ascii=False))
    return entry


def supplier_flags() -> dict[str, dict]:
    """orgnr_norm -> {paused: bool, reason, ts}."""
    if not config.SUPPLIER_FLAGS.exists():
        return {}
    try:
        return json.loads(config.SUPPLIER_FLAGS.read_text())
    except Exception:
        return {}


def set_supplier_paused(orgnr: str, paused: bool, reason: str = "") -> dict:
    import time as _t
    from .models import _norm_orgnr
    flags = supplier_flags()
    key = _norm_orgnr(orgnr)
    flags[key] = {"paused": paused, "reason": reason[:200],
                  "ts": _t.strftime("%Y-%m-%dT%H:%M:%S")}
    config.SUPPLIER_FLAGS.write_text(json.dumps(flags, indent=1, ensure_ascii=False))
    return flags[key]


def validate_world(w: World) -> dict:
    """Cross-checks that every number the UI shows is internally consistent.
    Returns {ok, checks: [{name, ok, detail}]}. Runs on startup and on demand."""
    checks = []

    def check(name, ok, detail=""):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    ids = [i.id for i in w.invoices]
    check("invoice ids unique", len(ids) == len(set(ids)), f"{len(ids)} invoices")
    check("no invoice both current and history",
          not ({i.id for i in w.invoices} & {i.id for i in w.history_invoices}))
    bad_dates = [i.id for i in w.invoices if i.due_date and i.issue_date and i.due_date < i.issue_date]
    check("due dates >= issue dates", not bad_dates, str(bad_dates))
    neg = [i.id for i in w.invoices if i.amount <= 0]
    check("invoice amounts positive", not neg, str(neg))
    orphans = [i.id for i in w.invoices if not i.supplier_orgnr]
    check("invoices carry orgnr (REVIEW otherwise)", True,
          f"{len(orphans)} without orgnr -> routed to REVIEW")
    sal_sum = sum(e.monthly_salary for e in w.employees)
    sal_ob = next((o.amount for o in w.obligations if "salar" in o.name.lower()), None)
    check("payroll sum matches salaries obligation",
          sal_ob is None or abs(sal_sum - sal_ob) < 1,
          f"employees {sal_sum:.0f} vs obligation {sal_ob}")
    # every receivable paid_date >= due implies lateness >= 0 is not required (early pay ok),
    # but paid receivables must have both dates parseable
    from datetime import date as _d
    bad_rec = []
    for r in w.receivables:
        try:
            _d.fromisoformat(r.due_date)
            if r.paid_date:
                _d.fromisoformat(r.paid_date)
        except Exception:
            bad_rec.append(r.id)
    check("receivable dates parseable", not bad_rec, str(bad_rec))
    check("balance positive", w.balance > 0, f"{w.balance:.0f} {w.currency}")
    dup_tx = len(w.transactions) - len({t.id for t in w.transactions})
    check("transaction ids unique", dup_tx == 0, f"{dup_tx} duplicates")
    return {"ok": all(c["ok"] for c in checks), "checks": checks}


if __name__ == "__main__":
    import sys
    w = get_world("seed")
    print(f"invoices={len(w.invoices)} history={len(w.history_invoices)} "
          f"tx={len(w.transactions)} receivables={len(w.receivables)} "
          f"obligations={len(w.obligations)} balance={w.balance} {w.currency}")
    if "--check" in sys.argv:
        assert len(w.invoices) == 14
        sg = [t for t in w.transactions if t.creditor_orgnr == "556677-8899"]
        assert len(sg) == 31
        assert w.balance - sum(i.amount for i in w.invoices if i.supplier_orgnr != "556677-8899") - 84000 == 4200
        print("story invariants OK (4200 SEK dip confirmed)")
