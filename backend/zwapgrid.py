"""Zwapgrid API.1 client — consents + accounting pulls.

Endpoints verified live 2026-08-23:
  Consent API : https://apione.zwapgrid.com/consents/api/v1/consents  (+/{id}, /{id}/otc)
  Accounting  : https://apione.zwapgrid.com/accounting/consents/{consentId}/...
Headers on every call: x-api-key + fresh x-correlation-id GUID.
"""
from __future__ import annotations

import json
import uuid

import httpx

from . import config
from .models import Invoice, Receivable


def _headers() -> dict:
    return {
        "x-api-key": config.ZWAPGRID_API_KEY,
        "x-correlation-id": str(uuid.uuid4()),
        "Accept": "application/json",
    }


def _client() -> httpx.Client:
    return httpx.Client(timeout=30.0, headers=_headers())


# ---------- consent lifecycle ----------

def create_consent(name: str = "Zentra Build Day") -> dict:
    """Create a consent; returns {id, otc, onboarding_url} and caches it."""
    with _client() as c:
        r = c.post(f"{config.ZG_CONSENTS_BASE}/consents", json={"name": name})
        r.raise_for_status()
        data = r.json()
    consent_id = data.get("id") or data.get("consentId") or (data.get("data") or {}).get("id")
    otc = data.get("otc") or data.get("oneTimeCode") or (data.get("data") or {}).get("otc")
    if consent_id and not otc:
        otc = get_otc(consent_id)
    info = {
        "id": consent_id,
        "otc": otc,
        "onboarding_url": onboarding_url(consent_id, otc) if consent_id and otc else None,
        "raw": data,
    }
    config.ZG_CONSENT_CACHE.write_text(json.dumps(info, indent=1))
    return info


def get_otc(consent_id: str) -> str | None:
    with _client() as c:
        r = c.post(f"{config.ZG_CONSENTS_BASE}/consents/{consent_id}/otc")
        if r.status_code >= 400:  # some deployments use GET
            r = c.get(f"{config.ZG_CONSENTS_BASE}/consents/{consent_id}/otc")
        if r.status_code >= 400:
            return None
        data = r.json()
    return data.get("otc") or data.get("oneTimeCode") or data.get("code") or (
        data if isinstance(data, str) else None)


def onboarding_url(consent_id: str, otc: str) -> str:
    from urllib.parse import quote
    return f"{config.ZG_ONBOARDING_BASE}/consent/{consent_id}/?otc={quote(otc, safe='')}"


def consent_status(consent_id: str) -> dict:
    with _client() as c:
        r = c.get(f"{config.ZG_CONSENTS_BASE}/consents/{consent_id}")
        r.raise_for_status()
        return r.json()


def cached_consent() -> dict | None:
    if config.ZG_CONSENT_CACHE.exists():
        return json.loads(config.ZG_CONSENT_CACHE.read_text())
    return None


# ---------- accounting pulls ----------

def _paged(c: httpx.Client, url: str, params: dict | None = None) -> list[dict]:
    out, page = [], 1
    while True:
        p = dict(params or {})
        p["page"] = page
        r = c.get(url, params=p, headers=_headers())
        r.raise_for_status()
        body = r.json()
        data = body.get("data") or []
        out.extend(data)
        meta = body.get("meta") or {}
        total = meta.get("totalPages") or 1
        if page >= total or not data:
            return out
        page += 1


def _map_supplier_invoice(d: dict) -> Invoice:
    party = ((d.get("accountingSupplierParty") or {}).get("party")) or {}
    name = ((party.get("partyName") or {}).get("name")) or "(no name returned)"
    orgnr = None
    for ident in party.get("partyIdentification") or []:
        if str(ident.get("schemeId", "")).upper().endswith("ORGNR"):
            orgnr = ident.get("id")
            break
    if not orgnr:
        legal = (party.get("partyLegalEntity") or {}).get("companyId") or {}
        orgnr = legal.get("id")
    pm = (d.get("paymentMeans") or [{}])
    fa = (pm[0].get("financialAccount") or {}) if pm else {}
    total = d.get("totalBalanceAmount") or {}
    amount = total.get("amount")
    if amount is None:
        lm = d.get("legalMonetaryTotal") or {}
        pa = lm.get("payableAmount") or {}
        amount = pa.get("amount", 0.0)
    return Invoice(
        id=str(d.get("id")),
        supplier_name=name,
        supplier_orgnr=orgnr,
        amount=float(amount or 0.0),
        currency=total.get("currencyId") or "SEK",
        issue_date=d.get("issueDate") or "",
        due_date=d.get("dueDate") or "",
        account_id=fa.get("id") or "",
        institution=fa.get("financialInstitution"),
        reference=d.get("reference"),
        source="live",
    )


def get_supplier_invoices(consent_id: str) -> list[Invoice]:
    with _client() as c:
        rows = _paged(c, f"{config.ZG_ACCOUNTING_BASE}/consents/{consent_id}/supplierinvoices")
    return [_map_supplier_invoice(r) for r in rows]


def get_sales_invoices(consent_id: str) -> list[Receivable]:
    with _client() as c:
        rows = _paged(c, f"{config.ZG_ACCOUNTING_BASE}/consents/{consent_id}/salesinvoices")
    out = []
    for d in rows:
        party = ((d.get("accountingCustomerParty") or {}).get("party")) or {}
        name = ((party.get("partyName") or {}).get("name")) or "(customer)"
        total = d.get("totalBalanceAmount") or {}
        status = (d.get("paymentStatus") or {})
        paid = None
        if isinstance(status, dict) and str(status.get("status", "")).lower() in ("paid", "fullypaid"):
            paid = d.get("modifiedDateTime", "")[:10] or None
        out.append(Receivable(
            id=str(d.get("id")), customer_name=name,
            amount=float(total.get("amount") or 0.0),
            currency=total.get("currencyId") or "SEK",
            due_date=d.get("dueDate") or "", paid_date=paid, source="live",
        ))
    return out


def get_company_info(consent_id: str) -> dict:
    with _client() as c:
        r = c.get(f"{config.ZG_ACCOUNTING_BASE}/consents/{consent_id}/companyinformation",
                  headers=_headers())
        r.raise_for_status()
        return r.json()


# ---------- cached wrappers for datalayer ----------

def get_supplier_invoices_cached() -> list[Invoice]:
    cc = cached_consent()
    if not cc or not cc.get("id"):
        return []
    return get_supplier_invoices(cc["id"])


if __name__ == "__main__":
    import sys
    if "--consent" in sys.argv:
        info = create_consent()
        print(json.dumps({k: v for k, v in info.items() if k != "raw"}, indent=1))
        print("\nOpen the onboarding_url in a browser, connect TEST.1, then run --status")
    elif "--status" in sys.argv:
        cc = cached_consent()
        print(json.dumps(consent_status(cc["id"]), indent=1) if cc else "no cached consent")
    elif "--dump" in sys.argv:
        cc = cached_consent()
        if not cc:
            print("no cached consent — run --consent first")
        else:
            for inv in get_supplier_invoices(cc["id"])[:10]:
                print(inv.to_dict())
    else:
        print("usage: python -m backend.zwapgrid --consent | --status | --dump")
