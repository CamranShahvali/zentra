"""Zentra agent — orchestrates the pipeline, uses Claude (via local claude CLI)
to write the morning briefing. Falls back to a deterministic template.

Design rule the whole product stands on:
  * verdicts come from fraud.py (deterministic), never from the LLM;
  * the LLM writes language, chooses emphasis — it cannot overrule a HOLD;
  * no tool can move money; staging a basket is the ceiling of its authority.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from datetime import date

from . import audit, config, datalayer, fraud, planner


def run_pipeline(mode: str | None = None) -> dict:
    """Deterministic part: gather world -> screen -> plan. Fully audited."""
    audit.clear()
    w = datalayer.get_world(mode)
    audit.log("get_invoices", f"mode={mode or config.DATA_MODE}",
              f"{len(w.invoices)} due invoices, {len(w.history_invoices)} history")
    audit.log("get_balance", "account=Företagskonto",
              f"{w.balance:.0f} {w.currency} (source: {w.sources.get('balance')})")
    audit.log("get_transactions", "bookingStatus=booked since 2024-01",
              f"{len(w.transactions)} outgoing payments")

    verdicts = []
    trusted = datalayer.trusted_pairs()
    if trusted:
        audit.log("load_trusted_accounts", f"{len(trusted)} owner-verified pairs", "loaded")
    for inv in w.invoices:
        v = fraud.verify(inv, w.history_invoices, w.transactions, trusted)
        verdicts.append(v)
        audit.log("verify_invoice",
                  f"{inv.id} {inv.supplier_name} -> {inv.account_id[-6:]}",
                  f"{v.status}: {v.reason[:120]}")

    held = [v for v in verdicts if v.status == "HOLD"]
    review = [v for v in verdicts if v.status == "REVIEW"]
    cleared_ids = {v.invoice_id for v in verdicts if v.status == "CLEAR"}
    cleared = [i for i in w.invoices if i.id in cleared_ids]

    today = date.fromisoformat(config.DEMO_TODAY)
    items, projection = planner.plan(
        cleared, w.balance, w.receivables, w.obligations,
        today=today, buffer_floor=config.BUFFER_FLOOR_SEK,
    )
    audit.log("plan_payments",
              f"{len(cleared)} cleared invoices, floor={config.BUFFER_FLOOR_SEK}",
              f"naive min {projection['naive']['min_balance']:.0f} -> planned min "
              f"{projection['planned']['min_balance']:.0f}")

    inv_by_id = {i.id: i for i in w.invoices}
    pay_today = [p for p in items if p.pay_date == config.DEMO_TODAY]
    pay_later = [p for p in items if p.pay_date != config.DEMO_TODAY]

    return {
        "today": config.DEMO_TODAY,
        "world": w,
        "verdicts": verdicts,
        "held": held,
        "review": review,
        "cleared": cleared,
        "plan": items,
        "projection": projection,
        "pay_today": pay_today,
        "pay_later": pay_later,
        "inv_by_id": inv_by_id,
        "totals": {
            "due_count": len(w.invoices),
            "due_sum": sum(i.amount for i in w.invoices),
            "held_sum": sum(inv_by_id[v.invoice_id].amount for v in held),
            "today_sum": sum(inv_by_id[p.invoice_id].amount for p in pay_today),
            "later_sum": sum(inv_by_id[p.invoice_id].amount for p in pay_later),
        },
    }


# ---------- briefing text ----------

def _facts_for_llm(r: dict) -> str:
    w = r["world"]
    held_lines = []
    for v in r["held"]:
        inv = r["inv_by_id"][v.invoice_id]
        ev = v.evidence
        known = ev.get("known_accounts") or [{}]
        held_lines.append(
            f"- HOLD {inv.supplier_name} ({inv.amount:.0f} SEK, due {inv.due_date}): "
            f"paid {known[0].get('times_paid', '?')}x to {known[0].get('account', '?')[-6:]} "
            f"since {known[0].get('first_seen', '?')[:7]}; this invoice names NEW account "
            f"{ev.get('new_account', '?')[-6:]}."
        )
    plan_lines = [
        f"- {r['inv_by_id'][p.invoice_id].supplier_name}: {r['inv_by_id'][p.invoice_id].amount:.0f} SEK on {p.pay_date} ({p.reason})"
        for p in r["plan"]
    ]
    proj = r["projection"]
    inflow = proj["inflows"][0] if proj["inflows"] else None
    return "\n".join([
        f"Date: {r['today']}. Company: cleaning firm, 6 employees, no finance department.",
        f"Bank balance: {w.balance:.0f} SEK.",
        f"Invoices due: {r['totals']['due_count']} totalling {r['totals']['due_sum']:.0f} SEK.",
        f"Held by fraud screen: {len(r['held'])} ({r['totals']['held_sum']:.0f} SEK).",
        *held_lines,
        f"Obligations: " + "; ".join(f"{o.name} {o.amount:.0f} SEK on {o.due_date}" for o in w.obligations),
        f"If everything were paid today, lowest projected balance: {proj['naive']['min_balance']:.0f} SEK "
        f"(buffer floor {proj['buffer_floor']:.0f}).",
        f"Planned instead: {len(r['pay_today'])} invoices today ({r['totals']['today_sum']:.0f} SEK), "
        f"{len(r['pay_later'])} later ({r['totals']['later_sum']:.0f} SEK); "
        f"lowest projected balance {proj['planned']['min_balance']:.0f} SEK.",
        (f"Key expected inflow: {inflow['customer']} {inflow['amount']:.0f} SEK around {inflow['date']} "
         f"(historically pays {inflow['avg_lateness_days']:.0f} days late)." if inflow else ""),
        "Payment plan:",
        *plan_lines,
    ])


SYSTEM_PROMPT = (
    "You are Zentra, an AI finance employee for a small Swedish company. "
    "You prepare everything; you can never move money — only the owner signs, in their own bank. "
    "Write the owner's morning briefing from the FACTS below. Rules: "
    "(1) 120-170 words, plain English, no jargon, no markdown headers; "
    "(2) lead with what you HELD and why, in one or two crisp sentences — "
    "include the times-paid history and that the bank will not check this; "
    "(3) then the timing plan and the single number that justifies it; "
    "(4) mention the expected late customer payment if relevant; "
    "(5) end with exactly what you prepared and that one signature in their bank completes it; "
    "(6) never claim a payment was sent; never soften a HOLD. "
    "Numbers: use thousands separators like 48 000 SEK."
)


def briefing_llm(facts: str) -> str | None:
    """Ask the local Claude Code CLI for the briefing. None on any failure."""
    exe = shutil.which("claude")
    if not exe or config.LLM_BACKEND != "claude-code":
        return None
    try:
        proc = subprocess.run(
            [exe, "-p", "--model", "sonnet", "--max-turns", "1"],
            input=f"{SYSTEM_PROMPT}\n\nFACTS:\n{facts}\n\nWrite the briefing now.",
            capture_output=True, text=True, timeout=60,
        )
        text = proc.stdout.strip()
        if proc.returncode == 0 and 200 < len(text) < 2000:
            return text
    except Exception:
        pass
    return None


def briefing_template(r: dict) -> str:
    held_txt = ""
    if r["held"]:
        v = r["held"][0]
        inv = r["inv_by_id"][v.invoice_id]
        known = (v.evidence.get("known_accounts") or [{}])[0]
        held_txt = (
            f"I have held one invoice. {inv.supplier_name} — {inv.amount:,.0f} SEK — has been paid "
            f"{known.get('times_paid', 'many')} times to the same account since "
            f"{str(known.get('first_seen', ''))[:7]}. Today's invoice names a different account, "
            f"seen for the first time. Your bank will not check this. Call them on the number "
            f"you already have before anything moves. "
        ).replace(",", " ")
    proj = r["projection"]
    inflow = proj["inflows"][0] if proj["inflows"] else None
    plan_txt = (
        f"Of the cleared invoices, paying everything today would take the balance down to "
        f"{proj['naive']['min_balance']:,.0f} SEK before the tax payment — under your "
        f"{proj['buffer_floor']:,.0f} SEK buffer. So: {len(r['pay_today'])} invoices today "
        f"({r['totals']['today_sum']:,.0f} SEK), {len(r['pay_later'])} on "
        f"{r['pay_later'][0].pay_date if r['pay_later'] else '—'} "
    ).replace(",", " ")
    if inflow:
        plan_txt += (
            f"when {inflow['customer']}'s {inflow['amount']:,.0f} SEK should land — they average "
            f"{inflow['avg_lateness_days']:.0f} days late, and I plan around how customers actually "
            f"pay, not when they promise to. "
        ).replace(",", " ")
    close = (
        f"I have prepared the {len(r['pay_today'])} payments for today as one batch. "
        f"One signature in your bank completes it — I cannot sign, by design."
    )
    return held_txt + plan_txt + close


def morning_briefing(mode: str | None = None, use_llm: bool = True) -> dict:
    r = run_pipeline(mode)
    facts = _facts_for_llm(r)
    text = briefing_llm(facts) if use_llm else None
    author = "claude"
    if not text:
        text = briefing_template(r)
        author = "template"
    audit.log("write_briefing", f"author={author}", text[:150])

    w = r["world"]
    return {
        "today": r["today"],
        "briefing": text,
        "briefing_author": author,
        "balance": w.balance,
        "currency": w.currency,
        "sources": w.sources,
        "totals": r["totals"],
        "held": [
            {**v.to_dict(), "invoice": r["inv_by_id"][v.invoice_id].to_dict()}
            for v in r["held"]
        ],
        "review": [
            {**v.to_dict(), "invoice": r["inv_by_id"][v.invoice_id].to_dict()}
            for v in r["review"]
        ],
        "cleared": [
            {
                "invoice": r["inv_by_id"][p.invoice_id].to_dict(),
                "pay_date": p.pay_date,
                "reason": p.reason,
                "verdict": next(v.to_dict() for v in r["verdicts"] if v.invoice_id == p.invoice_id),
            }
            for p in r["plan"]
        ],
        "projection": r["projection"],
        "obligations": [o.to_dict() for o in w.obligations],
    }


if __name__ == "__main__":
    out = morning_briefing()
    print(f"[{out['briefing_author']}]")
    print(out["briefing"])
    print("\nheld:", len(out["held"]), "| cleared:", len(out["cleared"]))
