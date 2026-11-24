"""The SQLite database: the tables, and one shared connection.

NiceGUI runs the whole app in one Python process, so one connection is enough.
Every table with business data has a business_id column, and every query filters by it.
"""
import os
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS businesses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    category TEXT,                              -- cafe / clinic / salon / ...
    phone TEXT,
    address TEXT,
    timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
    failed_logins INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT,
    created_at TEXT NOT NULL
);

-- Simple key/value settings: which pages the customer sees, which fields we ask, ...
CREATE TABLE IF NOT EXISTS settings (
    business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    key TEXT NOT NULL,
    value TEXT,
    PRIMARY KEY (business_id, key)
);

-- The columns on the dashboard: "Ordering", "Preparing", "Ready", "Delivery agents"
CREATE TABLE IF NOT EXISTS lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    is_entry INTEGER NOT NULL DEFAULT 0,        -- 1 = new customers land in this line
    customer_label TEXT                         -- what the customer sees while in this line, e.g. "Your food is ready"
);

-- Page 2: the list customers pick from (a menu, a list of services)
CREATE TABLE IF NOT EXISTS list_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT,
    price TEXT,                                 -- text so "₹120" or "Free" both work
    available INTEGER NOT NULL DEFAULT 1,
    position INTEGER NOT NULL DEFAULT 0
);

-- Page 3: links, pictures and text the business wants to show
CREATE TABLE IF NOT EXISTS extras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,                         -- link / image / text
    title TEXT,
    body TEXT,                                  -- the text, or the URL for a link
    filename TEXT,                              -- for images
    show_on_page INTEGER NOT NULL DEFAULT 1,    -- show on page 3
    show_with_token INTEGER NOT NULL DEFAULT 0, -- also show on the ticket screen
    position INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    line_id INTEGER REFERENCES lines(id) ON DELETE SET NULL,
    token TEXT NOT NULL,                        -- e.g. 014, resets every day
    code TEXT NOT NULL UNIQUE,                  -- random, used in the customer's link and cookie
    source TEXT NOT NULL DEFAULT 'qr',          -- qr / nfc / ip (in person)
    name TEXT,
    phone TEXT,
    email TEXT,
    note TEXT,
    status TEXT NOT NULL DEFAULT 'waiting',     -- waiting / called / done / left
    position REAL NOT NULL DEFAULT 0,           -- order inside its line
    joined_at TEXT NOT NULL,
    line_joined_at TEXT,                        -- when it entered its current line
    called_at TEXT,
    finished_at TEXT,
    alert_stopped INTEGER NOT NULL DEFAULT 0   -- 1 = the customer pressed "Stop alert"
);

CREATE TABLE IF NOT EXISTS ticket_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    item_id INTEGER,
    name TEXT NOT NULL,                         -- copied, so renaming an item keeps old orders right
    quantity INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS page_views (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    source TEXT,
    viewed_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tickets_business ON tickets (business_id, status);
CREATE INDEX IF NOT EXISTS idx_items_ticket ON ticket_items (ticket_id);
CREATE INDEX IF NOT EXISTS idx_views_business ON page_views (business_id, viewed_at);
"""

connection = None


def connect(database_path, journal_mode="WAL"):
    """Opens the database (creating the tables if needed) and keeps it for get_db()."""
    global connection
    os.makedirs(os.path.dirname(database_path), exist_ok=True)
    conn = sqlite3.connect(database_path, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    for attempt in range(50):
        try:
            conn.execute(f"PRAGMA journal_mode = {journal_mode}")
            break
        except sqlite3.OperationalError:
            time.sleep(0.1)
    conn.executescript(SCHEMA)
    # Databases made before the "Stop alert" button need the new column
    columns = [row[1] for row in conn.execute("PRAGMA table_info(tickets)")]
    if "alert_stopped" not in columns:
        conn.execute("ALTER TABLE tickets ADD COLUMN alert_stopped INTEGER NOT NULL DEFAULT 0")
    conn.commit()
    connection = conn
    return conn


def get_db():
    return connection
