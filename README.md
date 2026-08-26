# Zentra — the finance employee who can't touch the money

**Embedded Finance Build Day 2026 · Stockholm · built on Zwapgrid API.1 + Open Payments**

Sweden has ~820,000 limited companies and most have no finance function — the owner
pays invoices tired, on Sunday night. Two things go wrong: **invoice fraud** (a known
supplier's invoice arrives with a swapped bank account — Swedish banks won't verify
payees until Verification of Payee arrives in **July 2027**) and **bad timing** (pay
everything Monday, miss the tax payment Thursday).

Zentra is an AI finance employee that reads the books, catches the fraud the bank
can't, finds the invoices you already paid once, plans payments around real cash — and
**prepares everything but signs nothing**. The human signs once, in their own bank.
Zentra holds no payment credentials, by design.

It does three things before money moves:

1. **Invoice fraud** — a known supplier's invoice naming an account never paid before
2. **Duplicate payments** — the same invoice paid twice; money already gone, recoverable
3. **Timing** — spacing payments so the cash buffer survives VAT and payroll

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
- **Duplicate rule:** the same join asked in reverse — was one invoice paid more than
  once? Grouped by (account, exact amount) inside a 14-day window, with salary accounts
  excluded by identity so monthly standing charges can never register as duplicates.
- **Planner:** day-by-day cash simulation; incoming invoices are shifted by each
  customer's *observed* lateness (due date vs. actual settlement); payments defer to
  inflow days rather than breach the buffer floor. Never past due date.
- **Invoice upload:** PDF (text layer), image (PNG/JPG/TIFF via tesseract OCR) or
  plain text. Extraction is a draft the human reviews — the screening is the authority,
  and re-registering an invoice already on the list is refused.
- **Agent:** orchestrates the pipeline and writes the morning briefing in plain
  language (local `claude` CLI; deterministic template fallback). Every tool call is
  appended to `audit.jsonl` — the "Know Your Agent" trail shown in the UI.

## Connections gate

With no bookkeeping or bank consent cached, Zentra shows nothing and says why — the
books say what should have happened, the bank says what did, and it needs both. It
never renders a seeded company to someone who has connected nothing.

## Honest data statement

The **pipelines are live** against both sandboxes (Zwapgrid dev / TEST.1, Open
Payments sandbox — SEB test bank). The **fraud scenario and payment-lateness history
are seeded** (`backend/seed/`), because no sandbox ships with a built-in criminal.
`DATA_MODE=seed|hybrid|live` switches the source; every record carries a `source` tag
and the UI badge says so.

## Demo instance

During Build Day this ran at `http://192.121.133.232` (Safespring VPS). **That
instance has been decommissioned** — run it locally with the steps below; the seeded
scenario is committed, so the fraud catch, the duplicate finding and the cash plan all
work offline with `DATA_MODE=seed` and no credentials at all.

## Run it

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env          # add your keys for live/hybrid mode
.venv/bin/python -m backend.seed.generate
DATA_MODE=seed .venv/bin/uvicorn backend.app:app --port 8010
# open http://localhost:8010   (8000 often collides with Docker Desktop)
```

Tests: `.venv/bin/python -m pytest` — **22 tests** (fraud rule, duplicate rule,
planner, data layer).

Optional: `sudo apt install tesseract-ocr tesseract-ocr-swe` to read invoice images.

Zwapgrid consent bootstrap (live mode): `python -m backend.zwapgrid --consent`,
open the printed onboarding URL, connect TEST.1, then `--status` / `--dump`.
Open Payments: `python -m backend.openpayments --banks | --consent | --dump`.

## Stack

Python 3.11 · FastAPI · httpx · vanilla HTML/CSS/JS (no build step) ·
`claude` CLI for narration · pytest.

*Built solo for Build Day. The scenario is seeded; the pipeline is real.*
