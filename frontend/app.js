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
  const r = await fetch("/api/briefing" + (fast ? "?fast=1" : ""));
  DATA = await r.json();
  renderOverview();
  renderInvoices();
  renderPayments();
  renderCustomers();
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

  if (DATA.held.length) {
    const h = DATA.held[0];
    const known = (h.evidence.known_accounts || [{}])[0];
    $("ov-held").textContent = sek(DATA.totals.held_sum);
    $("nav-alerts").hidden = false;
    $("nav-alerts").textContent = DATA.held.length;
    $("ov-alert").hidden = false;
    $("ov-alert-title").textContent = h.invoice.supplier_name;
    $("ov-alert-sub").textContent =
      `paid ${known.times_paid}× to one account since ${String(known.first_seen || "").slice(0, 7)} — this invoice names a new one`;
    $("ov-alert-amount").textContent = sek(h.invoice.amount);
    $("ov-alert-open").onclick = () => openDetail(h.invoice.id);
  } else {
    $("ov-held").textContent = "0 SEK";
  }

  renderChart();
  renderUpcoming();
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
  if (isHold) {
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
  } else {
    $("dt-times").textContent = ev.times_paid || "—";
    $("dt-known-acct").textContent = shortAcct(inv.account_id);
    $("dt-range").textContent =
      `${String(ev.first_seen || "").slice(0, 7)} → ${String(ev.last_seen || "").slice(0, 7)}`;
    $("dt-bankline").textContent = "Account matches the payment history for this supplier.";
  }

  const strip = $("dt-strip");
  strip.innerHTML = "";
  const n = (isHold ? known.times_paid : ev.times_paid) || 0;
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
  if (isHold && inv.supplier_orgnr) {
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
        openDetail(inv.id);         // re-render this invoice — now VERIFIED
      } catch (e) {
        btn.textContent = "Failed — retry";
        btn.disabled = false;
      }
    };
  } else {
    tb.hidden = true;
  }

  show("detail");
  document.querySelectorAll(".nav-item").forEach((n) =>
    n.classList.toggle("active", n.dataset.page === "invoices")
  );
}
$("detail-back").addEventListener("click", () => show("invoices"));

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
  const r = await fetch("/api/basket", { method: "POST" });
  const b = await r.json();
  $("bk-result").hidden = false;
  $("bk-id").textContent = b.basket_id;
  $("bk-status").textContent = b.status;
  btn.textContent = "Staged ✓";
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
    zg.textContent = c.zwapgrid.connected ? "CONNECTED" : c.zwapgrid.pending ? "WAITING FOR APPROVAL" : "NOT CONNECTED";
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
    pollZg();
  } else {
    $("conn-zg-btn").textContent = "Failed — retry";
  }
});

async function pollZg() {
  for (let i = 0; i < 60; i++) {
    await new Promise((res) => setTimeout(res, 5000));
    await refreshConnections();
    if ($("conn-zg").classList.contains("on")) return;
  }
}

$("conn-op-btn").addEventListener("click", async () => {
  $("conn-op-btn").disabled = true;
  $("conn-op-btn").textContent = "Creating bank consent…";
  const r = await fetch("/api/connections/openpayments", { method: "POST" });
  const d = await r.json();
  $("conn-op-btn").disabled = false;
  const hint = $("conn-op-hint");
  hint.hidden = false;
  if (d.sca_url) {
    hint.innerHTML = `Bank approval page opened in a new tab. Approve there, then come back.`;
    window.open(d.sca_url, "_blank");
    $("conn-op-btn").textContent = "Approval page opened ↗";
  } else if (d.connected) {
    hint.textContent = "Connected — no user approval required by this sandbox bank.";
  } else {
    hint.textContent = d.detail || "The sandbox did not return an approval link — see Agent log.";
    $("conn-op-btn").textContent = "Retry";
  }
  refreshConnections();
});

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

load();
