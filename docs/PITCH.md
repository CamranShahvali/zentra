# Zentra — rehearsal script

> **Note:** the live demo at `192.121.133.232` was decommissioned after Build Day.
> Run locally instead — see the README.

Read this top to bottom while doing it. **DO** = an action. **SAY** = words out loud.
**PAUSE** = stop talking and let them look.

Target: **5:00**. Time yourself. The first run always overruns — that is normal.

---

# BEFORE YOU START

**DO —** run this in a terminal:
```bash
curl -X POST http://192.121.133.232/api/reset
```

**DO —** run this and read the output:
```bash
curl -s http://192.121.133.232/api/briefing?fast=1 | python3 -c "import json,sys;d=json.load(sys.stdin);print('held',len(d['held']),'payroll',len(d['payroll']['held']),'dup',d['duplicates']['count'])"
```
Must print **`held 1 payroll 1 dup 1`**. If not, run the reset again.

**DO —** open http://192.121.133.232 and press **Ctrl+Shift+R**.

**DO —** if the tour pops up, press **Esc**. You are presenting, not touring.

**DO —** confirm you can see a red box: **HELD · Städgrossisten AB · 48 000 SEK**.

**DO —** close every other tab. Full-screen the browser.

Now start the timer.

---

# 0:00 — OPEN. HANDS OFF THE KEYBOARD.

**DO —** step back from the laptop. Do not touch it. Look at the judges.

**SAY —**
> "A finance assistant at a Swedish company gets an invoice from a supplier they
> have paid thirty times before. Same logo. Same layout. Same contact name.
> Correct amount. Correct reference.
>
> One field has changed. The bank account number."

**PAUSE —** two seconds. Let that sit.

**SAY —**
> "She pays it. She authenticates properly. Every security control in the chain
> works exactly as designed, and the money is gone.
>
> Sweden recorded two hundred and thirty-two thousand fraud offences last year.
> This is the one nobody catches."

---

# 0:40 — THE BRIEFING

**DO —** turn to the screen. Point at the paragraph headed *"Zentra this morning"*.

**SAY —**
> "Six employees. No finance department. Every morning Zentra reads their
> bookkeeping and their bank, and writes them this."

**PAUSE —** four seconds. Let them actually read it. Do not talk over it.

**DO —** point at the small label beside the heading.

**SAY —**
> "That was written by the agent this morning. Not a template."

---

# 1:15 — THE EVIDENCE. THIS IS THE ONE THAT MATTERS.

**DO —** click **"Review evidence →"** in the red box.

**DO —** wait for the page. Point at the row of small blocks.

**SAY —**
> "Each one of these blocks is a real payment, pulled from their bank.
> Thirty-one of them. Every single one to account 839825."

**DO —** point at the account number on the invoice side.

**SAY —**
> "This invoice asks for 944411. An account that has never appeared. Not once."

**PAUSE —** two seconds.

**SAY — slowly. This is the whole pitch:**
> "Zwapgrid tells me what the books *claim*. Open Payments tells me what the bank
> *actually did*.
>
> Neither one can see this alone. The ledger has no proof. The bank has no idea
> what the invoice claimed.
>
> The signal **is** the disagreement. A team building on one API has built half a
> product."

---

# 2:15 — UPLOAD A REAL INVOICE

**DO —** click **Invoices** in the sidebar, then **"⇪ Upload invoice"**.

**DO —** choose `invoice-stadgrossisten-swapped-account.txt` from Downloads.

**SAY — while it reads:**
> "This is what actually lands in the inbox. A properly formatted Swedish invoice.
> It even says *OBS, vi har bytt bank* — we have changed banks, please update your
> details. That is the real line fraudsters use."

**DO —** when the fields appear, point at them.

**SAY —**
> "It read the invoice. But the extraction is only a draft — the screening is the
> authority. Register that and it is held anyway, because the account has no
> history."

**IF IT FAILS —** do not debug. Say this and move on:
> "The AI is a convenience. The rule is the product."

---

# 3:00 — PAYROLL

**DO —** click **Payroll** in the sidebar.

**SAY —**
> "Same rule, different attack surface. Someone changed an employee's salary
> account. One rule, two places money leaves the company."

---

# 3:25 — PAID TWICE

**DO —** click **Overview**. Scroll to the card titled **"Paid twice"**.

**SAY —**
> "And the same comparison, asked the other way round, finds this.
>
> Fordonsleasing was paid twelve thousand four hundred kronor on the eighth of
> July. And again on the fourteenth. Both payments authorised. Both correctly
> booked. Nobody noticed — because nobody reconciles a payment that succeeded.
>
> The first check prevents a loss. This one hands money back."

---

# 3:55 — THE HONEST PART. DO NOT SKIP THIS.

**DO —** look at the judges, not the screen.

**SAY —**
> "I want to be straight about two things.
>
> Open Payments already sells Verification of Payee. It works. It is in
> production. But it checks that a *name* matches an account. It cannot catch a
> fraudster who registers a company under the *right* name with a *new* account.
> Only payment history catches that. And it is not mandatory for Swedish banks
> until July 2027.
>
> And here is where *we* break. A brand-new supplier clears automatically. There
> is no history to compare against. You cannot diff nothing."

---

# 4:30 — CLOSE

**DO —** click **Agent log**.

**SAY —**
> "Every tool call the agent made is here. Append-only.
>
> And the part that matters: the language model in this system has no path to a
> payment API. Not by policy — architecturally. It receives decided facts and
> writes English. Staging a batch is the ceiling of its authority."

**DO —** stop clicking. Hands off.

**SAY —**
> "Nothing has moved. One signature in their own bank does that.
>
> Zentra is the finance employee who can't touch the money."

**DO —** stop talking. 5:00.

---

# IF YOU ARE RUNNING LONG

Cut in this order:
1. **2:15 upload** — the evidence screen already made the point
2. **3:00 payroll**
3. **4:30 agent-log click** — keep the words, skip the click

**Never cut:** the open, the evidence screen, or the honest part.

---

# DO NOT, DURING THE DEMO

- Do **not** click *"I verified — trust this account"* — it clears the fraud catch
- Do **not** click *"Pause payments to this supplier"*
- Do **not** click *Connect bookkeeping* or *Connect bank*
- Do **not** apologise for the seeded data — answer it if asked, never pre-empt it

---
---

# REFERENCE — read before, not during

## "Is this real data or fixtures?"

> "Both, and the screen says which. The bank consent is real and valid at SEB —
> obtained through the full Berlin Group BankID handshake. The ledger genuinely
> reads Zwapgrid; I can show you the invoice count it pulls back.
>
> The thirty-one-payment history is seeded, because no sandbox ships a two-year
> payment pattern. We label the source of every number rather than blurring it."

## "What about consent renewal / SCA churn?"

> "We don't solve it — but we degrade well. The rule runs on payment history, not
> a live feed. When the connection drops, screening still works on what we know."

## "Why not machine learning?"

> "A rule a bank auditor can read. I can tell you exactly why any invoice was
> held, in one sentence, with the evidence attached."

## "How do you avoid false positives on duplicates?"

> "Salary accounts are excluded by identity, and the matching window is fourteen
> days — deliberately shorter than a month, so rent and subscriptions can never
> chain into a finding. Every hit lists the bank reference ids so you can check
> them yourself. Eight tests cover exactly that."

## "Who is logged in? Where is the auth?"

> "There is none — it's a demo on a throwaway VPS with fictional data. In
> production this sits behind the customer's own login, and the architecture
> already assumes it: Zentra holds no payment credentials, cannot move money, and
> every action is in an append-only log."

## "What's the business model?"

> "SMEs directly — it pays for itself the first time it catches one invoice. And
> lenders as a channel: payment behaviour is a live credit signal. A lender who
> can see ledger-versus-bank disagreement underwrites better than one reading an
> annual report from eight months ago."

## "What would you build next?"

> "Consent renewal as a designed moment rather than an error state. And the
> double-financed invoice — two financiers looking at the same receivable."

## Numbers, if you need them

- 232,862 reported fraud offences in Sweden, 2025 (Brå)
- 100–150 bn SEK/year — organised crime, laundering, fraud (Police estimate)
- ~820,000 Swedish limited companies, most with no finance function
- 10,731 Swedish bankruptcies in 2025 · ~1 in 4 from unpaid invoices
- ~1 in 2 EU commercial invoices paid late
- 0.1–0.5% of total spend lost to duplicate payments
- Verification of Payee mandatory for Swedish banks: July 2027

## Commands

```bash
# ARM THE DEMO — before you present
curl -X POST http://192.121.133.232/api/reset

# CHECK — want: held 1 payroll 1 dup 1
curl -s http://192.121.133.232/api/briefing?fast=1 | python3 -c "import json,sys;d=json.load(sys.stdin);print('held',len(d['held']),'payroll',len(d['payroll']['held']),'dup',d['duplicates']['count'])"

# FULL FIRST-RUN — rehearsal only; you must reconnect in the UI afterwards
curl -X POST "http://192.121.133.232/api/reset?disconnect=1"

# IF THE SERVER MISBEHAVES
ssh -i ~/ips-sol-pentaguard-main/stc.pem ubuntu@192.121.133.232 "sudo systemctl restart zentra"
```
