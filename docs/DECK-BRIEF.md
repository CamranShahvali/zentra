# Pitch deck brief — Zentra

> **Note:** the live demo at `192.121.133.232` was decommissioned after Build Day.
> Run locally instead — see the README.

**How to use this file:** paste the whole thing into an AI deck tool (Gamma, Tome,
Claude, Beautiful.ai) with the instruction below. Everything here is real — the
numbers, the quotes, the product behaviour. Do not let the tool invent statistics,
customer logos, testimonials, revenue figures or team bios. If a fact is not in this
file, it should not be on a slide.

> **Prompt to give the tool:**
> "Build a 12-slide pitch deck from the brief below. Follow the slide order and use
> the supplied copy close to verbatim. Keep each slide to one idea. Prefer large
> type and whitespace over dense bullets. Do not invent any statistic, logo, quote
> or claim that is not in the brief.
>
> Critical: this deck is handed to judges and will be read **without anyone
> narrating it**. Every slide must make its point on its own. Do not write slides
> that only work with a speaker — no bare headline slides, no 'see notes'. A judge
> flicking through it three hours later should still get the whole argument."

**This deck is a judge-facing deliverable, not a teleprompter.** It is read cold,
possibly after eight other demos, possibly by someone who missed the live pitch.
So each slide carries enough sentence-level content to be understood alone, while
staying short enough to project. Where a slide below has a "speaker note", treat
that as guidance for the live pitch only — the slide itself must already work
silently.

---

## Context

- **Event:** Embedded Finance Build Day, Stockholm, 25 August 2026
- **Format:** 5-minute pitch, live demo, jury Q&A after
- **Audience:** CTO of an SME lender (Froda), Open Banking partnerships at Danske
  Bank, CEO of Open Payments, CEO of Zwapgrid, payments engineering at Worldline,
  plus product/AI generalists
- **Two of the judges run the APIs this is built on.** The deck must never
  overstate what those APIs do or fail to do.
- **Live product:** http://192.121.133.232

## Tone

Plain, specific, unhurried. Concrete numbers instead of adjectives. No "revolutionary",
no "AI-powered", no rocket emojis. The product's whole argument is that it does not
overclaim, so the deck must not either. Where there is a limitation, say it on the
slide rather than hoping nobody asks.

## Visual direction

- Editorial, near-monochrome. Off-white or near-black background, one accent colour
  used sparingly for the held/alert state (a muted red or amber).
- One idea per slide. Many slides are a single sentence in large type.
- Real screenshots from the live product, not mockups or stock imagery.
- No stock photos of people shaking hands. No generic fintech illustration.
- Numbers are the hero: set statistics very large, source them in small type beneath.

---

# Slides

## 1 — Title

**Zentra**
The finance employee who can't touch the money.

*Small, beneath:* Built on Open Payments and Zwapgrid · Embedded Finance Build Day 2026

*Visual:* Just the wordmark on an empty field. No imagery.

---

## 2 — The story

> An invoice arrives from a supplier they have paid thirty times before.
> Same logo. Same layout. Same contact name. Correct amount. Correct reference.
>
> **One field has changed: the bank account number.**
>
> They pay it. They authenticate properly. Every security control in the chain
> works exactly as designed, and the money is gone.

*Visual:* A single invoice, with one field highlighted in the accent colour.
*Speaker note:* Say this before showing anything else. Do not rush it.

---

## 3 — The scale

**232,862**
reported fraud offences in Sweden, 2025 *(Brå)*

**100–150 bn SEK**
annual cost of organised crime, money laundering and fraud *(Police estimate)*

**~820,000**
Swedish limited companies — most with no finance function at all

*Visual:* Three numbers, very large, one per column. Sources in small grey type.

---

## 4 — Why nobody catches it

This is a structural gap, not a negligence problem:

**Your bank** sees the payment — but has no idea what the invoice claimed.
It sees a valid account number.

**Your accounting system** sees the invoice — but has no proof of what actually
left the account.

**The evidence needed to catch the swap sits between the two, and nothing joins them.**

*Visual:* Two boxes side by side with a gap between them. The gap is labelled and
is the visual focus of the slide.

---

## 5 — The insight

| Zwapgrid | Open Payments |
|---|---|
| what the books **claim** happened | what the bank **actually did** |
| the invoice and the account it asks to be paid to | the real outgoing payments |
| a claim printed on a document | proof, under PSD2 consent |

**The signal is the disagreement.**
A team building on one API has built half a product.

*Speaker note:* This is the single most important slide. Slow down here.

---

## 6 — How the rule works

For every supplier, Zentra builds a fingerprint of known-good accounts out of
**real outgoing bank payments** — not out of anything the invoice claims about itself.

An invoice naming an account that has never appeared is **held before anything is
staged**, and the owner sees the evidence rather than a score:

> **31 payments to account 839825 since January 2024.
> This invoice asks for 944411.**

The same rule runs over payroll — changing an employee's salary account is the same
attack wearing different clothes.

*Visual:* Screenshot of the evidence screen showing the row of payment blocks.

---

## 7 — Live product

*Visual:* Full-bleed screenshot of the Overview with the held invoice visible.

**It is live right now: http://192.121.133.232**

Deployed on a VPS, not a localhost demo. 22 tests passing.

**Both connections are real, and the Connections screen proves it:**
a valid SEB consent obtained through the full Berlin Group decoupled BankID
handshake, and a Zwapgrid consent that genuinely reads the ledger — the screen
shows the invoice count it just pulled back over the wire.

**The screening scenario is seeded, and we say so.** Zwapgrid's sandbox ERP
returns placeholder rows with no organisation numbers and no payment accounts,
dated 2023. You cannot demonstrate a *changed* payment account when there is no
account and no history to change from. So the demo runs a seeded Swedish company,
and the Overview carries a strip naming the source of every number rather than
letting a reader assume it is all live.

*Accuracy note for whoever builds this slide:* the honest claim is
**"the connections are live, the scenario is seeded"** — not "the data is live".
Do not write that live ledger rows appear in the invoice list. They do not.

---

## 8 — The same join, asked the other way

**12,400 SEK — paid twice.**

Fordonsleasing was paid on 8 July and again on 14 July. Both payments authorised.
Both correctly booked. Nobody noticed, because nobody reconciles a payment that
succeeded.

Industry loss to duplicate payments: **0.1–0.5% of total spend.**

**The fraud rule prevents a loss. This one hands money back.**

*Visual:* Screenshot of the "Paid twice" card.

---

## 9 — What we are not claiming

**Verification of Payee already exists.** Open Payments sells it, it works, it is in
production. It checks that a *name* matches an account.

**What it cannot catch:** a fraudster who registers a company under the *right* name
with a *new* account. Only payment history catches that.

VoP is not mandatory for Swedish banks until **July 2027**.

*Speaker note:* Say this before anyone in the room has to correct you. Two of the
judges sell these APIs — this slide is why they will trust the rest of the deck.

---

## 10 — Where we break

**A brand-new supplier clears automatically.**
There is no history to diff against. You cannot diff nothing.

That is why a supplier with no organisation number routes to REVIEW rather than
CLEAR — and REVIEW asks for the missing field instead of letting you click past
the check.

*Visual:* Plain text, no decoration. The starkness is the point.
*Speaker note:* Volunteering the false-negative surface is what makes everything
else credible to a credit-risk audience.

---

## 11 — The constraint we built around

**Zentra prepares. It never signs.**

The language model has no path to a payment API — not by policy, by architecture.
It receives decided facts and writes English. It cannot produce a verdict and cannot
soften one. Staging a batch is the ceiling of its authority.

Every tool call it makes lands in an append-only log.

**One signature in your own bank completes it.**

*Visual:* Screenshot of the agent log.

---

## 12 — Who this is for

**SMEs** — the cheapest finance hire they will ever make. It pays for itself the
first time it catches one invoice, and the duplicate finding returns cash on day one.

**Lenders** — payment behaviour is a live credit signal. A lender who can see
ledger-versus-bank disagreement underwrites better than one reading an annual report
from eight months ago.

**Accounting firms** — screening across a whole client book as a service line.

*Closing line, large:*
> Your books say what should have happened. Your bank says what did.
> **Zentra is the difference.**

---

# Facts the deck may use

Use these exactly. Do not round, embellish or add to them.

- 232,862 reported fraud offences in Sweden, 2025 (Brå)
- 100–150 bn SEK/year — organised crime, laundering and fraud (Police estimate)
- ~820,000 Swedish limited companies, majority with no finance function
- 10,731 Swedish bankruptcies in 2025, affecting 24,882 employees
- ~1 in 4 bankruptcies attributed to unpaid invoices
- ~1 in 2 EU commercial invoices paid late or not at all
- 0.1–0.5% of total spend lost to duplicate payments (industry estimate)
- Verification of Payee mandatory for Swedish banks: July 2027
- Demo scenario: 31 payments to one account since Jan 2024; invoice names a new one
- Demo amounts: 48,000 SEK held · 12,400 SEK recoverable · 14-day cash plan

# Things the deck must not do

- Invent customers, logos, testimonials, revenue, funding or team credentials
- Claim the fraud data is live. The **connections** are real and verifiable on the
  Connections screen; the **screening scenario is seeded**. Never blur those two.
- Claim live ledger rows appear among the invoices. They do not — the product runs
  on the seeded company, with the source of every number labelled on screen.
- Say "nobody checks this" — Verification of Payee checks part of it (see slide 9)
- Use the words revolutionary, disrupt, seamless, game-changing, or cutting-edge
- Add a competitor comparison grid — there is no researched competitor set here
- Show a hockey-stick projection — there are no financials to project
