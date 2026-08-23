"""Zentra web app — FastAPI serving the API + static frontend."""
from __future__ import annotations

import json
import time
import uuid

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import agent, audit, config

app = FastAPI(title="Zentra", version="0.1.0")

ROOT = config.ROOT
FRONTEND = ROOT / "frontend"

_cache: dict = {"briefing": None, "at": 0.0}
_baskets: list[dict] = []


@app.get("/api/briefing")
def get_briefing(refresh: bool = False):
    if refresh or not _cache["briefing"] or time.time() - _cache["at"] > 600:
        _cache["briefing"] = agent.morning_briefing()
        _cache["at"] = time.time()
    return _cache["briefing"]


@app.get("/api/evidence/{invoice_id}")
def get_evidence(invoice_id: str):
    b = get_briefing()
    for group in ("held", "review"):
        for item in b[group]:
            if item["invoice_id"] == invoice_id:
                return item
    for item in b["cleared"]:
        if item["invoice"]["id"] == invoice_id:
            return item
    return JSONResponse({"error": "unknown invoice"}, status_code=404)


@app.post("/api/basket")
def stage_basket():
    """Stage today's cleared payments as one batch. NEVER signs, never sends."""
    b = get_briefing()
    today_items = [c for c in b["cleared"] if c["pay_date"] == b["today"]]
    payments = [
        {
            "instructedAmount": {"amount": str(c["invoice"]["amount"]), "currency": "SEK"},
            "creditorName": c["invoice"]["supplier_name"],
            "creditorAccount": {"iban": c["invoice"]["account_id"]},
            "remittanceInformationUnstructured": c["invoice"].get("reference") or c["invoice"]["id"],
        }
        for c in today_items
    ]
    basket = {
        "basket_id": f"ZB-{uuid.uuid4().hex[:8].upper()}",
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "payment_count": len(payments),
        "total": sum(c["invoice"]["amount"] for c in today_items),
        "currency": "SEK",
        "status": "STAGED — awaiting signature in your bank",
        "signed_by_zentra": False,
        "live_initiation": None,
    }
    # try live payment initiation in the sandbox; the demo works either way
    try:
        from . import openpayments
        result = openpayments.stage_payments(payments)
        if result.get("initiated"):
            basket["live_initiation"] = {
                "initiated": len(result["initiated"]),
                "ids": [r.get("paymentId") for r in result["initiated"]][:20],
            }
            basket["status"] = "STAGED at bank (sandbox) — awaiting signature"
        elif result.get("errors"):
            basket["live_initiation"] = {"errors": result["errors"][:3]}
    except Exception as e:
        basket["live_initiation"] = {"errors": [str(e)[:200]]}

    audit.log("stage_signing_basket",
              f"{basket['payment_count']} payments, {basket['total']:.0f} SEK",
              f"{basket['basket_id']} {basket['status']} (signed_by_zentra=false)")
    _baskets.append(basket)
    return basket


@app.get("/api/audit")
def get_audit():
    return {"entries": audit.read()}


# ---------- connections (onboarding) ----------

@app.get("/api/connections")
def connections_status():
    zg: dict = {"connected": False, "pending": False, "consent_id": None}
    try:
        from . import zwapgrid
        cc = zwapgrid.cached_consent() or {}
        if cc.get("id"):
            zg["consent_id"] = cc["id"]
            st = zwapgrid.consent_status(cc["id"])
            raw = st.get("status")
            # observed: 0 = created/pending; treat accepted/active strings or >=1 as connected
            s = str(raw).lower()
            zg["connected"] = s in ("1", "2", "accepted", "active", "granted")
            zg["pending"] = not zg["connected"]
    except Exception as e:
        zg["error"] = str(e)[:150]

    op: dict = {"connected": False, "pending": False}
    try:
        from . import openpayments
        cc = openpayments.cached_consent() or {}
        cid = cc.get("consentId")
        if cid:
            st = openpayments.consent_status(cid)
            s = str(st.get("consentStatus", "")).lower()
            op["connected"] = s == "valid"
            op["pending"] = s in ("received", "partiallyauthorised")
            op["status"] = s
    except Exception as e:
        op["error"] = str(e)[:150]
    return {"zwapgrid": zg, "openpayments": op}


@app.post("/api/connections/zwapgrid")
def connect_zwapgrid():
    try:
        from . import zwapgrid
        info = zwapgrid.create_consent()
        audit.log("create_consent", "provider=zwapgrid",
                  f"consent {str(info.get('id'))[:8]}… — onboarding URL issued (human approves)")
        return {"onboarding_url": info.get("onboarding_url"), "consent_id": info.get("id")}
    except Exception as e:
        audit.log("create_consent", "provider=zwapgrid", f"ERROR {str(e)[:120]}")
        return JSONResponse({"detail": str(e)[:200]}, status_code=502)


@app.post("/api/connections/openpayments")
def connect_openpayments():
    try:
        from . import openpayments
        data = openpayments.create_consent()
        cid = data.get("consentId")
        links = data.get("_links") or {}
        sca = (links.get("scaRedirect") or {}).get("href") or (links.get("scaOAuth") or {}).get("href")
        audit.log("create_consent", "provider=openpayments bank=SEB",
                  f"consent {str(cid)[:12]}… status={data.get('consentStatus')}")
        st = str(data.get("consentStatus", "")).lower()
        return {"consent_id": cid, "sca_url": sca, "connected": st == "valid",
                "status": st or "created"}
    except Exception as e:
        audit.log("create_consent", "provider=openpayments", f"ERROR {str(e)[:120]}")
        return JSONResponse({"detail": str(e)[:200]}, status_code=502)


# ---------- invoices: add + trust ----------

@app.post("/api/invoices")
def add_invoice(payload: dict):
    """Register a new supplier invoice from the UI; it goes through the SAME
    screening pipeline as everything else on the next briefing refresh."""
    import json as _json
    from .models import Invoice
    required = ("supplier_name", "amount", "due_date", "account_id")
    missing = [k for k in required if not str(payload.get(k, "")).strip()]
    if missing:
        return JSONResponse({"detail": f"missing: {', '.join(missing)}"}, status_code=422)
    rows = []
    if config.RUNTIME_INVOICES.exists():
        rows = _json.loads(config.RUNTIME_INVOICES.read_text())
    inv = Invoice(
        id=f"SI-UI-{uuid.uuid4().hex[:6].upper()}",
        supplier_name=str(payload["supplier_name"]).strip(),
        supplier_orgnr=(str(payload.get("supplier_orgnr", "")).strip() or None),
        amount=float(payload["amount"]),
        currency="SEK",
        issue_date=str(payload.get("issue_date") or config.DEMO_TODAY),
        due_date=str(payload["due_date"]),
        account_id=str(payload["account_id"]).strip(),
        institution=payload.get("institution"),
        reference=payload.get("reference"),
        source="seed",
    )
    rows.append(inv.to_dict() | {})
    # keep only model fields when re-loading
    keep = {"id", "supplier_name", "supplier_orgnr", "amount", "currency",
            "issue_date", "due_date", "account_id", "institution", "reference", "source"}
    rows = [{k: v for k, v in r.items() if k in keep} for r in rows]
    config.RUNTIME_INVOICES.write_text(_json.dumps(rows, indent=1, ensure_ascii=False))
    audit.log("register_invoice",
              f"{inv.supplier_name} {inv.amount:.0f} SEK -> {inv.account_id[-6:]}",
              f"{inv.id} registered — will be screened like any other invoice")
    _cache["briefing"] = None  # force re-screen
    return {"id": inv.id, "screened_on_next_load": True}


@app.post("/api/trust")
def trust_account(payload: dict):
    """Owner attests: I called the supplier, the new account is real."""
    import json as _json
    from .models import _norm_account
    orgnr = str(payload.get("orgnr", "")).strip()
    account = _norm_account(payload.get("account", ""))
    if not orgnr or not account:
        return JSONResponse({"detail": "orgnr and account required"}, status_code=422)
    rows = []
    if config.TRUSTED_ACCOUNTS.exists():
        rows = _json.loads(config.TRUSTED_ACCOUNTS.read_text())
    if not any(r["orgnr"] == orgnr and r["account"] == account for r in rows):
        rows.append({"orgnr": orgnr, "account": account,
                     "verified_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                     "verified_by": "owner"})
    config.TRUSTED_ACCOUNTS.write_text(_json.dumps(rows, indent=1))
    audit.log("trust_account", f"orgnr={orgnr} account=…{account[-6:]}",
              "owner attested after direct supplier contact — future invoices to this account clear")
    _cache["briefing"] = None
    return {"trusted": True}


@app.get("/api/suppliers")
def list_suppliers():
    """Known suppliers (for the add-invoice form autofill)."""
    b = get_briefing()
    seen = {}
    for group in (b["cleared"],):
        for c in group:
            i = c["invoice"]
            seen[i["supplier_orgnr"] or i["supplier_name"]] = {
                "name": i["supplier_name"], "orgnr": i["supplier_orgnr"]}
    for h in b["held"] + b["review"]:
        i = h["invoice"]
        seen.setdefault(i["supplier_orgnr"] or i["supplier_name"],
                        {"name": i["supplier_name"], "orgnr": i["supplier_orgnr"]})
    return {"suppliers": sorted(seen.values(), key=lambda s: s["name"])}


@app.post("/api/reset")
def reset():
    _cache["briefing"] = None
    _baskets.clear()
    audit.clear()
    for p in (config.RUNTIME_INVOICES, config.TRUSTED_ACCOUNTS):
        if p.exists():
            p.unlink()
    return {"ok": True}


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")


app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
