# Screen-recording prompt — Zentra

> **Note:** the live demo at `192.121.133.232` was decommissioned after Build Day.
> Run locally instead — see the README.

Paste the block below into a browser-automation agent (Claude with computer use,
Browser Use, Operator, Playwright-driven agent) that can drive a browser and record
the screen. Everything in it has been verified against the running app.

---

## THE PROMPT

You are producing a **90-second silent screen recording** of a web app called
Zentra, to be shown to hackathon judges. No narration, no voiceover — the recording
will be captioned later. Your job is to navigate the app calmly and legibly so a
viewer can read each screen.

**Target:** http://192.121.133.232

### Recording settings
- Viewport **1440 × 900**, browser zoom **100%**
- Hide bookmarks bar and any extension toolbars
- Record the browser window only — no desktop, no taskbar, no personal tabs
- **Move the mouse slowly.** Never jump the cursor; glide it to a target, pause
  briefly before clicking. The cursor is the viewer's eye.
- **Do not scroll quickly.** Where scrolling is needed, scroll smoothly and stop.

### Before you start
1. Open a fresh browser window in a **private/incognito** session.
2. Go to `http://192.121.133.232` and do a **hard refresh** (Ctrl+Shift+R).
3. Verify the page shows a red alert box reading
   **"HELD · Städgrossisten AB · 48 000 SEK"**.
   If it does not, stop and report that the demo is not armed — do not record.

### Sequence

**Step 1 — Overview, hold still (0:00–0:12)**
Land on the Overview page. Do nothing for 4 seconds so the page settles.
Slowly move the cursor to the paragraph headed **"Zentra this morning"** and let it
rest beside the text for 6 seconds. Do not click. This paragraph must be readable
in the recording.

**Step 2 — The four figures (0:12–0:20)**
Glide the cursor left to right across the four stat tiles at the top:
*Bank balance · Due this week · Held by Zentra · Lowest point, 14 days.*
Pause about 1 second on each. Do not click.

**Step 3 — The held invoice (0:20–0:28)**
Move the cursor to the red alert card showing **Städgrossisten AB · 48 000 SEK**.
Rest on it for 4 seconds, then click the link **"Review evidence →"**.

**Step 4 — The evidence screen (0:28–0:48)**
A detail page opens. Wait 3 seconds without moving.
Then move the cursor slowly across the row of small blocks (each block is one past
payment) from left to right, taking about 5 seconds to traverse them.
Then rest the cursor for 4 seconds on the two account numbers — the previously used
account and the new one this invoice names. These two values are the single most
important thing in the recording; make sure they are on screen and unobscured.
**Do not click any button on this page.** In particular never click
*"I verified — trust this account"*.

**Step 5 — Payroll (0:48–1:00)**
Click **Payroll** in the left sidebar. Wait 2 seconds.
Rest the cursor on the held-employee alert card for 5 seconds so it can be read.

**Step 6 — Paid twice (1:00–1:15)**
Click **Overview** in the left sidebar. Wait 2 seconds.
Scroll down smoothly until the card titled **"Paid twice"** is fully visible.
Rest the cursor on it for 6 seconds. The amount and the two payment dates must be
legible.

**Step 7 — The agent log (1:15–1:25)**
Click **Agent log** in the left sidebar. Wait 2 seconds.
Scroll down slowly through roughly one screenful of log entries over 5 seconds,
then stop.

**Step 8 — End (1:25–1:30)**
Click **Overview** in the left sidebar. Let the page sit completely still for
4 seconds. Stop recording.

### Rules
- **Never click any button that changes data.** Specifically, do not click:
  *"I verified — trust this account"*, *"Pause payments to this supplier"*,
  *"Stage batch for signing"*, *"Connect bookkeeping"*, *"Connect bank"*,
  *"Add note"*, *"+ New invoice"*, or *"⇪ Upload invoice"*.
  These mutate state and will break the demo for the live pitch.
- If a page fails to load or a screen looks empty, stop and report it. Do not
  improvise a different route.
- Do not open developer tools, the Connections page, or any other tab.
- Deliver the file as MP4, 1440×900, 30fps.

---

## After recording — check these before you use it

- [ ] The "Zentra this morning" paragraph is readable when paused
- [ ] Both account numbers on the evidence screen are legible
- [ ] The "Paid twice" amount and both dates are legible
- [ ] No button that changes data was ever clicked
- [ ] No personal tabs, bookmarks or desktop visible
- [ ] Re-run `curl -X POST http://192.121.133.232/api/reset` afterwards anyway

---

## If you want a longer version

To extend to about **2 minutes**, insert between Step 6 and Step 7:

**Step 6b — Connections**
Click **Connections** in the sidebar. Wait 2 seconds. Rest the cursor for 5 seconds
on the two connection rows so the statuses can be read. **Do not click either
connect button.**

This is worth adding for a judge audience, because it is the on-screen evidence that
both the bank and the bookkeeping connections are genuinely live.
