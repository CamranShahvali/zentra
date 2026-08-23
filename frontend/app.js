/* Zentra frontend — fetch, render, navigate. No framework, no build step. */

const $ = (id) => document.getElementById(id);
const sek = (n) =>
  new Intl.NumberFormat("sv-SE", { maximumFractionDigits: 0 }).format(Math.round(n)) + " SEK";
const shortAcct = (a) => (a && a.length > 10 ? a.slice(0, 4) + " …" + a.slice(-6) : a || "—");

let DATA = null;

async function load() {
  const r = await fetch("/api/briefing");
  DATA = await r.json();
  renderBriefing();
  renderSignoff();
}

/* ---------- navigation ---------- */
function show(name) {
  document.querySelectorAll(".screen").forEach((s) => s.classList.remove("active"));
  $("screen-" + name).classList.add("active");
  document.querySelectorAll(".crumb").forEach((c) =>
    c.classList.toggle("active", c.dataset.screen === name)
  );
  window.scrollTo({ top: 0, behavior: "instant" });
}
document.querySelectorAll(".crumb").forEach((c) =>
  c.addEventListener("click", () => !c.disabled && show(c.dataset.screen))
);

/* ---------- screen 1 ---------- */
function renderBriefing() {
  const d = new Date(DATA.today + "T08:00:00");
  $("date-line").textContent =
    d.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" }) +
    " · 08:00";
  $("briefing-text").textContent = DATA.briefing;
  $("author-chip").textContent =
    DATA.briefing_author === "claude" ? "written by the agent" : "deterministic briefing";

  $("stat-balance").textContent = sek(DATA.balance);
  $("stat-naive").textContent = sek(DATA.projection.naive.min_balance);
  $("stat-planned").textContent = sek(DATA.projection.planned.min_balance);
  $("stat-planned-sub").textContent =
    "lowest projected balance · buffer floor " + sek(DATA.projection.buffer_floor);

  if (DATA.held.length) {
    const h = DATA.held[0];
    const inv = h.invoice;
    const known = (h.evidence.known_accounts || [{}])[0];
    $("hold-card").hidden = false;
    $("hold-supplier").textContent = inv.supplier_name;
    $("hold-amount").textContent = sek(inv.amount);
    $("hold-line").textContent =
      `Paid ${known.times_paid} times to the same account since ${String(known.first_seen || "").slice(0, 7)}. ` +
      `This invoice names a different account — first seen today. Held until you verify by phone.`;
    $("crumb-evidence").disabled = false;
  }

  const list = $("cleared-list");
  list.innerHTML = "";
  DATA.cleared.forEach((c) => {
    const li = document.createElement("li");
    li.innerHTML = `
      <span class="tick">✓</span>
      <span>
        <div class="li-name">${c.invoice.supplier_name}</div>
        <div class="li-note">${c.verdict.reason}</div>
      </span>
      <span class="li-date">${c.pay_date}</span>
      <span class="li-amount">${sek(c.invoice.amount)}</span>`;
    list.appendChild(li);
  });
  $("cleared-count").textContent = DATA.cleared.length;

  renderEvidence();
}

/* ---------- screen 2 ---------- */
function renderEvidence() {
  if (!DATA.held.length) return;
  const h = DATA.held[0];
  const inv = h.invoice;
  const ev = h.evidence;
  const known = (ev.known_accounts || [{}])[0];

  $("ev-title").textContent = inv.supplier_name;
  $("ev-supplier").textContent = inv.supplier_name;
  $("ev-orgnr").textContent = inv.supplier_orgnr || "—";
  $("ev-amount").textContent = sek(inv.amount);
  $("ev-due").textContent = inv.due_date;
  $("ev-new-acct").textContent = shortAcct(ev.new_account_display || ev.new_account);
  $("ev-times").textContent = known.times_paid;
  $("ev-known-acct").textContent = shortAcct(known.account);
  $("ev-range").textContent =
    `${String(known.first_seen || "").slice(0, 7)} → ${String(known.last_seen || "").slice(0, 7)}`;
  $("ev-verdict").textContent = " " + h.reason;
  $("ev-bankline").textContent =
    `${ev.bank_confirmed_payments} of them confirmed in the bank's own outgoing transaction history — ` +
    `the books claim, the bank proves.`;

  const strip = $("tx-strip");
  strip.innerHTML = "";
  for (let i = 0; i < (known.times_paid || 0); i++) {
    const cell = document.createElement("span");
    cell.className = "tx-cell" + (i % 5 === 4 ? " big" : "");
    strip.appendChild(cell);
  }
}

/* ---------- screen 3 ---------- */
function renderSignoff() {
  const today = DATA.cleared.filter((c) => c.pay_date === DATA.today);
  const later = DATA.cleared.filter((c) => c.pay_date !== DATA.today);

  const fill = (elId, rows, showDate) => {
    const ul = $(elId);
    ul.innerHTML = "";
    rows.forEach((c) => {
      const li = document.createElement("li");
      li.innerHTML = `
        <span>
          <div class="li-name">${c.invoice.supplier_name}</div>
          <div class="li-note">${c.reason}</div>
        </span>
        ${showDate ? `<span class="li-date">${c.pay_date}</span>` : ""}
        <span class="li-amount">${sek(c.invoice.amount)}</span>`;
      ul.appendChild(li);
    });
  };
  fill("plan-today", today, false);
  fill("plan-later", later, true);
  $("today-count").textContent = today.length;
  $("later-count").textContent = later.length;
  $("basket-total").textContent = sek(today.reduce((s, c) => s + c.invoice.amount, 0));
  $("basket-count").textContent = `${today.length} payments · one signature`;
}

$("to-signoff").addEventListener("click", () => show("signoff"));
$("open-evidence").addEventListener("click", () => show("evidence"));

$("stage-btn").addEventListener("click", async () => {
  $("stage-btn").disabled = true;
  $("stage-btn").textContent = "Staging…";
  const r = await fetch("/api/basket", { method: "POST" });
  const b = await r.json();
  $("basket-result").hidden = false;
  $("basket-id").textContent = b.basket_id;
  $("basket-status").textContent = b.status;
  $("stage-btn").textContent = "Staged ✓";
  refreshAudit();
});

/* ---------- audit drawer ---------- */
async function refreshAudit() {
  const r = await fetch("/api/audit");
  const { entries } = await r.json();
  const ul = $("audit-list");
  ul.innerHTML = "";
  entries.forEach((e) => {
    const li = document.createElement("li");
    li.innerHTML = `<span class="t">${e.ts.slice(11)}</span> <span class="tool">${e.tool}</span> ${e.args} <span class="r">→ ${e.result}</span>`;
    ul.appendChild(li);
  });
}
$("audit-toggle").addEventListener("click", async () => {
  await refreshAudit();
  $("drawer").classList.add("open");
});
$("drawer-close").addEventListener("click", () => $("drawer").classList.remove("open"));

load();
