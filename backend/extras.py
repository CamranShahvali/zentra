"""Zentra extras — monthly report, invoice-file extraction, product assistant.

All three follow the house rule: deterministic data first, LLM only for language,
never for verdicts, never for actions.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from datetime import date

from . import audit, config, datalayer


# ---------------- monthly report ----------------

def month_report(briefing: dict, year: int, month: int) -> dict:
    """Deterministic monthly statement from the world + screening results.

    In production this is generated on the 1st and delivered by email/Slack;
    the demo generates it on demand (honestly labeled).
    """
    w = datalayer.get_world()
    prefix = f"{year}-{month:02d}"
    paid_tx = [t for t in w.transactions if t.booking_date.startswith(prefix)]
    fallback_note = None
    if not paid_tx:
        # no bank activity in the requested month (young sandbox data) — use the
        # latest month that HAS activity, and say so honestly instead of showing zeros
        months = sorted({t.booking_date[:7] for t in w.transactions if t.amount < 0})
        if months:
            actual = months[-1]
            fallback_note = (f"No bank payments recorded in {prefix}; showing the most "
                             f"recent active month {actual} instead.")
            prefix = actual
            paid_tx = [t for t in w.transactions if t.booking_date.startswith(prefix)]
    paid_out = sum(-t.amount for t in paid_tx if t.amount < 0)

    open_invoices = []
    for group, label in ((briefing["held"], "HELD"), (briefing["review"], "REVIEW")):
        for item in group:
            inv = item["invoice"]
            open_invoices.append({
                "supplier": inv["supplier_name"], "amount": inv["amount"],
                "due": inv["due_date"], "status": label,
                "why_not_paid": item["reason"],
            })
    for c in briefing["cleared"]:
        inv = c["invoice"]
        open_invoices.append({
            "supplier": inv["supplier_name"], "amount": inv["amount"],
            "due": inv["due_date"], "status": f"SCHEDULED {c['pay_date']}",
            "why_not_paid": c["reason"],
        })

    by_supplier: dict[str, float] = {}
    for t in paid_tx:
        if t.amount < 0 and t.creditor_name:
            by_supplier[t.creditor_name] = by_supplier.get(t.creditor_name, 0) - t.amount
    top_costs = sorted(by_supplier.items(), key=lambda kv: -kv[1])[:8]

    outstanding_in = [r.to_dict() for r in w.receivables if not r.paid_date]

    report = {
        "period": prefix,
        "period_note": fallback_note,
        "generated_at": date.today().isoformat(),
        "delivery": "on-demand (production: auto-generated on the 1st, delivered by email)",
        "bank_balance": w.balance,
        "paid_out_total": round(paid_out, 2),
        "paid_out_count": sum(1 for t in paid_tx if t.amount < 0),
        "top_costs": [{"name": n, "amount": round(a, 2)} for n, a in top_costs],
        "open_invoices": sorted(open_invoices, key=lambda x: x["due"]),
        "money_owed_to_you": outstanding_in,
        "payroll_monthly": briefing.get("payroll", {}).get("total_monthly"),
        "alerts": {
            "invoices_held": len(briefing["held"]),
            "payroll_held": len(briefing.get("payroll", {}).get("held", [])),
        },
    }
    audit.log("generate_report", f"period={prefix}",
              f"{report['paid_out_count']} payments out, "
              f"{len(open_invoices)} open invoices, {len(outstanding_in)} receivables open")
    return report


def month_report_text(report: dict) -> str:
    """Plain-language narration of the report (LLM with template fallback)."""
    facts = json.dumps(report, ensure_ascii=False)
    exe = shutil.which("claude")
    if exe and config.LLM_BACKEND == "claude-code":
        try:
            p = subprocess.run(
                [exe, "-p", "--model", "sonnet", "--max-turns", "1"],
                input=("Write a monthly financial statement for a small-business owner "
                       "from this JSON. Plain English, no jargon, max 150 words. Cover: "
                       "money out, biggest costs, what is still unpaid and why (held/"
                       "scheduled), who owes us money, and any alerts. Never invent "
                       f"numbers.\n\nJSON:\n{facts}"),
                capture_output=True, text=True, timeout=60,
            )
            t = p.stdout.strip()
            if p.returncode == 0 and 100 < len(t) < 2000:
                return t
        except Exception:
            pass
    # template fallback
    tc = ", ".join(f"{c['name']} ({c['amount']:,.0f})".replace(",", " ")
                   for c in report["top_costs"][:3]) or "—"
    held = [i for i in report["open_invoices"] if i["status"] == "HELD"]
    return (
        f"In {report['period']} the company paid out {report['paid_out_total']:,.0f} SEK "
        f"across {report['paid_out_count']} payments. Largest costs: {tc}. "
        f"{len(report['open_invoices'])} invoices are open; "
        f"{len(held)} held ({held[0]['supplier'] if held else '—'}: "
        f"{held[0]['why_not_paid'][:80] if held else ''}…). "
        f"Customers owe {sum(r['amount'] for r in report['money_owed_to_you']):,.0f} SEK. "
        f"Payroll runs at {report['payroll_monthly']:,.0f} SEK/month."
    ).replace(",", " ")


# ---------------- invoice file extraction ----------------

EXTRACT_PROMPT = """Extract these fields from the invoice text below and answer with ONLY a JSON object:
{"supplier_name": str|null, "supplier_orgnr": str|null (format NNNNNN-NNNN),
 "amount": number|null (total incl VAT), "currency": str|null,
 "due_date": "YYYY-MM-DD"|null, "issue_date": "YYYY-MM-DD"|null,
 "reference": str|null (invoice number), "account_id": str|null
 (bankgiro/plusgiro/IBAN the invoice asks to be paid to)}
No prose. If a field is absent use null. INVOICE TEXT:
"""


def extract_invoice(file_bytes: bytes, filename: str) -> dict:
    """Extract invoice fields from an uploaded file. Text-first; LLM for parsing.
    Returns {fields, confidence, method}. NEVER auto-registers — the user reviews."""
    config.UPLOAD_DIR.mkdir(exist_ok=True)
    safe = "".join(c for c in filename if c.isalnum() or c in "._-")[:80]
    path = config.UPLOAD_DIR / safe
    path.write_bytes(file_bytes)

    text = ""
    if filename.lower().endswith(".pdf"):
        try:
            import subprocess as sp
            r = sp.run(["pdftotext", str(path), "-"], capture_output=True, text=True, timeout=30)
            text = r.stdout if r.returncode == 0 else ""
        except Exception:
            text = ""
    elif filename.lower().endswith((".txt", ".text")):
        text = file_bytes.decode(errors="replace")

    if not text.strip():
        audit.log("extract_invoice", filename, "no text layer — manual entry required")
        return {"fields": {}, "confidence": 0.0, "method": "none",
                "detail": "Could not read text from this file (scanned image?). "
                          "Fill the form manually — the screening is identical either way."}

    exe = shutil.which("claude")
    if exe and config.LLM_BACKEND == "claude-code":
        try:
            p = subprocess.run(
                [exe, "-p", "--model", "sonnet", "--max-turns", "1"],
                input=EXTRACT_PROMPT + text[:6000],
                capture_output=True, text=True, timeout=60,
            )
            raw = p.stdout.strip()
            start, end = raw.find("{"), raw.rfind("}")
            if p.returncode == 0 and start >= 0 < end:
                fields = json.loads(raw[start:end + 1])
                filled = sum(1 for v in fields.values() if v)
                audit.log("extract_invoice", filename,
                          f"AI extracted {filled}/8 fields — pending human review")
                return {"fields": fields, "confidence": round(filled / 8, 2),
                        "method": "claude", "detail": "Review before registering — "
                        "extraction is a draft, screening is the authority."}
        except Exception:
            pass

    audit.log("extract_invoice", filename, "text read; AI parse unavailable")
    return {"fields": {}, "confidence": 0.0, "method": "text-only",
            "detail": "File read but automatic parsing unavailable — fill manually."}


# ---------------- product assistant ----------------

ASSISTANT_SYSTEM = """You are the Zentra assistant. You ONLY answer questions about the
Zentra application the user is looking at: what its screens show, how its checks work,
what its numbers mean, and what the user can do in it. You have the app's live state in
CONTEXT.

Hard rules:
- If asked about anything outside Zentra (general advice, other products, coding, the
  world), reply exactly: "I can only help with Zentra — ask me about anything you see
  in the app."
- You cannot perform actions: no paying, no staging, no trusting accounts, no creating
  invoices. When asked to act, explain WHERE in the app the human does it, and that
  Zentra by design never moves money — the owner signs in their own bank.
- Verdicts come from Zentra's deterministic rules; never second-guess a HOLD.
- Max 120 words. Plain language. Use the CONTEXT numbers, never invent any.
"""


def assistant_reply(question: str, briefing: dict) -> dict:
    ctx = {
        "today": briefing["today"], "balance": briefing["balance"],
        "held_invoices": [{"supplier": h["invoice"]["supplier_name"],
                           "amount": h["invoice"]["amount"], "reason": h["reason"]}
                          for h in briefing["held"]],
        "payroll_held": [{"employee": h["employee"]["name"], "reason": h["reason"]}
                         for h in briefing.get("payroll", {}).get("held", [])],
        "cleared_count": len(briefing["cleared"]),
        "plan": [{"supplier": c["invoice"]["supplier_name"], "pay_date": c["pay_date"]}
                 for c in briefing["cleared"]][:20],
        "projection_min_planned": briefing["projection"]["planned"]["min_balance"],
        "projection_min_naive": briefing["projection"]["naive"]["min_balance"],
        "screens": ["Overview", "Invoices (+ New invoice, notes, pause supplier)",
                    "Payroll", "Payments (stage basket — you sign in your bank)",
                    "Customers", "Reports", "Connections", "Agent log"],
    }
    exe = shutil.which("claude")
    if exe and config.LLM_BACKEND == "claude-code":
        try:
            p = subprocess.run(
                [exe, "-p", "--model", "sonnet", "--max-turns", "1"],
                input=f"{ASSISTANT_SYSTEM}\n\nCONTEXT:\n{json.dumps(ctx, ensure_ascii=False)}"
                      f"\n\nUSER QUESTION: {question[:500]}\n\nAnswer:",
                capture_output=True, text=True, timeout=60,
            )
            t = p.stdout.strip()
            if p.returncode == 0 and 0 < len(t) < 1500:
                audit.log("assistant", question[:80], t[:100])
                return {"answer": t, "author": "claude"}
        except Exception:
            pass
    # deterministic fallback: answer the most common questions from context
    q = question.lower()
    if "held" in q or "stopp" in q or "hold" in q:
        hs = ctx["held_invoices"]
        a = (f"{len(hs)} invoice(s) are held. " +
             " ".join(f"{h['supplier']} ({h['amount']:,.0f} SEK): {h['reason']}"
                      for h in hs))[:600].replace(",", " ")
    elif "payroll" in q or "salary" in q or "lön" in q:
        ph = ctx["payroll_held"]
        a = (f"Payroll: {len(ph)} salary account(s) held. " +
             " ".join(f"{h['employee']}: {h['reason'][:120]}" for h in ph)) if ph \
            else "All salary accounts match their payment history."
    elif "sign" in q or "pay" in q or "betala" in q:
        a = ("Zentra stages payments on the Payments page, but it cannot sign or send "
             "money. You sign once, in your own bank, with BankID. That separation is "
             "by design.")
    else:
        a = (f"Balance {ctx['balance']:,.0f} SEK; {ctx['cleared_count']} invoices "
             f"cleared; {len(ctx['held_invoices'])} held. Ask about held invoices, "
             "payroll, the plan, or any screen.").replace(",", " ")
    audit.log("assistant", question[:80], f"[template] {a[:100]}")
    return {"answer": a, "author": "template"}
