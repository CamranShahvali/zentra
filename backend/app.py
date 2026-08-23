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


@app.post("/api/reset")
def reset():
    _cache["briefing"] = None
    _baskets.clear()
    audit.clear()
    return {"ok": True}


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")


app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
