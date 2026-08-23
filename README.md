# Zentra — the finance employee who can't touch the money

**Embedded Finance Build Day 2026 · Stockholm · built on Zwapgrid API.1 + Open Payments**

Sweden has ~820,000 limited companies and most have no finance function — the owner
pays invoices tired, on Sunday night. Two things go wrong: **invoice fraud** (a known
supplier's invoice arrives with a swapped bank account — Swedish banks won't verify
payees until Verification of Payee arrives in **July 2027**) and **bad timing** (pay
everything Monday, miss the tax payment Thursday).

Zentra is an AI finance employee that reads the books, catches the fraud the bank
can't, plans payments around real cash — and **prepares everything but signs nothing**.
The human signs once, in their own bank. Zentra holds no payment credentials, by design.

## How it works

```
Zwapgrid API.1  ──►  what the books CLAIM   ─┐
                     (supplier invoices,      ├─►  fraud rule (deterministic)
Open Payments   ──►  what the bank PROVES    ─┘    payment planner (cash simulation)
(Berlin Group)       (balance, transactions)              │
                                                          ▼
                                              LLM agent writes the briefing
                                              (it can narrate — never overrule a HOLD)
                                                          │
                                                          ▼
                                              one staged signing basket
                                              → human signs in their own bank
```

- **Fraud rule:** a supplier's known payment accounts are learned from its own invoice
  history and confirmed against actual outgoing bank transactions. A new account for a
  known supplier ⇒ HOLD. No ML — a rule a bank auditor can read.
- **Planner:** day-by-day cash simulation; incoming invoices are shifted by each
  customer's *observed* lateness (due date vs. actual settlement); payments defer to
  inflow days rather than breach the buffer floor. Never past due date.
- **Agent:** orchestrates the pipeline and writes the morning briefing in plain
  language (local `claude` CLI; deterministic template fallback). Every tool call is
  appended to `audit.jsonl` — the "Know Your Agent" trail shown in the UI.

## Honest data statement

The **pipelines are live** against both sandboxes (Zwapgrid dev / TEST.1, Open
Payments sandbox — SEB test bank). The **fraud scenario and payment-lateness history
are seeded** (`backend/seed/`), because no sandbox ships with a built-in criminal.
`DATA_MODE=seed|hybrid|live` switches the source; every record carries a `source` tag
and the UI badge says so.

## Run it

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env          # add your keys for live/hybrid mode
.venv/bin/python -m backend.seed.generate
DATA_MODE=seed .venv/bin/uvicorn backend.app:app --port 8000
# open http://localhost:8000
```

Tests: `.venv/bin/python -m pytest` (fraud rule, planner, data layer — 13 tests).

Zwapgrid consent bootstrap (live mode): `python -m backend.zwapgrid --consent`,
open the printed onboarding URL, connect TEST.1, then `--status` / `--dump`.
Open Payments: `python -m backend.openpayments --banks | --consent | --dump`.

## Stack

Python 3.11 · FastAPI · httpx · vanilla HTML/CSS/JS (no build step) ·
`claude` CLI for narration · pytest.

*Built solo for Build Day. The scenario is seeded; the pipeline is real.*
