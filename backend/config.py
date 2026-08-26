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
# Accounting paths are versioned: /accounting/api/v1/... Dropping the version
# segment returns 404 "Resource not found" on every endpoint, which is easy to
# misread as "the consent isn't connected" — it is not, the URL is just wrong.
ZG_ACCOUNTING_BASE = os.getenv("ZWAPGRID_ACCOUNTING_BASE",
                               "https://apione.zwapgrid.com/accounting/api/v1")
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
INVOICE_NOTES = ROOT / ".invoice_notes.json"         # notes per invoice id
SUPPLIER_FLAGS = ROOT / ".supplier_flags.json"       # paused suppliers keyed by orgnr_norm
ORGNR_OVERRIDES = ROOT / ".orgnr_overrides.json"     # owner-supplied orgnr, keyed by invoice id
UPLOAD_DIR = ROOT / ".uploads"                       # uploaded invoice files

# --- LLM ---
LLM_BACKEND = os.getenv("LLM_BACKEND", "claude-code")  # claude-code | none
LLM_MODEL = os.getenv("LLM_MODEL", "sonnet")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "60"))

# The CLI narrates; it must never be able to touch this host. `claude -p` ships
# with Bash/Read/Edit/Write enabled by default, and every prompt below carries
# text an outsider can reach (an uploaded invoice, an assistant question), so
# the tools are switched off explicitly rather than left to the default.
# dontAsk also guarantees no permission prompt can block a non-TTY subprocess.
LLM_NO_TOOLS = [
    "--permission-mode", "dontAsk",
    "--disallowedTools", "Bash,Read,Edit,Write,WebFetch,WebSearch,Agent",
]


def llm_argv(exe: str) -> list[str]:
    """Argv for a single locked-down narration turn."""
    return [exe, "-p", "--model", LLM_MODEL, "--max-turns", "1", *LLM_NO_TOOLS]

# --- Business rules ---
BUFFER_FLOOR_SEK = int(os.getenv("BUFFER_FLOOR_SEK", "10000"))
PLANNING_HORIZON_DAYS = 14
# Demo clock: seed data is written against this "today" so the story is stable.
DEMO_TODAY = os.getenv("DEMO_TODAY", "2026-08-25")
