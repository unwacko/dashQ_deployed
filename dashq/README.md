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
.venv/bin/python main.py
```

The two sample businesses are created the first time it starts.

| Page | Address |
|---|---|
| Home page | http://localhost:5050 |
| Sign up / log in | http://localhost:5050/app/signup · /app/login |
| Sample businesses | click them on the log-in page (password `demo-pass-2026`) |
| Encave's customer page | http://localhost:5050/b/encave-cafe |
| NFC link (same page, marked NFC) | http://localhost:5050/b/encave-cafe?via=nfc |

Tests: `.venv/bin/python -m pytest -q`

---|---|
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

Progress is kept in NiceGUI's browser storage (a signed **cookie**), so if the customer closes the tab by mistake, opening
the link again takes them back to where they were.

When staff call them, the page **beeps** (a WAV made in Python, `services/sound.py`)
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

**Everything is Python.** There are no HTML, CSS or JavaScript files. NiceGUI turns Python code
(`ui.button(...)`, `ui.label(...)`) into the web page and sends clicks back to our Python functions.

| Part | Tool | Why |
|---|---|---|
| Pages | **NiceGUI** (`@ui.page`, `ui.*` elements) | the whole interface in Python |
| Styling | `.classes("...")` and `.props("...")` in Python | ready-made style words, no CSS file |
| Live updates | `ui.timer(3, ...)` + `@ui.refreshable` | redraws the board only when the data changed |
| Drag and drop | `.on("dragstart")` / `.on("drop")` handled in Python | move or reorder cards |
| Charts | matplotlib + seaborn → SVG, shown with `ui.image` | what the team was taught |
| Data | SQLite (`sqlite3`), pandas | plain SQL strings, no ORM |
| QR codes | `qrcode` | |
| Pictures | Pillow | checks and re-saves every upload |
| Alarm sound | `wave` + `math` (standard library) | a beep made by Python |

```
dashq/
├── main.py             start here: python main.py
├── config.py, db.py    settings, tables and the database connection
├── views/              the pages (Python): landing, auth_pages, customer,
│                       board, settings_page, analytics_page, dashboard_frame, common
├── services/           the logic, no web code, easy to test
│   ├── accounts.py     businesses and settings
│   ├── queue.py        lines and tickets: call, done, move, stop/resend alert, board()
│   ├── join_flow.py    the customer's pages and when the token is given
│   ├── pages.py        the list (menu) and extras (links/pictures/text)
│   ├── analytics.py    tickets → pandas DataFrames
│   ├── charts.py       one short function per chart
│   ├── sample_data.py  Encave, Sociovate and 30 days of history
│   ├── sound.py        the beep, written with the `wave` module
│   └── qr.py
├── static/             logo, favicon, chart font
└── tests/
```

### The idea behind the live board, in one paragraph
`board.py` draws the columns inside a `@ui.refreshable` function. A `ui.timer(3, check_for_changes)` reads a
short summary of the tickets every 3 seconds and calls `lanes.refresh()` only when it changed. Buttons call
Python functions directly, for example `on_click=lambda: done(ticket_id)`, which update the database and redraw.

---

## 4. Security notes
- Passwords are hashed (`werkzeug`); 5 wrong tries lock the account for 10 minutes.
- Clicks travel over NiceGUI's live connection for that page, so there are no forms another site could submit.
- Every query filters by `business_id`; `tests/test_board.py` checks one business can't touch another.
- Uploads: JPEG/PNG/WebP only, 4 MB cap, re-saved by Pillow with a random name.
- Links on page 3 must start with `https://`, `http://` or `upi://`.
- The sample accounts can be opened without a password (they're public demos) but can't be deleted.

Older versions are saved in `../_archive/` (v2 with superadmin; v3 built with Flask and HTML templates).
