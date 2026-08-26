/* Guided tour — Zentra explains itself.
 *
 * The demo link gets opened by people we are not standing next to. Without this
 * they land on a dense finance screen with no idea which number is the point.
 * Steps spotlight one element at a time and say why it matters; a step can move
 * the app to another page first, so the tour walks the real product rather than
 * describing it.
 *
 * Vanilla, no dependencies, matching the rest of the frontend (no build step).
 */

const TOUR_KEY = "zentra.tour.seen.v1";

const STEPS = [
  {
    el: null,
    title: "This is Zentra",
    text:
      "An AI finance assistant for a small Swedish company with no finance " +
      "department. It does three things before any money moves:\n\n" +
      "• catches invoices where the bank account has been swapped\n" +
      "• catches invoices you have already paid once\n" +
      "• times the rest so the cash buffer survives the month\n\n" +
      "This tour takes about a minute.",
  },
  {
    el: null,
    title: "The problem, in one paragraph",
    text:
      "An invoice arrives from a supplier you have paid thirty times before. Same " +
      "logo, same layout, right amount, right reference. One field has changed: the " +
      "bank account number.\n\nYou pay it. You authenticate properly. Every control " +
      "in the chain works exactly as designed, and the money is gone. Sweden recorded " +
      "232 862 fraud offences last year.",
  },
  {
    page: "overview",
    el: "#ov-briefing",
    title: "The morning briefing",
    text:
      "Written by the agent each morning in plain English — what it held, what it is " +
      "paying, and the one number that justifies the plan. Not a dashboard you have " +
      "to interpret.",
  },
  {
    page: "overview",
    el: "#ov-alert",
    title: "1. The invoice that changed its bank account",
    text:
      "Städgrossisten has been paid 31 times since January 2024 — always to the same " +
      "account. This invoice asks for a different one, so it is held before anything " +
      "is staged.",
  },
  {
    page: "detail",
    detailFor: "fraud",
    el: "#dt-strip",
    title: "The evidence, not a score",
    text:
      "Each block is one real payment pulled from the bank. Thirty-one of them, all to " +
      "account 839825. The invoice names 944411, an account that has never appeared " +
      "once.\n\nYour bookkeeping says what should have happened. Your bank says what " +
      "did. Neither can see this alone — the disagreement is the signal.",
  },
  {
    page: "overview",
    el: "#ov-dup",
    title: "2. Invoices you have already paid",
    text:
      "The same comparison, asked the other way round: was this invoice paid twice?\n\n" +
      "Fordonsleasing was paid 12 400 SEK on 8 July and again on 14 July. Both payments " +
      "authorised, both correctly booked — nobody reconciles a payment that succeeded. " +
      "Companies lose 0.1–0.5% of total spend this way.\n\nThe first check prevents a " +
      "loss. This one hands money back.",
  },
  {
    page: "payroll",
    el: "#pr-alert",
    title: "The same rule guards payroll",
    text:
      "Changing an employee's salary account is the same attack wearing different " +
      "clothes, so the identical check runs over every salary payment.",
  },
  {
    el: null,
    title: "What we are not claiming",
    text:
      "Verification of Payee already exists and works — it checks that a name matches " +
      "an account. What it cannot catch is a fraudster who registers a company under " +
      "the right name with a new account. Only payment history catches that.\n\n" +
      "It is also not mandatory for Swedish banks until July 2027.",
  },
  {
    el: null,
    title: "And where this breaks",
    text:
      "A brand-new supplier clears automatically. There is no history to compare " +
      "against — you cannot diff nothing.\n\nThat is why an invoice with no " +
      "organisation number goes to REVIEW rather than CLEAR, and asks you for the " +
      "missing field instead of letting you click past the check.",
  },
  {
    page: "connections",
    el: "#page-connections",
    title: "Both sides, genuinely connected",
    text:
      "Open Payments is the bank — a real consent, approved with BankID. Zwapgrid is " +
      "the bookkeeping. Zentra needs both, because one says what should have happened " +
      "and the other says what did.",
  },
  {
    page: "log",
    el: "#page-log",
    title: "Know Your Agent",
    text:
      "Every tool call the agent made, append-only.\n\nThe language model here has no " +
      "path to a payment API. It receives decided facts and writes English — it cannot " +
      "issue a verdict, and it cannot soften one.",
  },
  {
    page: "overview",
    el: null,
    title: "Zentra prepares. It never signs.",
    text:
      "Staging a batch is the ceiling of its authority. One signature in your own bank " +
      "completes it. That constraint is architectural, not a promise.\n\n" +
      "Restart this tour any time from the ? button, bottom right.",
    last: true,
  },
];

let idx = 0;
let live = [];

function q(sel) {
  if (!sel) return null;
  for (const s of sel.split(",")) {
    const el = document.querySelector(s.trim());
    if (el && el.offsetParent !== null) return el;
  }
  return null;
}

function ensureChrome() {
  if (document.getElementById("tour-overlay")) return;
  const wrap = document.createElement("div");
  wrap.innerHTML = `
    <div id="tour-overlay" hidden>
      <div id="tour-spot"></div>
      <div id="tour-pop" role="dialog" aria-live="polite">
        <div id="tour-step"></div>
        <h3 id="tour-title"></h3>
        <p id="tour-text"></p>
        <div id="tour-actions">
          <button class="tour-skip" id="tour-skip">Skip</button>
          <span class="tour-gap"></span>
          <button class="tour-back" id="tour-back">Back</button>
          <button class="tour-next" id="tour-next">Next</button>
        </div>
      </div>
    </div>
    <button id="tour-launch" title="Show me around">?</button>`;
  document.body.appendChild(wrap);

  document.getElementById("tour-skip").onclick = end;
  document.getElementById("tour-back").onclick = () => go(idx - 1);
  document.getElementById("tour-next").onclick = () => go(idx + 1);
  document.getElementById("tour-launch").onclick = () => start();
  document.addEventListener("keydown", (e) => {
    if (document.getElementById("tour-overlay").hidden) return;
    if (e.key === "Escape") end();
    if (e.key === "ArrowRight" || e.key === "Enter") go(idx + 1);
    if (e.key === "ArrowLeft") go(idx - 1);
  });
  window.addEventListener("resize", () => { if (live.length) place(); });
}

function place() {
  const [step] = live;
  const spot = document.getElementById("tour-spot");
  const pop = document.getElementById("tour-pop");
  const el = q(step.el);

  if (!el) {                        // centred card, no spotlight
    spot.style.opacity = "0";
    pop.style.left = "50%";
    pop.style.top = "50%";
    pop.style.transform = "translate(-50%, -50%)";
    return;
  }
  pop.style.transform = "none";
  const r = el.getBoundingClientRect();
  const pad = 8;
  spot.style.opacity = "1";
  spot.style.left = r.left - pad + "px";
  spot.style.top = r.top - pad + "px";
  spot.style.width = r.width + pad * 2 + "px";
  spot.style.height = r.height + pad * 2 + "px";

  const pw = 380;
  const ph = pop.offsetHeight || 220;
  let left = Math.min(Math.max(12, r.left), window.innerWidth - pw - 12);
  let top = r.bottom + 14;
  if (top + ph > window.innerHeight - 12) top = Math.max(12, r.top - ph - 14);
  pop.style.left = left + "px";
  pop.style.top = top + "px";
}

function go(n) {
  if (n < 0) return;
  if (n >= STEPS.length) return end();
  idx = n;
  const step = STEPS[n];
  live = [step];

  // move the app to the page this step talks about
  if (step.detailFor === "fraud") {
    const held = (typeof DATA !== "undefined" && DATA && DATA.held) || [];
    const target = held.find((h) => ((h.evidence || {}).known_accounts || []).length) || held[0];
    if (target && typeof openDetail === "function") openDetail(target.invoice.id);
    else if (typeof show === "function") show("overview");
  } else if (step.page && typeof show === "function") {
    show(step.page);
  }

  document.getElementById("tour-step").textContent = `${n + 1} of ${STEPS.length}`;
  document.getElementById("tour-title").textContent = step.title;
  document.getElementById("tour-text").textContent = step.text;
  document.getElementById("tour-back").style.visibility = n === 0 ? "hidden" : "visible";
  document.getElementById("tour-next").textContent = step.last ? "Done" : "Next";
  document.getElementById("tour-overlay").hidden = false;

  const el = q(step.el);
  if (el) el.scrollIntoView({ block: "center", behavior: "smooth" });
  setTimeout(place, 260);           // let the scroll settle before measuring
}

function end() {
  const o = document.getElementById("tour-overlay");
  if (o) o.hidden = true;
  live = [];
  try { localStorage.setItem(TOUR_KEY, "1"); } catch (e) { /* private mode */ }
  if (typeof show === "function") show("overview");
}

function start() {
  ensureChrome();
  go(0);
}

/* Auto-run once per browser, but only when there is something to point at —
   an empty product would give the tour nothing to explain. app.js kicks off its
   fetch as this file parses, so wait for the data rather than racing it. */
function dataReady() {
  return typeof DATA !== "undefined" && DATA && Array.isArray(DATA.held) && DATA.held.length > 0;
}

function maybeAutoStart() {
  ensureChrome();
  let seen = false;
  try { seen = localStorage.getItem(TOUR_KEY) === "1"; } catch (e) { seen = false; }
  if (seen) return;

  let tries = 0;
  const poll = setInterval(() => {
    if (dataReady()) { clearInterval(poll); setTimeout(start, 600); return; }
    if (++tries > 40) clearInterval(poll);      // ~12s, then give up quietly
  }, 300);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", maybeAutoStart);
} else {
  maybeAutoStart();
}

window.zentraTour = { start, end };
