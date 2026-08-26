/* Zentra admin board — vanilla JS, no build step. */

const $ = (id) => document.getElementById(id);
const sek = (n) =>
  new Intl.NumberFormat("sv-SE", { maximumFractionDigits: 0 }).format(Math.round(n)) + " SEK";
const shortAcct = (a) => (a && a.length > 12 ? a.slice(0, 4) + " …" + a.slice(-6) : a || "—");
const fmtDate = (iso) => {
  if (!iso) return "—";
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
};

let DATA = null;

/* ---------- navigation ---------- */
function show(page) {
  document.querySelectorAll(".page").forEach((p) => p.classList.remove("active"));
  $("page-" + page).classList.add("active");
  document.querySelectorAll(".nav-item").forEach((n) =>
    n.classList.toggle("active", n.dataset.page === page)
  );
  window.scrollTo({ top: 0, behavior: "instant" });
  if (page === "log") refreshAudit();
  if (page === "connections") refreshConnections();
}
document.querySelectorAll(".nav-item").forEach((n) =>
  n.addEventListener("click", () => show(n.dataset.page))
);

/* ---------- load ---------- */
async function load(fast = false) {
  // A failed load used to leave DATA as an error object and every render threw,
  // so the whole product read as dead. Say what happened instead.
  try {
    const r = await fetch("/api/briefing" + (fast ? "?fast=1" : ""));
    if (!r.ok) throw new Error("briefing " + r.status);
    const next = await r.json();
    if (!next || !next.totals) throw new Error("malformed briefing");
    DATA = next;
  } catch (e) {
    const b = $("ov-briefing");
    if (b) {
      b.textContent =
        "Zentra could not load this morning's screening (" + e.message +
        "). The data is intact — reload, or reset the demo scenario.";
    }
    const a = $("ov-author");
    if (a) a.textContent = "not loaded";
    return;
  }
  renderOverview();
  renderInvoices();
  renderPayroll();
  renderPayments();
  renderCustomers();
  renderConnectionGate();
}

/* Show the data now, narrate a moment later.
   The full briefing waits on the LLM (~8s). Blocking a connection flow on that
   made the Connections page look stuck and the numbers look slow to arrive, so
   paint the deterministic result first and let the narration swap itself in. */
async function loadNow() {
  await load(true);            // instant: screening + plan, template text
  load();                      // background: same data, written by the agent
}

/* Nothing connected = nothing to show. Make that state deliberate and legible
   rather than letting the screens render a convincing pile of zeroes. */
function renderConnectionGate() {
  const need = DATA.needs_connection;
  const gate = $("gate-card");
  if (!gate) return;
  if (!need || (!need.ledger && !need.bank)) {
    gate.hidden = true;
    return;
  }
  const missing = [];
  if (need.ledger) missing.push("bookkeeping");
  if (need.bank) missing.push("bank");
  $("gate-title").textContent =
    "Connect your " + missing.join(" and ") + " to begin";
  $("gate-sub").textContent = DATA.briefing || "";
  $("gate-btn").onclick = () => show("connections");
  gate.hidden = false;
}

/* ---------- overview ---------- */
function renderOverview() {
  const d = new Date(DATA.today + "T08:00:00");
  $("ov-date").textContent = d.toLocaleDateString("en-GB", {
    weekday: "long", day: "numeric", month: "long", year: "numeric",
  });
  $("ov-balance").textContent = sek(DATA.balance);
  $("ov-account").textContent = "Företagskonto · SEB";
  $("ov-due").textContent = sek(DATA.totals.due_sum);
  $("ov-due-sub").textContent = DATA.totals.due_count + " supplier invoices";
  $("ov-low").textContent = sek(DATA.projection.planned.min_balance);
  const sf = DATA.projection.shortfall;
  const lowStat = $("ov-low");
  if (sf) {
    lowStat.classList.add("danger");
    $("ov-low-sub").textContent = sf.below_zero
      ? "planned outflows exceed cash — shortfall shown, not hidden"
      : "dips under your buffer even with optimal timing";
  } else {
    lowStat.classList.remove("danger");
    $("ov-low-sub").textContent = "with Zentra's plan";
  }

  $("ov-briefing").textContent = DATA.briefing;
  $("ov-author").textContent =
    DATA.briefing_author === "claude" ? "written by the agent" : "generated";

  // Lead with an account-swap hold if there is one: a paused supplier carries no
  // payment history, so letting it take the alert card would push the fraud
  // story off the screen and render "paid undefined×".
  const fraudHolds = DATA.held.filter(
    (h) => ((h.evidence || {}).known_accounts || []).length
  );
  const lead = fraudHolds[0] || DATA.held[0];

  if (lead) {
    const ev = lead.evidence || {};
    const known = (ev.known_accounts || [{}])[0];
    $("ov-held").textContent = sek(DATA.totals.held_sum);
    $("ov-held-stat").classList.add("alert");
    $("nav-alerts").hidden = false;
    $("nav-alerts").textContent = DATA.held.length;
    $("ov-alert").hidden = false;
    $("ov-alert-title").textContent = lead.invoice.supplier_name;
    $("ov-alert-sub").textContent = ev.paused
      ? "payments to this supplier are paused by you — nothing will be staged"
      : known.times_paid
      ? `paid ${known.times_paid}× to one account since ${String(known.first_seen || "").slice(0, 7)} — this invoice names a new one`
      : "held for review before anything moves";
    $("ov-alert-amount").textContent = sek(lead.invoice.amount);
    $("ov-alert-open").onclick = () => openDetail(lead.invoice.id);
  } else {
    // Nothing held any more (e.g. the owner just verified the account) — clear
    // the alert surfaces too, or the screen contradicts the verdict it shows.
    $("ov-held").textContent = "0 SEK";
    $("ov-held-stat").classList.remove("alert");
    $("ov-alert").hidden = true;
    $("nav-alerts").hidden = true;
  }

  renderChart();
  renderUpcoming();
  renderProvenance();
  renderDuplicates();
}

/* Money already out the door. The fraud rule asks whether an account was ever
   paid; this asks whether an invoice was paid twice — same join, opposite
   question, and the only one of the two that hands cash back. */
function renderDuplicates() {
  const card = $("ov-dup");
  if (!card) return;
  const d = DATA.duplicates;
  if (!d || !d.count) { card.hidden = true; return; }

  $("dup-total").textContent = sek(d.total_recoverable) + " recoverable";
  $("dup-lead").textContent =
    d.count === 1
      ? "One invoice was paid more than once."
      : `${d.count} invoices were paid more than once.`;

  const ul = $("dup-list");
  ul.innerHTML = "";
  d.findings.forEach((f) => {
    const li = document.createElement("li");
    li.innerHTML =
      `<b>${f.supplier_name}</b> — ${sek(f.amount)} paid ${f.times_paid}× ` +
      `(${fmtDate(f.first_paid)} and ${fmtDate(f.last_paid)}, ${f.days_apart} days apart)` +
      `<div class="dup-ids">bank references: ${(f.transaction_ids || []).join(", ")}</div>`;
    ul.appendChild(li);
  });
  card.hidden = false;
}

/* Say where every number came from. A blank presented as a fact is the failure
   mode this product exists to argue against, so the ledger must never look
   connected when it is a seeded company. */
async function renderProvenance() {
  const strip = $("prov-strip");
  if (!strip) return;
  const src = DATA.sources || {};
  const ledgerLive = String(src.invoices || "").includes("live");
  const bankLive = String(src.transactions || "").includes("live");

  let conn = null;
  try {
    const r = await fetch("/api/connections");
    if (r.ok) conn = await r.json();
  } catch (e) { /* offline: fall back to the source tags alone */ }

  const zgOn = conn && conn.zwapgrid && conn.zwapgrid.connected;
  const opOn = conn && conn.openpayments && conn.openpayments.connected;

  const zgPending = conn && conn.zwapgrid && conn.zwapgrid.pending;
  $("prov-ledger").textContent = ledgerLive
    ? "Ledger: live from " + ((conn.zwapgrid && conn.zwapgrid.system) || "your bookkeeping")
    : zgOn
    ? "Ledger: bookkeeping bound — seeded demo company still shown"
    : zgPending
    ? "Ledger: seeded demo company · consent approved, no accounting system bound yet"
    : "Ledger: seeded demo company (Annas Städ AB)";
  $("prov-ledger").className = "prov-item " + (ledgerLive ? "live" : "seed");

  $("prov-bank").textContent = bankLive
    ? "Bank: live transactions"
    : opOn
    ? "Bank: SEB sandbox · consent valid"
    : "Bank: not connected";
  $("prov-bank").className = "prov-item " + (bankLive || opOn ? "live" : "seed");

  $("prov-connect").hidden = !!(ledgerLive || zgOn);
  $("prov-connect").onclick = () => show("connections");
  strip.hidden = false;
}

function renderChart() {
  const el = $("cash-chart");
  el.innerHTML = "";
  const planned = DATA.projection.planned.series;
  const naive = DATA.projection.naive.series;
  const floor = DATA.projection.buffer_floor;
  const maxv = Math.max(...planned.map((p) => p.balance), ...naive.map((p) => p.balance), floor) * 1.08;

  const floorLine = document.createElement("div");
  floorLine.className = "floor-line";
  floorLine.style.bottom = (floor / maxv) * 100 + "%";
  el.appendChild(floorLine);

  planned.forEach((p, i) => {
    const wrap = document.createElement("div");
    wrap.className = "bar-wrap";
    const n = naive[i];
    const nb = document.createElement("div");
    nb.className = "bar naive" + (n.balance < floor ? " under" : "");
    nb.style.height = Math.max((n.balance / maxv) * 100, 2) + "%";
    nb.title = `${p.date} · everything today: ${sek(n.balance)}`;
    const pb = document.createElement("div");
    pb.className = "bar";
    pb.style.height = Math.max((p.balance / maxv) * 100, 2) + "%";
    pb.title = `${p.date} · planned: ${sek(p.balance)}`;
    wrap.appendChild(pb);
    wrap.appendChild(nb);
    el.appendChild(wrap);
  });
}

function renderUpcoming() {
  const ul = $("ov-upcoming");
  ul.innerHTML = "";
  const events = [];
  DATA.obligations.forEach((o) =>
    events.push({ date: o.due_date, what: o.name, amt: -o.amount })
  );
  DATA.projection.inflows.forEach((i) =>
    events.push({
      date: i.date,
      what: `${i.customer} — expected (avg ${i.avg_lateness_days} days late)`,
      amt: i.amount,
    })
  );
  events.sort((a, b) => a.date.localeCompare(b.date));
  events.slice(0, 6).forEach((e) => {
    const li = document.createElement("li");
    li.innerHTML = `<span class="up-date">${fmtDate(e.date)}</span>
      <span class="up-what">${e.what}</span>
      <span class="up-amt ${e.amt > 0 ? "in" : ""}">${e.amt > 0 ? "+" : "−"}${sek(Math.abs(e.amt))}</span>`;
    ul.appendChild(li);
  });
}

/* ---------- invoices table ---------- */
function allRows() {
  const held = DATA.held.map((h) => ({
    kind: "hold", inv: h.invoice, verdict: h, pay_date: null,
  }));
  const review = DATA.review.map((h) => ({
    kind: "review", inv: h.invoice, verdict: h, pay_date: null,
  }));
  const cleared = DATA.cleared.map((c) => ({
    kind: "ok", inv: c.invoice, verdict: c.verdict, pay_date: c.pay_date, reason: c.reason,
  }));
  return [...held, ...review, ...cleared];
}

function renderInvoices() {
  const tb = document.querySelector("#inv-table tbody");
  tb.innerHTML = "";
  allRows().forEach((r) => {
    const tr = document.createElement("tr");
    if (r.kind === "hold") tr.className = "held";
    const chip =
      r.kind === "hold"
        ? `<span class="status-chip hold">HELD</span>`
        : r.kind === "review"
        ? `<span class="status-chip review">REVIEW</span>`
        : `<span class="status-chip ok">VERIFIED</span>`;
    const verif =
      r.kind === "hold"
        ? `<span class="verif-note bad">account never seen for this supplier</span>`
        : r.kind === "review"
        ? `<span class="verif-note">no org. number — cannot verify</span>`
        : `<span class="verif-note">${(r.verdict.evidence && r.verdict.evidence.times_paid) || ""}${r.verdict.evidence && r.verdict.evidence.times_paid ? "× to this account" : "verified against history"}</span>`;
    tr.innerHTML = `
      <td>${chip}</td>
      <td><b>${r.inv.supplier_name}</b><div class="verif-note">${r.inv.supplier_orgnr || ""}</div></td>
      <td>${r.inv.reference || r.inv.id}</td>
      <td>${fmtDate(r.inv.due_date)}</td>
      <td class="num">${sek(r.inv.amount)}</td>
      <td class="acct-mono">${shortAcct(r.inv.account_id)}</td>
      <td>${verif}</td>`;
    tr.addEventListener("click", () => openDetail(r.inv.id));
    tb.appendChild(tr);
  });
}

/* ---------- invoice detail ---------- */
function openDetail(invoiceId) {
  const r = allRows().find((x) => x.inv.id === invoiceId);
  if (!r) return;
  const inv = r.inv;
  const ev = (r.verdict && r.verdict.evidence) || {};

  $("dt-title").textContent = inv.supplier_name;
  $("dt-supplier").textContent = inv.supplier_name;
  $("dt-orgnr").textContent = inv.supplier_orgnr || "—";
  $("dt-ref").textContent = inv.reference || inv.id;
  $("dt-issued").textContent = fmtDate(inv.issue_date);
  $("dt-due").textContent = fmtDate(inv.due_date);
  $("dt-amount").textContent = sek(inv.amount);

  const flag = $("dt-flag");
  const isHold = r.kind === "hold";
  const isReview = r.kind === "review";
  flag.textContent = isHold ? "HELD" : isReview ? "REVIEW" : "VERIFIED";
  flag.className = "flag big" + (isHold ? "" : isReview ? " review" : " clear");

  const newAcctRow = $("dt-new-acct").parentElement;
  $("dt-new-acct").textContent = shortAcct(inv.account_id);
  newAcctRow.className = "kv acct " + (isHold ? "new" : "known");
  $("dt-firstseen").textContent = isHold ? "account first seen today" : "";

  const known = (ev.known_accounts || [])[0] || {};
  if (ev.paused) {
    // Paused carries no account history — rendering the fraud copy here printed
    // "paid undefined× ... since ".
    $("dt-times").textContent = "—";
    $("dt-known-acct").textContent = "paused";
    $("dt-range").textContent = "paused by you";
    $("dt-bankline").textContent =
      "You paused payments to this supplier" +
      (ev.reason ? ` — “${ev.reason}”` : "") +
      ". Nothing is staged for them until you lift it, whatever the account says.";
  } else if (isHold) {
    $("dt-times").textContent = known.times_paid || "—";
    $("dt-known-acct").textContent = shortAcct(known.account);
    $("dt-range").textContent =
      `${String(known.first_seen || "").slice(0, 7)} → ${String(known.last_seen || "").slice(0, 7)}`;
    $("dt-bankline").textContent =
      `${ev.bank_confirmed_payments || known.times_paid} of them confirmed in the bank's own outgoing transactions — the books claim, the bank proves.`;
  } else if (isReview) {
    $("dt-times").textContent = "—";
    $("dt-known-acct").textContent = "cannot match";
    $("dt-range").textContent = "no org. number on the invoice";
    $("dt-bankline").textContent =
      "Without an organisation number the payment history cannot be matched. Add the supplier's org. number, or verify manually.";
  } else if (ev.trusted_by_owner) {
    // Do not claim the history matched — it did not. You overrode it.
    $("dt-times").textContent = "—";
    $("dt-known-acct").textContent = shortAcct(inv.account_id);
    $("dt-range").textContent = "verified by you";
    $("dt-bankline").textContent =
      "No payment history backs this account. It is cleared because you confirmed " +
      "it directly with the supplier — that attestation is in the log.";
  } else {
    $("dt-times").textContent = ev.times_paid || "—";
    $("dt-known-acct").textContent = shortAcct(inv.account_id);
    $("dt-range").textContent =
      `${String(ev.first_seen || "").slice(0, 7)} → ${String(ev.last_seen || "").slice(0, 7)}`;
    $("dt-bankline").textContent = "Account matches the payment history for this supplier.";
  }

  const strip = $("dt-strip");
  strip.innerHTML = "";
  const n = (ev.paused || ev.trusted_by_owner)
    ? 0
    : (isHold ? known.times_paid : ev.times_paid) || 0;
  for (let i = 0; i < n; i++) {
    const c = document.createElement("span");
    c.className = "tx-cell" + (i % 5 === 4 ? " big" : "");
    strip.appendChild(c);
  }

  $("dt-status").textContent = flag.textContent;
  $("dt-reason").textContent = " " + (r.verdict.reason || "");
  $("dt-verdict-bar").style.background = isHold ? "var(--ink)" : "#1d3311";
  $("dt-regline").style.display = isHold ? "" : "none";

  // trust action: only for held invoices with an orgnr
  const tb = $("dt-trustbar");
  if (isHold && inv.supplier_orgnr && !ev.paused) {
    tb.hidden = false;
    const btn = $("dt-trust-btn");
    btn.disabled = false;
    btn.textContent = "I verified — trust this account";
    btn.onclick = async () => {
      btn.disabled = true;
      btn.textContent = "Recording…";
      try {
        const resp = await fetch("/api/trust", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ orgnr: inv.supplier_orgnr, account: inv.account_id }),
        });
        if (!resp.ok) throw new Error("trust failed: " + resp.status);
        btn.textContent = "Re-screening…";
        await load(true);           // fast re-screen — no LLM, instant
        btn.textContent = "Verified ✓";
        openDetail(inv.id);         // re-render this invoice — now VERIFIED
      } catch (e) {
        btn.textContent = "Failed — retry";
      } finally {
        // Never leave a progress label as the final state: the re-render normally
        // hides this bar, but if the reload bailed the button would otherwise be
        // stranded on "Re-screening…" for an action that already succeeded.
        btn.disabled = false;
        if (btn.textContent === "Re-screening…") btn.textContent = "Verified ✓";
      }
    };
  } else {
    tb.hidden = true;
  }

  // REVIEW has no orgnr to trust against — ask for the missing field instead,
  // then let the normal rule decide. Never a one-click "clear anyway".
  const ob = $("dt-orgnrbar");
  if (ob) {
    if (isReview) {
      ob.hidden = false;
      const inp = $("dt-orgnr-input");
      const obtn = $("dt-orgnr-btn");
      inp.value = "";
      obtn.disabled = false;
      obtn.textContent = "Add & re-screen";
      obtn.onclick = async () => {
        const orgnr = (inp.value || "").trim();
        if (orgnr.replace(/\D/g, "").length < 10) {
          obtn.textContent = "Needs 10 digits";
          setTimeout(() => (obtn.textContent = "Add & re-screen"), 1600);
          return;
        }
        obtn.disabled = true;
        obtn.textContent = "Re-screening…";
        try {
          const resp = await fetch(`/api/invoices/${encodeURIComponent(inv.id)}/orgnr`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ orgnr }),
          });
          if (!resp.ok) throw new Error("orgnr failed: " + resp.status);
          await load(true);
          openDetail(inv.id);
        } catch (e) {
          obtn.textContent = "Failed — retry";
        } finally {
          obtn.disabled = false;
          if (obtn.textContent === "Re-screening…") obtn.textContent = "Add & re-screen";
        }
      };
    } else {
      ob.hidden = true;
    }
  }

  // notes + pause controls
  renderNotes(inv.id);
  $("dt-note-btn").onclick = async () => {
    const t = $("dt-note-input").value.trim();
    if (!t) return;
    $("dt-note-btn").disabled = true;
    try {
      await fetch(`/api/invoices/${inv.id}/notes`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: t }),
      });
      $("dt-note-input").value = "";
      await load(true);
      renderNotes(inv.id);
    } finally {
      $("dt-note-btn").disabled = false;
    }
  };
  const flags = DATA.supplier_flags || {};
  const orgKey = (inv.supplier_orgnr || "").replace(/\D/g, "");
  const isPaused = !!(flags[orgKey] && flags[orgKey].paused);
  $("dt-pause-state").textContent = isPaused
    ? `Paused since ${String(flags[orgKey].ts || "").slice(0, 10)}${flags[orgKey].reason ? " — " + flags[orgKey].reason : ""}. All invoices from this supplier are held.`
    : "Payments to this supplier are active.";
  const pauseBtn = $("dt-pause-btn");
  pauseBtn.textContent = isPaused ? "Resume payments to this supplier" : "Pause payments to this supplier";
  pauseBtn.disabled = !inv.supplier_orgnr;
  pauseBtn.onclick = async () => {
    pauseBtn.disabled = true;
    try {
      await fetch("/api/suppliers/pause", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ orgnr: inv.supplier_orgnr, paused: !isPaused,
                               reason: $("dt-pause-reason").value.trim() }),
      });
      $("dt-pause-reason").value = "";
      await load(true);
      openDetail(inv.id);
    } finally {
      pauseBtn.disabled = false;
    }
  };

  show("detail");
  document.querySelectorAll(".nav-item").forEach((n) =>
    n.classList.toggle("active", n.dataset.page === "invoices")
  );
}
$("detail-back").addEventListener("click", () => show("invoices"));

function renderNotes(invoiceId) {
  const ul = $("dt-notes");
  ul.innerHTML = "";
  const notes = (DATA.notes || {})[invoiceId] || [];
  if (!notes.length) {
    ul.innerHTML = '<li class="muted">No notes yet.</li>';
    return;
  }
  notes.forEach((n) => {
    const li = document.createElement("li");
    li.innerHTML = `<div class="n-ts">${n.ts.replace("T", " ")}</div>${n.text}`;
    ul.appendChild(li);
  });
}

/* ---------- payments ---------- */
function renderPayments() {
  const today = DATA.cleared.filter((c) => c.pay_date === DATA.today);
  const later = DATA.cleared.filter((c) => c.pay_date !== DATA.today);
  const fill = (id, rows, showDate) => {
    const ul = $(id);
    ul.innerHTML = "";
    rows.forEach((c) => {
      const li = document.createElement("li");
      li.innerHTML = `
        <span>
          <div class="row-name">${c.invoice.supplier_name}</div>
          <div class="row-note">${c.reason}</div>
        </span>
        <span class="row-right">
          <div class="row-amt">${sek(c.invoice.amount)}</div>
          ${showDate ? `<div class="row-date">${fmtDate(c.pay_date)}</div>` : ""}
        </span>`;
      ul.appendChild(li);
    });
  };
  fill("pay-today", today, false);
  fill("pay-later", later, true);
  $("pay-today-count").textContent = today.length;
  $("pay-later-count").textContent = later.length;
  $("bk-count").textContent = today.length + " payments";
  $("bk-total").textContent = sek(today.reduce((s, c) => s + c.invoice.amount, 0));
}

$("stage-btn").addEventListener("click", async () => {
  const btn = $("stage-btn");
  btn.disabled = true;
  btn.textContent = "Staging…";
  try {
    const r = await fetch("/api/basket", { method: "POST" });
    if (!r.ok) throw new Error("basket " + r.status);
    const b = await r.json();
    $("bk-result").hidden = false;
    $("bk-id").textContent = b.basket_id;
    $("bk-status").textContent = b.status;
    btn.textContent = "Stage batch for signing";
  } catch (e) {
    btn.textContent = "Staging failed — retry";
  } finally {
    // Always re-arm: the demo is often run twice, and a button stuck on
    // "Staging…" reads as a hang.
    btn.disabled = false;
  }
});

/* ---------- customers ---------- */
function renderCustomers() {
  const tb = $("cust-body");
  tb.innerHTML = "";
  DATA.projection.inflows.forEach((i) => {
    const tr = document.createElement("tr");
    const late = i.avg_lateness_days;
    tr.innerHTML = `
      <td><b>${i.customer}</b></td>
      <td class="num">${sek(i.amount)}</td>
      <td>${fmtDate(i.due_date)}</td>
      <td>${fmtDate(i.date)}</td>
      <td><span class="habit ${late > 5 ? "late" : "ontime"}">${
        late > 0 ? `avg ${late} days late` : "pays on time"
      }</span></td>`;
    tb.appendChild(tr);
  });
  if (!DATA.projection.inflows.length) {
    tb.innerHTML = `<tr><td colspan="5" class="muted">No outstanding receivables.</td></tr>`;
  }
}

/* ---------- connections ---------- */
async function refreshConnections() {
  try {
    const r = await fetch("/api/connections");
    const c = await r.json();
    const zg = $("conn-zg");
    zg.textContent = c.zwapgrid.connected
      ? "CONNECTED" + (c.zwapgrid.system ? " · " + c.zwapgrid.system : "")
      : c.zwapgrid.pending ? "NO ACCOUNTING SYSTEM BOUND" : "NOT CONNECTED";
    zg.className = "conn-status " + (c.zwapgrid.connected ? "on" : c.zwapgrid.pending ? "wait" : "");
    $("conn-zg-id").textContent = c.zwapgrid.consent_id
      ? c.zwapgrid.consent_id.slice(0, 8) + "…" : "—";
    $("conn-zg-btn").textContent = c.zwapgrid.connected ? "Reconnect" : "Connect bookkeeping";

    const op = $("conn-op");
    op.textContent = c.openpayments.connected ? "CONNECTED" : c.openpayments.pending ? "WAITING FOR SCA" : "NOT CONNECTED";
    op.className = "conn-status " + (c.openpayments.connected ? "on" : c.openpayments.pending ? "wait" : "");
  } catch (e) { /* leave defaults */ }
}

$("conn-zg-btn").addEventListener("click", async () => {
  $("conn-zg-btn").disabled = true;
  $("conn-zg-btn").textContent = "Creating consent…";
  const r = await fetch("/api/connections/zwapgrid", { method: "POST" });
  const d = await r.json();
  $("conn-zg-btn").disabled = false;
  if (d.onboarding_url) {
    $("conn-zg-hint").hidden = false;
    window.open(d.onboarding_url, "_blank");
    $("conn-zg-btn").textContent = "Approval page opened ↗";
    // The consent now exists, so the gate lifts. Refresh the status chip first —
    // it is what the owner is looking at — then paint the data.
    await refreshConnections();
    loadNow();
    pollZg();
  } else {
    $("conn-zg-btn").textContent = "Failed — retry";
  }
});

async function pollZg() {
  for (let i = 0; i < 60; i++) {
    await new Promise((res) => setTimeout(res, 5000));
    await refreshConnections();
    if ($("conn-zg").classList.contains("on")) {
      loadNow();      // ledger now readable — bring the invoices in
      return;
    }
  }
}

$("conn-op-btn").addEventListener("click", async () => {
  const btn = $("conn-op-btn");
  const hint = $("conn-op-hint");
  btn.disabled = true;
  btn.textContent = "Creating bank consent…";
  hint.hidden = false;
  try {
    const r = await fetch("/api/connections/openpayments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ method: "mbid" }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || "consent " + r.status);

    if (d.sca_status) {
      // SEB's decoupled flow: the PSU approves in their own BankID app and the
      // authorisation finalises out-of-band, so poll rather than pretend.
      const names = (d.methods || []).map((m) => m.name).filter(Boolean);
      hint.textContent =
        (d.psu_message || "Confirm in your bank app.") +
        (names.length ? "  ·  SEB offers: " + names.join(", ") : "");
      btn.textContent = "Waiting for BankID…";
      await pollSca(d.consent_id, d.authorisation_id, hint, btn);
    } else if (d.connected) {
      hint.textContent = "Connected — this sandbox bank required no approval.";
      btn.textContent = "Connected ✓";
    } else if (d.sca_url) {
      hint.textContent = "Bank approval page opened in a new tab.";
      window.open(d.sca_url, "_blank");
      btn.textContent = "Approval page opened ↗";
    } else {
      hint.textContent = "No approval route returned — see Agent log.";
      btn.textContent = "Retry";
    }
  } catch (e) {
    hint.textContent = "Could not reach the bank: " + e.message;
    btn.textContent = "Retry";
  } finally {
    btn.disabled = false;
    await refreshConnections();
    loadNow();               // consent cached -> gate lifts -> show the data
  }
});

async function pollSca(consentId, authId, hint, btn) {
  if (!consentId || !authId) return;
  for (let i = 0; i < 10; i++) {
    await new Promise((r) => setTimeout(r, 1500));
    try {
      const r = await fetch(
        `/api/connections/openpayments/sca?consent_id=${encodeURIComponent(consentId)}` +
        `&authorisation_id=${encodeURIComponent(authId)}`
      );
      if (!r.ok) continue;
      const s = await r.json();
      if (s.finalised) {
        hint.textContent = "Approved in the bank app — consent is live.";
        btn.textContent = "Connected ✓";
        await refreshConnections();
        loadNow();
        return;
      }
      btn.textContent = `Waiting for BankID… (${s.sca_status || "started"})`;
    } catch (e) { /* keep polling */ }
  }
  hint.textContent = "Still waiting on BankID approval — reopen this page to re-check.";
  btn.textContent = "Check again";
}

/* ---------- audit ---------- */
async function refreshAudit() {
  const r = await fetch("/api/audit");
  const { entries } = await r.json();
  const ul = $("audit-list");
  ul.innerHTML = "";
  entries.forEach((e) => {
    const li = document.createElement("li");
    li.innerHTML = `<span class="t">${e.ts.slice(11)}</span> <span class="tool">${e.tool}</span> ${e.args} → ${e.result}`;
    ul.appendChild(li);
  });
}

/* ---------- new invoice form ---------- */
$("new-invoice-btn").addEventListener("click", async () => {
  const form = $("new-invoice-form");
  form.hidden = !form.hidden;
  if (!form.hidden) {
    $("f-due").value = DATA ? DATA.today : "";
    try {
      const r = await fetch("/api/suppliers");
      const { suppliers } = await r.json();
      const dl = $("supplier-list");
      dl.innerHTML = "";
      suppliers.forEach((s) => {
        const o = document.createElement("option");
        o.value = s.name;
        o.dataset.orgnr = s.orgnr || "";
        dl.appendChild(o);
      });
      $("f-supplier").onchange = () => {
        const hit = [...dl.options].find((o) => o.value === $("f-supplier").value);
        if (hit && hit.dataset.orgnr) $("f-orgnr").value = hit.dataset.orgnr;
      };
    } catch (e) {}
  }
});
$("f-cancel").addEventListener("click", () => ($("new-invoice-form").hidden = true));
$("f-submit").addEventListener("click", async () => {
  const msg = $("f-msg");
  const btn = $("f-submit");
  msg.textContent = "";
  const payload = {
    supplier_name: $("f-supplier").value,
    supplier_orgnr: $("f-orgnr").value,
    amount: parseFloat($("f-amount").value || "0"),
    due_date: $("f-due").value,
    reference: $("f-ref").value,
    account_id: $("f-account").value,
  };
  btn.disabled = true;
  btn.textContent = "Screening…";
  try {
    const r = await fetch("/api/invoices", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const d = await r.json();
    if (!r.ok) {
      msg.textContent = d.detail || "check the fields";
      return;
    }
    await load(true); // fast re-screen — the new invoice verifies instantly
    $("new-invoice-form").hidden = true;
    ["f-supplier","f-orgnr","f-amount","f-ref","f-account"].forEach((id) => ($(id).value = ""));
    show("invoices");
    if (allRows().find((x) => x.inv.id === d.id)) openDetail(d.id);
  } catch (e) {
    msg.textContent = "Request failed — retry";
  } finally {
    btn.disabled = false;
    btn.textContent = "Register & screen";
  }
});

/* ---------- payroll ---------- */
function renderPayroll() {
  const pr = DATA.payroll || { employees: [], held: [] };
  $("nav-payroll-alerts").hidden = pr.held.length === 0;
  $("nav-payroll-alerts").textContent = pr.held.length;
  $("pr-total").textContent = sek(pr.total_monthly || 0);
  $("pr-next").textContent = fmtDate(pr.next_run);

  const alertCard = $("pr-alert");
  if (pr.held.length) {
    const h = pr.held[0];
    alertCard.hidden = false;
    $("pr-alert-title").textContent = h.employee.name;
    $("pr-alert-sub").textContent = h.reason;
    $("pr-alert-amount").textContent = sek(h.employee.monthly_salary) + "/mo";
    const btn = $("pr-trust-btn");
    btn.disabled = false;
    btn.textContent = "I confirmed with the employee — trust account";
    btn.onclick = async () => {
      btn.disabled = true;
      btn.textContent = "Recording…";
      try {
        const r = await fetch("/api/payroll/trust", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ employee_id: h.employee.id, account: h.employee.account_id }),
        });
        if (!r.ok) throw new Error("failed");
        btn.textContent = "Re-screening…";
        await load(true);
        btn.textContent = "Verified ✓";
        show("payroll");
      } catch (e) {
        btn.textContent = "Failed — retry";
      } finally {
        btn.disabled = false;
        if (btn.textContent === "Re-screening…") btn.textContent = "Verified ✓";
      }
    };
  } else {
    alertCard.hidden = true;
  }

  const tb = $("pr-body");
  tb.innerHTML = "";
  (pr.employees || []).forEach((e) => {
    const v = e.verdict;
    const isHold = v.status === "HOLD";
    const isReview = v.status === "REVIEW";
    const tr = document.createElement("tr");
    if (isHold) tr.className = "held";
    tr.innerHTML = `
      <td>${isHold ? '<span class="status-chip hold">HELD</span>'
          : isReview ? '<span class="status-chip review">REVIEW</span>'
          : '<span class="status-chip ok">VERIFIED</span>'}</td>
      <td><b>${e.name}</b><div class="verif-note">${e.id}</div></td>
      <td>${e.role}</td>
      <td class="num">${sek(e.monthly_salary)}</td>
      <td class="acct-mono">${shortAcct(e.account_id)}</td>
      <td><span class="verif-note${isHold ? " bad" : ""}">${
        isHold ? "account changed " + (e.account_changed_at || "") + " — never received a salary"
        : (v.evidence && v.evidence.times_paid ? v.evidence.times_paid + "× to this account" : v.reason.slice(0, 60))
      }</span></td>`;
    tb.appendChild(tr);
  });
}

/* ---------- reports ---------- */
$("rep-generate").addEventListener("click", async () => {
  const btn = $("rep-generate");
  btn.disabled = true;
  btn.textContent = "Generating…";
  try {
    // The statement covers the last COMPLETE month — asking for the month that
    // is still running returns an empty period and an apology note.
    const t = new Date((DATA && DATA.today ? DATA.today : "2026-08-25") + "T00:00:00");
    const y = t.getMonth() === 0 ? t.getFullYear() - 1 : t.getFullYear();
    const m = t.getMonth() === 0 ? 12 : t.getMonth();   // getMonth() is 0-based => previous month
    const r = await fetch(`/api/report/${y}/${m}?narrate=1`);
    const rep = await r.json();
    $("rep-content").hidden = false;
    $("rep-empty").hidden = true;
    $("rep-period").textContent = rep.period;
    $("rep-narrative").textContent = rep.narrative || "—";
    $("rep-note").textContent = (rep.period_note || "") +
      "  ·  In production this statement is generated on the 1st and emailed automatically; payment failures are listed with the bank's stated reason.";
    $("rep-out-total").textContent = sek(rep.paid_out_total);
    $("rep-out-count").textContent = rep.paid_out_count + " payments";
    const costs = $("rep-costs");
    costs.innerHTML = "";
    rep.top_costs.forEach((c) => {
      const li = document.createElement("li");
      li.innerHTML = `<span class="row-name">${c.name}</span>
        <span class="row-right"><div class="row-amt">${sek(c.amount)}</div></span>`;
      costs.appendChild(li);
    });
    const open = $("rep-open");
    open.innerHTML = "";
    rep.open_invoices.forEach((o) => {
      const li = document.createElement("li");
      li.innerHTML = `<span>
          <div class="row-name">${o.supplier} — ${o.status}</div>
          <div class="row-note">${o.why_not_paid || ""} · due ${fmtDate(o.due)}</div>
        </span>
        <span class="row-right"><div class="row-amt">${sek(o.amount)}</div></span>`;
      open.appendChild(li);
    });
  } catch (e) {
    $("rep-empty").textContent = "Report generation failed — retry.";
  } finally {
    btn.disabled = false;
    btn.textContent = "Generate for August 2026";
  }
});

/* ---------- assistant ---------- */
$("fab").addEventListener("click", () => {
  $("assistant-panel").hidden = !$("assistant-panel").hidden;
  if (!$("assistant-panel").hidden) $("assistant-q").focus();
});
$("assistant-close").addEventListener("click", () => ($("assistant-panel").hidden = true));
async function askAssistant() {
  const q = $("assistant-q").value.trim();
  if (!q) return;
  $("assistant-q").value = "";
  const log = $("assistant-log");
  const user = document.createElement("div");
  user.className = "a-msg user";
  user.textContent = q;
  log.appendChild(user);
  const thinking = document.createElement("div");
  thinking.className = "a-msg bot thinking";
  thinking.textContent = "thinking…";
  log.appendChild(thinking);
  log.scrollTop = log.scrollHeight;
  try {
    const r = await fetch("/api/assistant", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q }),
    });
    const d = await r.json();
    thinking.classList.remove("thinking");
    thinking.textContent = d.answer || "No answer.";
  } catch (e) {
    thinking.textContent = "Request failed — try again.";
  }
  log.scrollTop = log.scrollHeight;
}
$("assistant-send").addEventListener("click", askAssistant);
$("assistant-q").addEventListener("keydown", (e) => e.key === "Enter" && askAssistant());

/* ---------- upload ---------- */
$("upload-btn").addEventListener("click", () => $("upload-input").click());
$("upload-input").addEventListener("change", async () => {
  const f = $("upload-input").files[0];
  if (!f) return;
  const btn = $("upload-btn");
  btn.disabled = true;
  btn.textContent = "Extracting…";
  try {
    const fd = new FormData();
    fd.append("file", f);
    const r = await fetch("/api/upload", { method: "POST", body: fd });
    const d = await r.json();
    const form = $("new-invoice-form");
    form.hidden = false;
    // The form is above the invoice table, so showing it without scrolling left
    // the owner looking at a table wondering where the extracted fields went.
    form.scrollIntoView({ block: "center", behavior: "smooth" });
    const fl = d.fields || {};
    if (fl.supplier_name) $("f-supplier").value = fl.supplier_name;
    if (fl.supplier_orgnr) $("f-orgnr").value = fl.supplier_orgnr;
    if (fl.amount) $("f-amount").value = fl.amount;
    if (fl.due_date) $("f-due").value = fl.due_date;
    if (fl.reference) $("f-ref").value = fl.reference;
    if (fl.account_id) $("f-account").value = fl.account_id;
    const read = String(d.method || "");
    $("f-msg").textContent = read.startsWith("claude")
      ? `Read ${read.includes("ocr") ? "from the image" : "from the file"} ` +
        `(confidence ${Math.round((d.confidence || 0) * 100)}%) — review, then Register & screen.`
      : (d.detail || "Fill the fields manually.");
  } catch (e) {
    $("f-msg").textContent = "Upload failed — fill manually.";
  } finally {
    btn.disabled = false;
    btn.textContent = "⇪ Upload invoice (PDF, image or text)";
    $("upload-input").value = "";
  }
});

// First paint must not wait on the narration: show the screening immediately,
// then swap in the agent's own words when they arrive.
loadNow();
