"""Open Payments (openpayments.io sandbox) client — Berlin Group PSD2.

Token: OAuth2 client_credentials, ~2 tokens/hour/PSU-context => DISK CACHE, always.
Every API call: fresh X-Request-ID GUID. Bank: SEB sandbox (fixed test PSU ids).
"""
from __future__ import annotations

import json
import time
import uuid
from urllib.parse import quote

import httpx

from . import config
from .models import Transaction


def _req_headers(token: str, extra: dict | None = None) -> dict:
    h = {
        "Authorization": f"Bearer {token}",
        "X-Request-ID": str(uuid.uuid4()),
        "Accept": "application/json",
    }
    h.update(extra or {})
    return h


def get_token(scope: str = "accountinformation aspspinformation corporate") -> str:
    """Cached token; refresh only when <5 min left. NEVER bypass the cache."""
    cache = {}
    if config.OP_TOKEN_CACHE.exists():
        try:
            cache = json.loads(config.OP_TOKEN_CACHE.read_text())
        except Exception:
            cache = {}
    entry = cache.get(scope)
    if entry and entry.get("expires_at", 0) - time.time() > 300:
        return entry["token"]
    r = httpx.post(
        f"{config.OP_AUTH_HOST}/connect/token",
        data={
            "client_id": config.OP_CLIENT_ID,
            "client_secret": config.OP_CLIENT_SECRET,
            "grant_type": "client_credentials",
            "scope": scope,
        },
        timeout=30.0,
    )
    r.raise_for_status()
    body = r.json()
    cache[scope] = {
        "token": body["access_token"],
        "expires_at": time.time() + body.get("expires_in", 3600),
        "scope": body.get("scope"),
    }
    config.OP_TOKEN_CACHE.write_text(json.dumps(cache))
    return cache[scope]["token"]


# ---------- ASPSP (bank discovery) ----------

def list_banks(country: str = "SE") -> list[dict]:
    tok = get_token()
    r = httpx.get(
        f"{config.OP_API_HOST}/psd2/aspspinformation/v1/aspsps",
        params={"isoCountryCodes": country},
        headers=_req_headers(tok),
        timeout=30.0,
    )
    r.raise_for_status()
    d = r.json()
    return d.get("aspsps", d if isinstance(d, list) else [])


# ---------- consent ----------

def _consent_headers(tok: str) -> dict:
    return _req_headers(tok, {
        "X-BicFi": config.OP_BANK_BIC,
        "PSU-ID": config.OP_PSU_ID,
        "PSU-Corporate-ID": config.OP_PSU_CORPORATE_ID,
        "PSU-IP-Address": "10.0.0.1",
        "PSU-User-Agent": "Zentra/1.0",
        "TPP-Redirect-Preferred": "true",
        "TPP-Redirect-URI": config.OP_REDIRECT_URI,
        "Content-Type": "application/json",
    })


def create_consent(valid_until: str = "2026-09-30") -> dict:
    tok = get_token()
    r = httpx.post(
        f"{config.OP_API_HOST}/psd2/consent/v1/consents",
        headers=_consent_headers(tok),
        json={
            "access": {},
            "recurringIndicator": True,
            "validUntil": valid_until,
            "frequencyPerDay": 4,
            "combinedServiceIndicator": False,
        },
        timeout=30.0,
    )
    r.raise_for_status()
    data = r.json()
    config.OP_CONSENT_CACHE.write_text(json.dumps(data, indent=1))
    return data


def consent_status(consent_id: str) -> dict:
    # Full consent headers, not a minimal set: the bank rejects a status read
    # that omits the PSU-Corporate-ID the consent was created with
    # ("The same Corporate-ID must be sent when referenced resource was
    # created with one") — which surfaced as a 400 on the Connections screen.
    tok = get_token()
    r = httpx.get(
        f"{config.OP_API_HOST}/psd2/consent/v1/consents/{consent_id}/status",
        headers=_consent_headers(tok),
        timeout=30.0,
    )
    r.raise_for_status()
    return r.json()


def cached_consent() -> dict | None:
    if config.OP_CONSENT_CACHE.exists():
        return json.loads(config.OP_CONSENT_CACHE.read_text())
    return None


# --- SCA: SEB answers the consent with `startAuthorisation` + `scaMethods`,
# not `scaRedirect`. That is the Berlin Group *decoupled* flow — the PSU
# approves in their BankID app while we poll. Three steps, then status.

def start_authorisation(consent_id: str) -> dict:
    """POST the consent's startAuthorisation link -> authorisationId + scaMethods."""
    tok = get_token()
    r = httpx.post(
        f"{config.OP_API_HOST}/psd2/consent/v1/consents/{consent_id}/authorisations",
        headers=_consent_headers(tok), json={}, timeout=30.0,
    )
    r.raise_for_status()
    return r.json()


def select_sca_method(consent_id: str, authorisation_id: str,
                      method_id: str = "mbid") -> dict:
    """Choose a BankID variant -> scaStatus 'started' + the message to show the PSU."""
    tok = get_token()
    r = httpx.put(
        f"{config.OP_API_HOST}/psd2/consent/v1/consents/{consent_id}"
        f"/authorisations/{authorisation_id}",
        headers=_consent_headers(tok), json={"authenticationMethodId": method_id},
        timeout=30.0,
    )
    r.raise_for_status()
    return r.json()


def sca_status(consent_id: str, authorisation_id: str) -> dict:
    """Poll one authorisation. 'finalised' means the PSU approved in their app."""
    tok = get_token()
    r = httpx.get(
        f"{config.OP_API_HOST}/psd2/consent/v1/consents/{consent_id}"
        f"/authorisations/{authorisation_id}",
        headers=_consent_headers(tok), timeout=30.0,
    )
    r.raise_for_status()
    return r.json()


def resolve_sca_oauth(href: str, consent_id: str) -> str:
    """The scaOAuth href ships with [CLIENT_ID]/[TPP_REDIRECT_URI]/[TPP_STATE]
    placeholders — fill them so the link is actually clickable."""
    return (href.replace("[CLIENT_ID]", config.OP_CLIENT_ID)
                .replace("[TPP_REDIRECT_URI]", quote(config.OP_REDIRECT_URI, safe=""))
                .replace("[TPP_STATE]", consent_id[:8]))


def _ais_headers(tok: str, consent_id: str) -> dict:
    return _req_headers(tok, {
        "X-BicFi": config.OP_BANK_BIC,
        "Consent-ID": consent_id,
        "PSU-ID": config.OP_PSU_ID,
        "PSU-Corporate-ID": config.OP_PSU_CORPORATE_ID,
    })


# ---------- account information ----------

def list_accounts(consent_id: str) -> list[dict]:
    tok = get_token()
    r = httpx.get(
        f"{config.OP_API_HOST}/psd2/accountinformation/v1/accounts",
        headers=_ais_headers(tok, consent_id),
        timeout=30.0,
    )
    r.raise_for_status()
    return r.json().get("accounts", [])


def get_balances(consent_id: str, resource_id: str) -> dict:
    tok = get_token()
    r = httpx.get(
        f"{config.OP_API_HOST}/psd2/accountinformation/v1/accounts/{resource_id}/balances",
        headers=_ais_headers(tok, consent_id),
        timeout=30.0,
    )
    r.raise_for_status()
    return r.json()


def get_transactions(consent_id: str, resource_id: str,
                     date_from: str = "2024-01-01") -> list[Transaction]:
    tok = get_token()
    r = httpx.get(
        f"{config.OP_API_HOST}/psd2/accountinformation/v1/accounts/{resource_id}/transactions",
        params={"bookingStatus": "booked", "dateFrom": date_from},
        headers=_ais_headers(tok, consent_id),
        timeout=30.0,
    )
    r.raise_for_status()
    body = r.json()
    booked = ((body.get("transactions") or {}).get("booked")) or []
    out = []
    for t in booked:
        amt = (t.get("transactionAmount") or {})
        cred_acc = (t.get("creditorAccount") or {})
        out.append(Transaction(
            id=t.get("transactionId") or str(uuid.uuid4()),
            booking_date=t.get("bookingDate") or "",
            amount=float(amt.get("amount") or 0.0),
            currency=amt.get("currency") or "SEK",
            creditor_name=t.get("creditorName"),
            creditor_account=cred_acc.get("iban") or cred_acc.get("bban") or "",
            source="live",
        ))
    return out


# ---------- payment initiation (staging only — Zentra never signs) ----------

def stage_payments(payments: list[dict]) -> dict:
    """Create payment initiations for the approved plan. Returns basket-like result.

    Exact signing-basket endpoint gets confirmed with OP engineers on event day;
    until then we create individual payment initiations (documented PIS flow) and
    collect their ids — honest fallback per plan Task 5.1.
    """
    tok = get_token("paymentinitiation corporate")
    results, errors = [], []
    for p in payments:
        try:
            r = httpx.post(
                f"{config.OP_API_HOST}/psd2/paymentinitiation/v1/payments/domestic",
                headers=_consent_headers(tok),
                json=p,
                timeout=30.0,
            )
            if r.status_code < 400:
                results.append(r.json())
            else:
                errors.append({"status": r.status_code, "body": r.text[:300]})
        except Exception as e:
            errors.append({"error": str(e)[:200]})
    return {"initiated": results, "errors": errors}


# ---------- cached wrappers for datalayer ----------

def _first_account(consent_id: str) -> dict | None:
    accounts = list_accounts(consent_id)
    return accounts[0] if accounts else None


def get_balance_cached() -> dict | None:
    cc = cached_consent()
    cid = (cc or {}).get("consentId")
    if not cid:
        return None
    acc = _first_account(cid)
    rid = (acc or {}).get("resourceId")
    if not rid:
        return None
    bal = get_balances(cid, rid)
    items = bal.get("balances") or []
    if not items:
        return None
    b0 = (items[0].get("balanceAmount") or {})
    return {"amount": b0.get("amount"), "currency": b0.get("currency"),
            "iban": (acc or {}).get("iban"), "name": (acc or {}).get("name")}


def get_transactions_cached() -> list[Transaction]:
    cc = cached_consent()
    cid = (cc or {}).get("consentId")
    if not cid:
        return []
    acc = _first_account(cid)
    rid = (acc or {}).get("resourceId")
    if not rid:
        return []
    return get_transactions(cid, rid)


if __name__ == "__main__":
    import sys
    if "--banks" in sys.argv:
        for b in list_banks():
            print(b.get("bicFi"), "-", b.get("name"))
    elif "--consent" in sys.argv:
        print(json.dumps(create_consent(), indent=1)[:2000])
    elif "--dump" in sys.argv:
        cc = cached_consent() or {}
        cid = cc.get("consentId")
        if not cid:
            print("no consent cached — run --consent")
        else:
            print("status:", json.dumps(consent_status(cid)))
            for a in list_accounts(cid):
                print("account:", a.get("iban"), a.get("name"))
    else:
        print("usage: python -m backend.openpayments --banks | --consent | --dump")
