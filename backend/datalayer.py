"""Zentra data layer — one world, three modes (seed | live | hybrid)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from . import config
from .models import Invoice, Obligation, Receivable, Transaction


@dataclass
class World:
    invoices: list[Invoice] = field(default_factory=list)          # today's unpaid pile
    history_invoices: list[Invoice] = field(default_factory=list)  # paid, past
    transactions: list[Transaction] = field(default_factory=list)  # bank outgoing
    receivables: list[Receivable] = field(default_factory=list)
    obligations: list[Obligation] = field(default_factory=list)
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
        return _seed_world()
    if mode in ("hybrid", "live"):
        return _merge_live(_seed_world())
    raise ValueError(f"unknown DATA_MODE {mode!r}")


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
