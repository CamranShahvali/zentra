"""Zentra web app — FastAPI serving the API + static frontend."""
from __future__ import annotations

import json
import time
import uuid
from datetime import date

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import agent, audit, config, datalayer, extras

app = FastAPI(title="Zentra", version="0.1.0")


@app.middleware("http")
async def no_cache(request, call_next):
    """Dev servers + browser caches are how demos die. Never cache."""
    resp = await call_next(request)
    resp.headers["Cache-Control"] = "no-store, must-revalidate"
    return resp

ROOT = config.ROOT
FRONTEND = ROOT / "frontend"

_cache: dict = {"briefing": None, "at": 0.0}
_baskets: list[dict] = []


def _ledger_connected() -> bool:
    """Has the owner connected a bookkeeping system?

    Deliberately a file check, not a live API call: the gate must be instant and
    must not fail closed because a venue's wifi dropped.
    """
    return config.ZG_CONSENT_CACHE.exists()


def _bank_connected() -> bool:
    return config.OP_CONSENT_CACHE.exists()


def _unconnected_briefing() -> dict:
    """The honest empty state. Zentra has nothing to say until it can read
    something — showing a seeded company to someone who has connected nothing
    would be the same lie this product exists to catch."""
    zg, op = _ledger_connected(), _bank_connected()
    if not zg and not op:
        msg = ("Nothing is connected yet. Connect your bookkeeping to see what you owe, "
               "and your bank to prove what was actually paid. I need both: the books "
               "say what should have happened, the bank says what did.")
    elif not zg:
        msg = ("Your bank is connected, so I can see what left the account — but without "
               "your bookkeeping I have no invoices to check it against. Connect your "
               "bookkeeping and I'll start screening.")
    else:
        msg = ("Your bookkeeping is connected, so I can see what you owe — but without "
               "your bank I cannot prove which accounts you have actually paid before, "
               "and that history is the whole fraud check. Connect your bank.")
    return {
        "today": config.DEMO_TODAY,
        "briefing": msg,
        "briefing_author": "template",
        "needs_connection": {"ledger": not zg, "bank": not op},
        "balance": 0.0,
        "currency": "SEK",
        "sources": {},
        "totals": {"due_count": 0, "due_sum": 0, "held_sum": 0,
                   "today_sum": 0, "later_sum": 0},
        "validation": {"ok": True, "checks": []},
        "duplicates": {"count": 0, "total_recoverable": 0, "findings": []},
        # every key the frontend renderers touch must exist here, or a render
        # throws and the "connect me" screen never paints at all
        "payroll": {"employees": [], "held": [], "cleared": [],
                    "total_monthly": 0, "next_run": None},
        "notes": {}, "supplier_flags": {},
        "held": [], "review": [], "cleared": [],
        "obligations": [],
        "projection": {"buffer_floor": config.BUFFER_FLOOR_SEK, "inflows": [],
                       "shortfall": None,
                       "planned": {"series": [], "min_balance": 0},
                       "naive": {"series": [], "min_balance": 0}},
    }


@app.get("/api/briefing")
def get_briefing(refresh: bool = False, fast: bool = False):
    """fast=1 skips the LLM narration (template text) — used after UI actions so
    re-screening is instant; the Claude-written text returns on a normal load.

    The fast result deliberately does NOT refresh `at`: a template briefing must
    never satisfy the 600s cache window, or the first UI action of a session
    would silently downgrade every later load from the agent's own words to the
    template — the opposite of what this product claims about itself.
    """
    # No connection, no data. The ledger and the bank are what this product reads;
    # with neither attached there is nothing to screen and nothing to claim.
    if not (_ledger_connected() and _bank_connected()):
        return _unconnected_briefing()
    if fast:
        _cache["briefing"] = agent.morning_briefing(use_llm=False)
        _cache["at"] = 0.0
        return _cache["briefing"]
    if refresh or not _cache["briefing"] or time.time() - _cache["at"] > 600:
        _cache["briefing"] = agent.morning_briefing()
        _cache["at"] = time.time()
    return _cache["briefing"]


def _briefing_cached_or_fast() -> dict:
    """Reuse the cached briefing; if absent, build WITHOUT the LLM (fast).
    Action endpoints must never block a button on a 30s narration call.

    `at` stays 0 for the same reason as the fast path: this template text must
    not satisfy the cache window and rob the next page load of its narration.
    """
    if not _cache["briefing"]:
        _cache["briefing"] = agent.morning_briefing(use_llm=False)
        _cache["at"] = 0.0
    return _cache["briefing"]


@app.get("/api/evidence/{invoice_id}")
def get_evidence(invoice_id: str):
    b = _briefing_cached_or_fast()
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
    b = _briefing_cached_or_fast()
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


@app.get("/api/duplicates")
def get_duplicates():
    """Invoices paid more than once — money already out the door, recoverable."""
    b = _briefing_cached_or_fast()
    return b.get("duplicates") or {"count": 0, "total_recoverable": 0, "findings": []}


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
            # The only honest test of "connected" is whether the ledger actually
            # reads. `status` alone overstates it and `systemSettingsId` stays
            # null on TEST.1 even when data flows — so probe, and report what
            # came back rather than inferring from a flag.
            zg["status"] = st.get("status")
            zg["system"] = st.get("source") or None
            try:
                invs = zwapgrid.get_supplier_invoices(cc["id"])
                zg["connected"] = True
                zg["readable"] = {"supplier_invoices": len(invs)}
            except Exception as probe_err:
                zg["connected"] = False
                zg["pending"] = True
                zg["detail"] = (f"Consent {st.get('status')} but the ledger does not read yet "
                                f"({str(probe_err)[:60]}) — finish onboarding to pick a system.")
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
def connect_openpayments(payload: dict | None = None):
    """Create the consent and drive SEB's decoupled BankID handshake as far as
    a human can be asked to take over: consent -> authorisation -> method.

    SEB does not return `scaRedirect`; it returns `startAuthorisation` and a
    list of BankID methods. Stopping at the consent (as this route used to)
    leaves the UI with nothing to click, which reads as "the bank connection
    is broken" when in fact the handshake had simply not been started.
    """
    method = str((payload or {}).get("method") or "mbid")
    try:
        from . import openpayments
        data = openpayments.create_consent()
        cid = data.get("consentId")
        st = str(data.get("consentStatus", "")).lower()
        out: dict = {"consent_id": cid, "status": st or "created",
                     "connected": st == "valid", "sca_url": None,
                     "sca_status": None, "psu_message": None,
                     "methods": data.get("scaMethods") or []}
        audit.log("create_consent", "provider=openpayments bank=SEB",
                  f"consent {str(cid)[:12]}… status={st}")

        auth = openpayments.start_authorisation(cid)
        aid = auth.get("authorisationId")
        out["authorisation_id"] = aid
        out["methods"] = auth.get("scaMethods") or out["methods"]
        audit.log("start_authorisation", f"consent={str(cid)[:12]}…",
                  f"authorisation {str(aid)[:12]}… — {len(out['methods'])} BankID method(s) offered")

        chosen = openpayments.select_sca_method(cid, aid, method)
        out["sca_status"] = chosen.get("scaStatus")
        out["psu_message"] = chosen.get("psuMessage")
        href = ((chosen.get("_links") or {}).get("scaOAuth") or {}).get("href")
        if href:
            out["sca_url"] = openpayments.resolve_sca_oauth(href, str(cid))
        audit.log("select_sca_method", f"method={method}",
                  f"scaStatus={out['sca_status']} — PSU approves in their own BankID app")
        return out
    except Exception as e:
        audit.log("create_consent", "provider=openpayments", f"ERROR {str(e)[:120]}")
        return JSONResponse({"detail": str(e)[:200]}, status_code=502)


@app.get("/api/connections/openpayments/sca")
def openpayments_sca_status(consent_id: str, authorisation_id: str):
    """Poll one authorisation — 'finalised' means the PSU approved in their app."""
    try:
        from . import openpayments
        st = openpayments.sca_status(consent_id, authorisation_id)
        return {"sca_status": st.get("scaStatus"),
                "psu_message": st.get("psuMessage"),
                "finalised": str(st.get("scaStatus", "")).lower() == "finalised"}
    except Exception as e:
        return JSONResponse({"detail": str(e)[:200]}, status_code=502)


# ---------- invoices: add + trust ----------

@app.post("/api/invoices")
def add_invoice(payload: dict):
    """Register a new supplier invoice from the UI; it goes through the SAME
    screening pipeline as everything else on the next briefing refresh."""
    import json as _json
    from .models import Invoice, _norm_orgnr
    required = ("supplier_name", "amount", "due_date", "account_id")
    missing = [k for k in required
               if payload.get(k) is None or not str(payload.get(k, "")).strip()]
    if missing:
        return JSONResponse({"detail": f"missing: {', '.join(missing)}"}, status_code=422)

    # Validate before anything is written: a row with an unparseable date or a
    # non-numeric amount is persisted to disk and would then break every later
    # briefing — a 422 now, or a 500 on every screen until someone SSHes in.
    try:
        amount = float(payload["amount"])
    except (TypeError, ValueError):
        return JSONResponse({"detail": "amount must be a number"}, status_code=422)
    if amount <= 0:
        return JSONResponse({"detail": "amount must be greater than 0"}, status_code=422)
    for field in ("due_date", "issue_date"):
        raw = str(payload.get(field) or "").strip()
        if raw:
            try:
                date.fromisoformat(raw)
            except ValueError:
                return JSONResponse(
                    {"detail": f"{field} must be YYYY-MM-DD"}, status_code=422)
    rows = []
    if config.RUNTIME_INVOICES.exists():
        rows = _json.loads(config.RUNTIME_INVOICES.read_text())

    # Refuse the same invoice twice. A product that flags duplicate *payments*
    # should not itself accept duplicate *entry* — and re-uploading the same
    # file is exactly how a double payment starts.
    ref = str(payload.get("reference", "")).strip()
    orgnr_in = _norm_orgnr(str(payload.get("supplier_orgnr", "")))
    for r in rows:
        same_ref = ref and str(r.get("reference", "")).strip().lower() == ref.lower()
        same_party = _norm_orgnr(str(r.get("supplier_orgnr") or "")) == orgnr_in
        same_amount = abs(float(r.get("amount", 0)) - amount) < 0.005
        if same_amount and (same_ref or (same_party and orgnr_in)):
            return JSONResponse(
                {"detail": f"Already registered as {r['id']} — invoice "
                           f"{ref or 'with this amount'} from this supplier is "
                           f"on the list. Re-registering it is how a double "
                           f"payment starts.",
                 "existing_id": r["id"], "duplicate": True},
                status_code=409)
    inv = Invoice(
        id=f"SI-UI-{uuid.uuid4().hex[:6].upper()}",
        supplier_name=str(payload["supplier_name"]).strip(),
        supplier_orgnr=(str(payload.get("supplier_orgnr", "")).strip() or None),
        amount=amount,
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


@app.post("/api/invoices/{invoice_id}/orgnr")
def set_invoice_orgnr(invoice_id: str, payload: dict):
    """Owner supplies the organisation number a REVIEW invoice arrived without.

    This is not an override: once the supplier can be identified, the invoice
    is re-screened by the same rule as everything else, and may well come back
    HOLD. Filling the gap is the point; skipping the check is not.
    """
    import json as _json
    from .models import _norm_orgnr
    orgnr = str(payload.get("orgnr", "")).strip()
    if len(_norm_orgnr(orgnr)) < 10:
        return JSONResponse(
            {"detail": "A Swedish organisation number has 10 digits."}, status_code=422)
    fixes = {}
    if config.ORGNR_OVERRIDES.exists():
        try:
            fixes = _json.loads(config.ORGNR_OVERRIDES.read_text())
        except Exception:
            fixes = {}
    fixes[invoice_id] = orgnr
    config.ORGNR_OVERRIDES.write_text(_json.dumps(fixes, indent=1))
    audit.log("supply_orgnr", f"invoice={invoice_id} orgnr={orgnr}",
              "owner supplied the missing organisation number — invoice re-screened by the normal rule")
    _cache["briefing"] = None
    return {"ok": True, "invoice_id": invoice_id, "orgnr": orgnr}


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
    b = _briefing_cached_or_fast()
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


# ---------- notes / pause / payroll / report / upload / assistant ----------

@app.post("/api/invoices/{invoice_id}/notes")
def add_note(invoice_id: str, payload: dict):
    text = str(payload.get("text", "")).strip()
    if not text:
        return JSONResponse({"detail": "empty note"}, status_code=422)
    entry = datalayer.add_invoice_note(invoice_id, text)
    audit.log("add_note", invoice_id, text[:100])
    _cache["briefing"] = None
    return entry


@app.post("/api/suppliers/pause")
def pause_supplier(payload: dict):
    orgnr = str(payload.get("orgnr", "")).strip()
    if not orgnr:
        return JSONResponse({"detail": "orgnr required"}, status_code=422)
    paused = bool(payload.get("paused", True))
    reason = str(payload.get("reason", "")).strip()
    flag = datalayer.set_supplier_paused(orgnr, paused, reason)
    audit.log("pause_supplier" if paused else "resume_supplier",
              f"orgnr={orgnr}", reason or "no reason given")
    _cache["briefing"] = None
    return flag


@app.post("/api/payroll/trust")
def trust_salary_account(payload: dict):
    """Owner attests an employee's new salary account after direct contact."""
    import json as _json
    from .models import _norm_account, _norm_orgnr
    emp_id = str(payload.get("employee_id", "")).strip()
    account = _norm_account(payload.get("account", ""))
    if not emp_id or not account:
        return JSONResponse({"detail": "employee_id and account required"}, status_code=422)
    rows = []
    if config.TRUSTED_ACCOUNTS.exists():
        rows = _json.loads(config.TRUSTED_ACCOUNTS.read_text())
    key = _norm_orgnr(emp_id)
    if not any(_norm_orgnr(r["orgnr"]) == key and _norm_account(r["account"]) == account for r in rows):
        rows.append({"orgnr": emp_id, "account": account,
                     "verified_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                     "verified_by": "owner", "kind": "payroll"})
    config.TRUSTED_ACCOUNTS.write_text(_json.dumps(rows, indent=1))
    audit.log("trust_salary_account", f"employee={emp_id} account=…{account[-6:]}",
              "owner confirmed with employee directly — account trusted for payroll")
    _cache["briefing"] = None
    return {"trusted": True}


@app.get("/api/report/{year}/{month}")
def get_report(year: int, month: int, narrate: bool = False):
    b = _briefing_cached_or_fast()
    rep = extras.month_report(b, year, month)
    if narrate:
        rep["narrative"] = extras.month_report_text(rep)
    return rep


@app.post("/api/upload")
async def upload_invoice(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > 5_000_000:
        return JSONResponse({"detail": "file too large (max 5MB)"}, status_code=413)
    return extras.extract_invoice(data, file.filename or "upload.pdf")


@app.post("/api/assistant")
def assistant(payload: dict):
    q = str(payload.get("question", "")).strip()
    if not q:
        return JSONResponse({"detail": "question required"}, status_code=422)
    b = _briefing_cached_or_fast()
    return extras.assistant_reply(q, b)


@app.get("/api/validate")
def validate():
    w = datalayer.get_world()
    return datalayer.validate_world(w)


@app.post("/api/reset")
def reset(disconnect: bool = False):
    """Re-arm the demo scenario. Keeps the audit log (append-only) and records the reset.

    `disconnect=1` also drops the cached bank and bookkeeping consents, so the
    product returns to its true first-run state: nothing connected, nothing to
    show, until the owner connects them again.
    """
    _cache["briefing"] = None
    _baskets.clear()
    if disconnect:
        for p in (config.ZG_CONSENT_CACHE, config.OP_CONSENT_CACHE):
            if p.exists():
                p.unlink()
        audit.log("demo_reset", "connections cleared",
                  "bank + bookkeeping consents dropped; product back to first-run state")
    for p in (config.RUNTIME_INVOICES, config.TRUSTED_ACCOUNTS,
              config.ORGNR_OVERRIDES, config.SUPPLIER_FLAGS, config.INVOICE_NOTES):
        if p.exists():
            p.unlink()
    audit.log("demo_reset", "runtime invoices, trusted accounts, orgnr overrides, "
                            "supplier flags + notes cleared",
              "scenario re-armed; audit trail preserved")
    return {"ok": True}


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")


app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
