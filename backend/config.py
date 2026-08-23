"""Zentra configuration — env loading and constants."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# --- Zwapgrid ---
ZWAPGRID_API_KEY = os.getenv("ZWAPGRID_API_KEY", "")
ZG_CONSENTS_BASE = "https://apione.zwapgrid.com/consents/api/v1"
ZG_ACCOUNTING_BASE = os.getenv("ZWAPGRID_ACCOUNTING_BASE", "https://apione.zwapgrid.com/accounting")
ZG_ONBOARDING_BASE = "https://onboarding.zwapgrid.com"
ZG_CONSENT_CACHE = ROOT / ".zg_consent.json"

# --- Open Payments (openpayments.io sandbox) ---
OP_CLIENT_ID = os.getenv("OP_CLIENT_ID", "")
OP_CLIENT_SECRET = os.getenv("OP_CLIENT_SECRET", "")
OP_AUTH_HOST = os.getenv("OP_AUTH_HOST", "https://auth.sandbox.openbankingplatform.com")
OP_API_HOST = os.getenv("OP_API_HOST", "https://api.sandbox.openbankingplatform.com")
OP_REDIRECT_URI = os.getenv("OP_REDIRECT_URI", "https://localhost:8080/")
OP_TOKEN_CACHE = ROOT / ".token_cache.json"
OP_CONSENT_CACHE = ROOT / ".op_consent.json"

# Sandbox bank of choice (SEB has fixed test PSU ids)
OP_BANK_BIC = os.getenv("OP_BANK_BIC", "ESSESESS")
OP_PSU_ID = os.getenv("OP_PSU_ID", "199311219639")
OP_PSU_CORPORATE_ID = os.getenv("OP_PSU_CORPORATE_ID", "4007314497")

# --- Data / demo ---
DATA_MODE = os.getenv("DATA_MODE", "hybrid")  # live | seed | hybrid
SEED_DIR = ROOT / "backend" / "seed"
AUDIT_LOG = ROOT / "audit.jsonl"
RUNTIME_INVOICES = ROOT / ".runtime_invoices.json"   # invoices added via the UI
TRUSTED_ACCOUNTS = ROOT / ".trusted_accounts.json"   # owner-verified (orgnr, account) pairs

# --- LLM ---
LLM_BACKEND = os.getenv("LLM_BACKEND", "claude-code")  # claude-code | none

# --- Business rules ---
BUFFER_FLOOR_SEK = int(os.getenv("BUFFER_FLOOR_SEK", "10000"))
PLANNING_HORIZON_DAYS = 14
# Demo clock: seed data is written against this "today" so the story is stable.
DEMO_TODAY = os.getenv("DEMO_TODAY", "2026-08-25")
