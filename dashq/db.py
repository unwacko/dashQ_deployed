import os
import sqlite3
import time

from flask import current_app, g


def get_db():
    # One connection per request, stored on flask.g
    if "db" not in g:
        # timeout: if another request is writing, wait up to 10 s instead of failing
        g.db = sqlite3.connect(current_app.config["DATABASE"], timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(database_path, journal_mode="WAL"):
    # Create the tables if they don't exist yet. Safe to run on every start.
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path) as f:
        schema = f.read()
    conn = sqlite3.connect(database_path, timeout=10)

    # gunicorn starts 2 workers at the same moment and both run this.
    # Only one can change the journal mode at a time, so the other waits and tries again.
    for attempt in range(50):
        try:
            conn.execute(f"PRAGMA journal_mode = {journal_mode}")
            break
        except sqlite3.OperationalError:
            time.sleep(0.1)

    conn.executescript(schema)

    # Databases made before the "Stop alert" button need the new column
    columns = [row[1] for row in conn.execute("PRAGMA table_info(tickets)")]
    if "alert_stopped" not in columns:
        conn.execute("ALTER TABLE tickets ADD COLUMN alert_stopped INTEGER NOT NULL DEFAULT 0")
    conn.commit()
    conn.close()


def query(sql, params=(), one=False):
    rows = get_db().execute(sql, params).fetchall()
    if one:
        if rows:
            return rows[0]
        return None
    return rows


def execute(sql, params=()):
    db = get_db()
    cursor = db.execute(sql, params)
    db.commit()
    return cursor.lastrowid
