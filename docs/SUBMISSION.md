# Zentra

> **Note:** the live demo at `192.121.133.232` was decommissioned after Build Day.
> Run locally instead — see the README.

**http://192.121.133.232**

Zentra is the finance employee who can't touch the money.

There are around 820,000 limited companies in Sweden and most of them have no
finance function at all. The person deciding whether to pay a supplier is the same
person doing the selling and the delivering, usually working through invoices late
on a Sunday, from a financial picture their accountant will send them three weeks
after it stopped being useful.

Here is what happens to that person. An invoice arrives from a supplier they have
paid thirty times before. Same logo, same layout, same contact name, right amount,
right reference. One field has changed: the bank account number, with a short note
saying the company has switched banks. They pay it. They authenticate properly.
Every security control in the chain works exactly as designed, and the money is
gone. Sweden recorded 232,862 fraud offences last year.

Nobody catches this, and the reason is structural. Your bank sees the payment but
has no idea what the invoice claimed — it just sees a valid account number. Your
accounting system sees the invoice but has no proof of what actually left the
account. The evidence needed to catch the swap sits in the gap between the two, and
nothing joins them.

That gap is the whole product. Zwapgrid tells us what the books claim happened.
Open Payments tells us what the bank actually did. Zentra builds each supplier's
fingerprint of known-good accounts out of real outgoing payments, and holds any
invoice naming an account that has never appeared. Not a risk score — the evidence:
thirty-one payments to 839825, and this invoice says 944411.

The same comparison, asked the other way round, finds invoices that were paid twice.
Both payments authorised, both correctly booked, nobody notices, because nobody
reconciles a payment that succeeded. That is money already out the door and
recoverable, and it shows up the first day you connect.

Then it schedules whatever cleared so the cash buffer survives the month, without
ever pushing an invoice past its due date.

Two things we decided early and did not bend on. The rule is deterministic, not
machine learning, because a small company being told "we held your payment" deserves
a sentence explaining why, and a bank auditor deserves a rule they can read. And
Zentra prepares but never signs — the language model in this system has no path to a
payment API, not by policy but by architecture. It stages a batch. One signature in
your own bank completes it.

We should be straight about the limits. Verification of Payee already exists and
works; it checks that a name matches an account. What it cannot catch is a fraudster
who registers a company under the right name with a new account, and that is the
case payment history catches. It also isn't mandatory for Swedish banks until July
2027. And our own rule has a blind spot: a brand-new supplier clears automatically,
because there is no history to compare against. You cannot diff nothing.

Built on Open Payments and Zwapgrid for Embedded Finance Build Day, 25 August 2026.

---

## Solution (standalone — for a separate form field)

Zentra reads both sides of the same money and flags where they disagree.

Zwapgrid gives us the books: the invoice, the supplier, the account it asks to be
paid to. Open Payments gives us the bank: the real outgoing payments, what actually
left the account. On their own each is half a picture. Together they answer a
question neither can answer alone — has this company ever actually paid this
supplier at this account before?

From that join Zentra builds a fingerprint of known-good accounts for every
supplier, out of real bank payments rather than anything the invoice claims about
itself. When an invoice arrives naming an account that has never appeared in two
years of payments, it gets held before anything is staged, and the owner is shown
the evidence rather than a score: thirty-one payments to this account since January
2024, and this invoice asks for a different one. The same rule runs over payroll,
because changing an employee's salary account is the same attack wearing different
clothes.

Asked the other way round, the identical comparison finds invoices that were paid
twice — a reminder arrives for something already settled, someone pays it again,
and nobody notices because both payments were legitimate and correctly booked. That
is cash already gone and recoverable, and it surfaces the first day you connect.

Whatever clears then goes through a fourteen-day cash plan that spaces payments so
the buffer survives VAT and payroll, without ever pushing an invoice past its due
date, and says so plainly when the money simply is not going to be there.

The rule is deterministic, not machine learning. A company told "we held your
payment" deserves one sentence explaining why, and a bank auditor deserves a rule
they can read. The language model writes the morning briefing in plain English; it
never produces a verdict and cannot soften one.

And Zentra prepares but never signs. It has no path to a payment API — staging a
batch is the ceiling of its authority, one signature in your own bank completes it,
and every tool call it made is in an append-only log.

---

## Form answer — "Describe the B2B finance problem your team is solving and why it matters"

A finance assistant at a Swedish company receives an invoice from a supplier they
have paid thirty times before. Same logo, same layout, same contact name, correct
amount, correct reference. One field has changed: the bank account number, with a
short line explaining the company has switched banks.

She pays it. She authenticates properly. Every security control in the chain works
exactly as designed, and the money is gone.

Nobody catches this, and the reason is structural rather than careless. Her bank
sees a payment to a valid account number and has no idea what the invoice claimed.
Her accounting system sees the invoice and has no proof of what actually left the
account. The evidence needed to spot the swap — that this supplier has been paid
thirty times and never once to this account — exists only when you put the two
sides together, and nothing does. Verification of Payee helps, but it checks that a
name matches an account; it cannot catch a fraudster who registers a company under
the right name with a new account, and it is not mandatory for Swedish banks until
July 2027.

The same blind spot hides a quieter loss. When a supplier sends a reminder for an
invoice that was already paid and it gets paid a second time, both payments are
legitimate, authorised and correctly booked. Nobody reconciles a payment that
succeeded, and companies lose an estimated 0.1–0.5% of total spend this way.

It matters because of who it happens to. Sweden has around 820,000 limited
companies and the overwhelming majority have no finance function at all — the
person approving invoices is the same person doing the selling and the delivering,
usually working late from a financial picture their accountant will send three
weeks after it stopped being useful. Sweden recorded 232,862 fraud offences in
2025, and police estimate organised crime, laundering and fraud cost the country
100–150 billion kronor a year. These companies are the least equipped to absorb
that and the least likely to have anyone whose job it is to look.

---

## Form answer — "How does your technology solve the problem you described?"

Zentra reads both sides of the same money and acts on where they disagree.

Zwapgrid gives us the books: the supplier invoice and the account it asks to be paid
to. Open Payments gives us the bank: the real outgoing transactions, what actually
left the account. Separately each is half a picture. Together they answer the
question neither can answer alone — has this company ever actually paid this
supplier at this account before?

From that join Zentra builds a fingerprint of known-good accounts for every
supplier, assembled from real bank payments rather than anything an invoice claims
about itself. When an invoice arrives naming an account that has never appeared, it
is held before anything is staged, and the owner is shown the evidence rather than a
risk score: thirty-one payments to this account since January 2024, and this invoice
asks for a different one. The identical rule runs over payroll, because changing an
employee's salary account is the same attack wearing different clothes.

Asked in reverse, the same comparison finds invoices that were paid twice — the
quiet loss, where both payments were authorised and correctly booked and nobody
reconciled the one that succeeded. Getting that right is mostly about not crying
wolf: salary and rent are the same account for the same amount every month, so
payroll accounts are excluded by identity and the matching window is deliberately
shorter than a month. Every finding lists the bank reference ids so the owner can
open them in their own bank and check.

Whatever clears then goes through a fourteen-day cash plan that spaces payments so
the buffer survives VAT and payroll, never pushes an invoice past its due date, and
says so plainly when the money simply is not going to be there.

Two engineering decisions carry the whole thing. The rule is deterministic, not
machine learning — a company told "we held your payment" deserves one sentence
explaining why, and a bank auditor deserves a rule they can read. And Zentra
prepares but never signs: the language model writes the morning briefing in plain
English but has no path to a payment API, cannot produce a verdict and cannot soften
one. Staging a batch is the ceiling of its authority, one signature in the owner's
own bank completes it, and every tool call the agent makes lands in an append-only
log.

Built on real API calls, not mocks: a live SEB consent obtained through the full
Berlin Group decoupled BankID handshake, and a live Zwapgrid consent reading the
ledger. The fraud scenario itself is seeded, because no sandbox ships a two-year
payment history — and the product labels the source of every number on screen
rather than blurring the two.
