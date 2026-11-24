# dashQ

**Shorter lines, no app needed.**

dashQ helps businesses run what happens at their counter: queues, orders from a menu, and
"your food is ready" alerts. Customers join in one of three ways (we call it *triple servicing*):

| Way | How | Shown on the board as |
|---|---|---|
| QR code | scan the printed code | `QR` |
| NFC sticker | tap the phone on a sticker | `NFC` |
| In person | staff add them from the dashboard | `IP` |

Anyone can make an account and start. There is no superadmin.

---

## 1. Run it on your laptop

You need Python 3.12.

```bash
cd dashq
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/flask --app app:create_app seed-demo          # the two sample businesses (only once)
.venv/bin/flask --app app:create_app run --debug --port 5050
```

| Page | Address |
|---|---|
| Landing page | http://localhost:5050 |
| Sign up / log in | http://localhost:5050/app/signup · /app/login |
| Sample businesses | click them on the log-in page (password `demo-pass-2026`) |
| Encave's customer page | http://localhost:5050/b/encave-cafe |
| NFC link (same page, marked NFC) | http://localhost:5050/b/encave-cafe?via=nfc |

Tests: `.venv/bin/python -m pytest -q`

---

## 2. What each part does

### The customer (phone)
After scanning, the customer goes through up to three short pages. The business switches each one on or off:

1. **Details**: name, phone, email. Each is *off*, *optional* or *required*.
2. **List**: a menu or list of services. Many items with quantities, or pick one.
3. **Extras**: links (UPI, payment page, map), pictures and text.

Then the **ticket**: token, people ahead, wait estimate, and the line they're in
("Preparing", "Ready to collect"…). The business picks **when** the token is handed out:
right away, after page 1, after page 2, or at the end. Pages after that still save onto the ticket.

Progress is kept in the session **cookie**, so if the customer closes the tab by mistake, opening
the link again takes them back to where they were.

When staff call them, the page **beeps** (a WAV made in Python, `services/sound.py`), **vibrates**,
and **flashes red** until they're served. The customer can press **Stop alert**; the staff card then shows
**Resend alert** to turn it back on.

### The business dashboard (laptop)
- **Live board** (`/app`): one column per line. Each card shows the token, name, how long ago they
  joined, QR/NFC/IP, and what they picked. Buttons: *Call next*, *Call*, *Done*, *Move to another line*,
  *Remove*, and *Add in person*. Drag cards to reorder them or to move them to another line.
- **Settings** (big gear, top right): customer pages, the list/menu, links/pictures/text, the lines
  on your board, and business details (rename, password, delete account).
- **Analytics** (next to settings): 8 matplotlib/seaborn charts: joins per day, how people join (pie),
  busiest times (heatmap), wait by hour (bar), most selected items (bar), line length vs wait
  (scatter), wait distribution (histogram), completed vs left (stacked bar).

---

## 3. How it's built

Python does the work. Libraries do the hard browser parts, so we don't write them ourselves.

| Part | Tool | Why |
|---|---|---|
| Web pages | Flask + Jinja templates | simple to read and explain |
| Live updates | **htmx** (`hx-get`, `hx-trigger="every 3s"`) | refreshes part of a page with HTML from Flask, no custom JavaScript |
| Only change what changed | **idiomorph** (`hx-swap="morph:innerHTML"`) | the board doesn't flicker |
| Smooth animations | **auto-animate** | someone joins/leaves/moves → it slides by itself |
| Drag and drop | **SortableJS** | drag cards between lines |
| Charts | matplotlib + seaborn → SVG | what the team was taught |
| Data | SQLite (`sqlite3`), pandas | plain SQL strings, no ORM |
| QR codes | `qrcode` | |
| Pictures | Pillow | checks and re-saves every upload |

The four libraries load from `cdn.jsdelivr.net` with fixed versions (see `templates/base.html`).
Our own JavaScript is tiny: `board.js` (sets up the two libraries), `ticket.js` (beep + red flash),
`stepper.js` (− / + buttons), `reveal.js` (landing page fade-in).

```
dashq/
├── app.py              create_app(), security headers, error pages, `seed-demo` command
├── auth.py             sign up, log in, demo log in, login_required
├── db.py / schema.sql  SQLite connection and tables
├── sections/           routes only (thin)
│   ├── landing.py      /  and the alarm sound
│   ├── customer.py     /b/<slug>/...  the 3 pages + ticket
│   └── dashboard.py    /app/...  board, settings, analytics
├── services/           the real logic, no Flask, easy to test
│   ├── accounts.py     businesses and settings
│   ├── queue.py        lines and tickets: call, done, move, board()
│   ├── pages.py        the list (menu) and extras (links/pictures/text)
│   ├── analytics.py    tickets → pandas DataFrames
│   ├── charts.py       one short function per chart
│   ├── sample_data.py  Encave, Sociovate and 30 days of history
│   ├── sound.py        the beep, written with the `wave` module
│   └── qr.py
├── templates/  static/  tests/
```

### The idea behind the live board, in one paragraph
`board.html` has a `<div id="live" hx-get="/app/live" hx-trigger="every 3s" hx-swap="morph:innerHTML">`.
Every 3 seconds htmx asks Flask for `/app/live`, which renders `_live.html` with the latest tickets.
idiomorph compares the new HTML with the page and only changes what's different. auto-animate notices
a card was added, removed or moved and animates it. The buttons work the same way: `hx-post="/app/ticket/5/done"`
does the work in Python and sends back the fresh board.

---

## 4. Security notes
- Passwords are hashed (`werkzeug`); 5 wrong tries lock the account for 10 minutes.
- CSRF on every form and every htmx request (the token is sent as a header from `base.html`).
- Every query filters by `business_id`; `tests/test_board.py` checks one business can't touch another.
- Uploads: JPEG/PNG/WebP only, 4 MB cap, re-saved by Pillow with a random name.
- Links on page 3 must start with `https://`, `http://` or `upi://`.
- The sample accounts can be opened without a password (they're public demos) but can't be deleted.

The previous version (with superadmin, rooms, calls) is saved in `../_archive/dashq_v2_before_redesign/`.
