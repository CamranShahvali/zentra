# Both platforms at full capability — what exists, what it does, when to use it

Verified against live docs + sandbox probes, 23 Aug 2026.
(✅ = works in our sandbox now · 🔒 = production access only · 🧪 = beta/limited)

---

## OPEN PAYMENTS (openpayments.io) — the bank side

OAuth2 client_credentials; scope = API scope + `private`/`corporate` context.
Headers everywhere: `X-Request-ID` (fresh GUID), mostly `X-BicFi`, `PSU-ID`, `PSU-Corporate-ID`.
`X-Feature-Flags: new-statuses` opts into harmonised payment statuses (default from 30 Sep 2026).

### Core APIs

| API | What it does | Why you'd use it | Zentra |
|---|---|---|---|
| **ASPSP Information** ✅ (`aspspinformation`) | Lists supported banks (`GET /psd2/aspspinformation/v1/aspsps?isoCountryCodes=SE`) + per-bank details: payment products, auth methods, **`transactionHistoryMaxDays` / extended history**, **`signingBasketsSupported` + limit** | Build bank-picker UIs; adapt to each bank's capabilities instead of hardcoding | Bank list on Connections page; check basket support before staging |
| **Consents** ✅ | `POST /psd2/consent/v1/consents` — PSU grants read access; `access:{}` = all accounts; `validUntil`, `frequencyPerDay`; then authorise via SCA | Legally required gateway to any account data | "Connect bank" button |
| **Account Information (AIS)** ✅ (`accountinformation`) | Accounts, balances, transactions (`bookingStatus`, `dateFrom`). NOTE: default history ≈ 88 days at e.g. Swedbank; **extended history (up to ~760 days) only within ~60 min of SCA** | Dashboards, reconciliation, cash analysis | Balance + outgoing payment history (the fraud rule's ground truth) |
| **Payment Initiation (PIS)** ✅ (`paymentinitiation`) | `POST /psd2/paymentinitiation/v1/payments/{product}`: `domestic`, `swedish-giro` (bankgiro/plusgiro + OCR), `sepa-credit-transfers`, `international`/`cross-border`, future-dated via `requestedExecutionDate`. **Built-in fraud screen: creditor accounts on Svensk Handel's watchlist return a warning** | Move money without building per-bank integrations | Stage the approved batch |
| **Authorisations & Signing Baskets** ✅ | `POST /psd2/paymentinitiation/v1/signing-baskets` bundles many paymentIds → ONE SCA signature (limit ~100/bank). Auth flows: **Redirect** (bank page) or **Decoupled** (BankID push in your UI — `scaMethods` include Mobilt BankID variants) | Pay 9 invoices with one BankID signature; embed signing UX in-app | The sign-once story; decoupled BankID = slick live demo in prod |
| **KYC** ✅ endpoint (`POST /kyc/integration/v1/new/{orgnr}?countryCode=SE`) | Hosted webform (24h URL) verifying an organisation before payments | Compliance onboarding without building ID verification | Would gate real onboarding; mention, don't demo |

### Alternative / Premium APIs

| API | What it does | Why you'd use it | Status for us |
|---|---|---|---|
| **ISO Payments** | JSON in → **ISO 20022 pain.001 file** generated & uploaded to online bank for authorisation | ERP/treasury-grade batch payments; corporate rails | Alternative to PIS; mention as scale path |
| **FX Connect** | `POST /psd2/paymentinitiation/v1/fx` → quote (rate, fee, validity; spot or forward ≤30 days, 180+ countries) — works even on top of your own bank integrations | Cross-border supplier invoices at transparent institutional rates | Out of scope for demo |
| **Bankgiro Lookup** 🔒 | `POST /psd2/premium/v1/creditor-name?giroNumber=…` → registered creditor name **+ OCR reference validation**; `giro-numbers` lists an org's registered bankgiro accounts | Pre-payment recipient verification for Swedish giro payments | 404 in sandbox (prod-only) — cite as production layer |
| **Verification of Payee (VoP)** 🔒 | `POST /premium/v1/payee-verifications` (+ `/bulk-`): does NAME match IBAN? → `MTCH`/`CMTC`+matchedName/`NMTC`/`NOAP` | The EU-mandated pre-payment name check (mandatory for banks July 2027) — Open Payments already sells it | **404 in sandbox (prod-only). CHANGES OUR PITCH — see below** |
| **Payout Service** 🔒 | `POST /premium/v1/payouts` — disbursements from Open Payments' **client funds account** via Bankgirot/Plusgirot; includes creditor-name lookup | Payroll/supplier/refund payouts without per-PSU bank SCA, no transaction limits | Prod-only; mention as scale path |
| **SEPA Direct Debit** 🧪 | pain.008 collections under mandate (NL, EUR, beta; consent with `X-Consent-Type: sepaDirectDebit`) | Recurring collections | Not available in SBX; skip |

### Sandbox facts that bite
- **~2 tokens/hour per PSU context** → disk-cache tokens (done).
- SEB sandbox payment products: `domestic`, `swedish-giro`, `sepa-credit-transfers`, `international`. ASPSP details in sandbox omit basket/history metadata (empty objects).
- Some banks need specific sandbox PSU credentials (SEB/Danske fixed IDs; others accept any real-format).

---

## ZWAPGRID (API.1) — the accounting side

`x-api-key` + fresh `x-correlation-id` GUID on every call. Consent-scoped paths.
Consent API: `https://apione.zwapgrid.com/consents/api/v1/consents` (+`/{id}`, `/{id}/otc` — POST, key `code`).
Onboarding: `https://onboarding.zwapgrid.com/consent/{id}/?otc=<url-encoded>` (single-use, 1h).
Accounting API: `https://apione.zwapgrid.com/accounting/consents/{consentId}/…`, paginated `meta`+`data`.

| Capability | What it does | Why you'd use it | Zentra |
|---|---|---|---|
| **Consent API** ✅ | Create consent (201, empty body — fetch id via list), OTC, status, lifecycle | The customer-permission handshake for books access | "Connect bookkeeping" button |
| **Supplier invoices** ✅ | Purchase invoices incl. `paymentMeans[].financialAccount` (the payee account!), party orgnr, due dates, `bookedInvoiceIndicator`, `cancelledInvoiceIndicator`, payments sub-endpoints | AP automation, spend analysis | The fraud rule's input |
| **Sales invoices (+payments)** ✅ | Receivables + **when they were actually settled** (Fortnox, Spiris, e-conomic, Billy, Xero) | AR, credit scoring, factoring data | Customer lateness model |
| **Customers / Suppliers** ✅ | Master records with legal identifiers (note: supplier `payeeFinancialAccounts` being REMOVED — use invoice-level accounts) | Counterparty enrichment | Orgnr matching |
| **Company information** ✅ | The connected company's own legal data | Onboarding prefill, KYC context | Sidebar identity |
| **Income statement / Balance sheet / Trial balances (V2)** ✅ | Formal statements + all ledger balances per period | Lending decisions, financial health scoring, covenant monitoring | Could power "can I afford this hire?" — stretch |
| **Journals (+attachments)** ✅ (Fortnox, BL, Procountor) | The book of original entry — every debit/credit | Audit trails, anomaly detection on bookkeeping itself | Out of scope |
| **File.1** ✅ | Upload PDFs (invoices) at fileone.zwapgrid.com with consent+OTC → extracted data | Capture invoices when the system has NO API — or paper | Mention: how a photographed invoice would enter Zentra |
| **Proxy.1** ✅ | Call the underlying system's OWN API through Zwapgrid auth: swap base URL for `…/consents/{id}/proxy` (Fortnox, Business Central, e-conomic, Xero, QuickBooks…) | Anything the unified schema doesn't cover, without building your own OAuth per system | Escape hatch if TEST.1 lacks a field |
| **Use-case docs** | Invoicing / Bookkeeping / Financial reporting primers | Domain vocabulary for the pitch | Read once |

**System-support caveat:** endpoint coverage varies per accounting system (e.g. journals: Fortnox ✅, Xero ✅, most others 📞; supplier invoices: broad but not universal). Check the per-endpoint support table before promising a data source.

---

## ⚠️ THE PITCH CORRECTION (important — a judge WILL know this)

Open Payments **already offers VoP in production**. So never say "nobody can check this."
The accurate — and stronger — line:

> "From July 2027 every Swedish bank must run Verification of Payee — the name-vs-account
> check Open Payments already sells today. But VoP answers *'does this name match this
> account?'* A fraudster who registers **Städgrossisten Sverige AB** and opens an account
> passes that check. Zentra answers a question VoP can't: *'is this the account this
> supplier has actually been paid to, 31 times, according to the bank?'* That history
> lives in the ERP + bank statement join — exactly the two platforms in this room.
> In production, Zentra would call VoP as one more layer: name check (theirs), watchlist
> check (built into their PIS), history check (ours). Three locks instead of zero."

Bonus discovery for the demo: **payment initiation already screens creditor accounts
against Svensk Handel's fraud watchlist** — so staging through Open Payments adds a real
second fraud layer, free. Say it when staging the basket.
