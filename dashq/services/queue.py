"""Lines and tickets: the heart of dashQ.

A business has one or more lines (the columns on its dashboard).
A ticket is one customer. It sits in one line at a time, in a position.
Ticket status: waiting -> called -> done   (or 'left' if the customer leaves)
"""
import secrets
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from services.accounts import get_settings, now_text

SOURCES = ["qr", "nfc", "ip"]
ACTIVE = ("waiting", "called")


# ---------- lines ----------

def get_lines(db, business_id):
    return db.execute(
        "SELECT * FROM lines WHERE business_id = ? ORDER BY position, id", (business_id,)
    ).fetchall()


def get_line(db, business_id, line_id):
    return db.execute(
        "SELECT * FROM lines WHERE business_id = ? AND id = ?", (business_id, line_id)
    ).fetchone()


def entry_line(db, business_id):
    line = db.execute(
        "SELECT * FROM lines WHERE business_id = ? ORDER BY is_entry DESC, position, id LIMIT 1",
        (business_id,),
    ).fetchone()
    return line


def add_line(db, business_id, name, customer_label=""):
    name = name.strip()[:40]
    if name == "":
        return "Please give the line a name."
    count = len(get_lines(db, business_id))
    if count >= 8:
        return "You can have up to 8 lines."
    db.execute(
        "INSERT INTO lines (business_id, name, position, customer_label) VALUES (?, ?, ?, ?)",
        (business_id, name, count, customer_label.strip()[:80]),
    )
    db.commit()
    return None


def update_line(db, business_id, line_id, name, customer_label):
    name = name.strip()[:40]
    if name == "":
        return "Please give the line a name."
    db.execute(
        "UPDATE lines SET name = ?, customer_label = ? WHERE business_id = ? AND id = ?",
        (name, customer_label.strip()[:80], business_id, line_id),
    )
    db.commit()
    return None


def set_entry_line(db, business_id, line_id):
    if get_line(db, business_id, line_id) is None:
        return
    db.execute("UPDATE lines SET is_entry = 0 WHERE business_id = ?", (business_id,))
    db.execute("UPDATE lines SET is_entry = 1 WHERE business_id = ? AND id = ?", (business_id, line_id))
    db.commit()


def move_line(db, business_id, line_id, direction):
    # direction is -1 (left) or +1 (right)
    lines = list(get_lines(db, business_id))
    ids = [line["id"] for line in lines]
    if line_id not in ids:
        return
    index = ids.index(line_id)
    other = index + direction
    if other < 0 or other >= len(ids):
        return
    ids[index], ids[other] = ids[other], ids[index]
    for position, some_id in enumerate(ids):
        db.execute("UPDATE lines SET position = ? WHERE business_id = ? AND id = ?",
                   (position, business_id, some_id))
    db.commit()


def delete_line(db, business_id, line_id):
    lines = get_lines(db, business_id)
    if len(lines) <= 1:
        return "You need at least one line."
    line = get_line(db, business_id, line_id)
    if line is None:
        return None
    db.execute("DELETE FROM lines WHERE business_id = ? AND id = ?", (business_id, line_id))
    # Whoever was in that line goes to the entry line
    if line["is_entry"]:
        first = get_lines(db, business_id)[0]
        db.execute("UPDATE lines SET is_entry = 1 WHERE id = ?", (first["id"],))
    new_home = entry_line(db, business_id)
    db.execute(
        "UPDATE tickets SET line_id = ? WHERE business_id = ? AND (line_id = ? OR line_id IS NULL)",
        (new_home["id"], business_id, line_id),
    )
    db.commit()
    return None


# ---------- tickets ----------

def start_of_today_utc(timezone_name):
    # Midnight in the business's own timezone, written as UTC text
    local_now = datetime.now(ZoneInfo(timezone_name))
    midnight = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight.astimezone(timezone.utc).isoformat(timespec="seconds")


def next_token(db, business):
    # Tokens start again from 001 every day
    row = db.execute(
        "SELECT COUNT(*) FROM tickets WHERE business_id = ? AND joined_at >= ?",
        (business["id"], start_of_today_utc(business["timezone"])),
    ).fetchone()
    return str(row[0] + 1).zfill(3)


def last_position(db, business_id, line_id):
    row = db.execute(
        "SELECT MAX(position) FROM tickets WHERE business_id = ? AND line_id = ? AND status IN ('waiting', 'called')",
        (business_id, line_id),
    ).fetchone()
    if row[0] is None:
        return 0
    return row[0]


def create_ticket(db, business, source, name="", phone="", email="", note="", line_id=None):
    if source not in SOURCES:
        source = "qr"
    if line_id is None or get_line(db, business["id"], line_id) is None:
        line_id = entry_line(db, business["id"])["id"]
    now = now_text()
    code = secrets.token_urlsafe(9)
    cursor = db.execute(
        "INSERT INTO tickets (business_id, line_id, token, code, source, name, phone, email, note, "
        "position, joined_at, line_joined_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (business["id"], line_id, next_token(db, business), code, source,
         clean(name, 60), clean(phone, 20), clean(email, 120), clean(note, 200),
         last_position(db, business["id"], line_id) + 1, now, now),
    )
    db.commit()
    return get_ticket(db, business["id"], cursor.lastrowid)


def clean(text, length):
    # Empty text is saved as NULL
    text = (text or "").strip()[:length]
    if text == "":
        return None
    return text


def get_ticket(db, business_id, ticket_id):
    return db.execute(
        "SELECT * FROM tickets WHERE business_id = ? AND id = ?", (business_id, ticket_id)
    ).fetchone()


def get_ticket_by_code(db, business_id, code):
    return db.execute(
        "SELECT * FROM tickets WHERE business_id = ? AND code = ?", (business_id, code)
    ).fetchone()


def update_details(db, business_id, ticket_id, name, phone, email):
    db.execute(
        "UPDATE tickets SET name = ?, phone = ?, email = ? WHERE business_id = ? AND id = ?",
        (clean(name, 60), clean(phone, 20), clean(email, 120), business_id, ticket_id),
    )
    db.commit()


def set_items(db, business_id, ticket_id, chosen):
    """chosen is a list of (item_id, name, quantity)."""
    db.execute("DELETE FROM ticket_items WHERE business_id = ? AND ticket_id = ?", (business_id, ticket_id))
    for item_id, name, quantity in chosen:
        db.execute(
            "INSERT INTO ticket_items (business_id, ticket_id, item_id, name, quantity) VALUES (?, ?, ?, ?, ?)",
            (business_id, ticket_id, item_id, name, quantity),
        )
    db.commit()


def get_items(db, business_id, ticket_id):
    return db.execute(
        "SELECT name, quantity FROM ticket_items WHERE business_id = ? AND ticket_id = ? ORDER BY id",
        (business_id, ticket_id),
    ).fetchall()


# ---------- staff actions ----------

def call_ticket(db, business_id, ticket_id):
    ticket = get_ticket(db, business_id, ticket_id)
    if ticket is None or ticket["status"] not in ACTIVE:
        return None
    # Keep the first time they were called: that is what the wait-time charts use
    called_at = ticket["called_at"] or now_text()
    db.execute("UPDATE tickets SET status = 'called', called_at = ?, alert_stopped = 0 WHERE id = ?", (called_at, ticket_id))
    db.commit()
    return get_ticket(db, business_id, ticket_id)


def stop_alert(db, business_id, ticket_id):
    """The customer pressed "Stop alert": no more sound or red screen."""
    db.execute("UPDATE tickets SET alert_stopped = 1 WHERE business_id = ? AND id = ? AND status = 'called'",
               (business_id, ticket_id))
    db.commit()


def resend_alert(db, business_id, ticket_id):
    """Staff pressed "Resend alert": the customer's phone alerts again."""
    db.execute("UPDATE tickets SET alert_stopped = 0 WHERE business_id = ? AND id = ? AND status = 'called'",
               (business_id, ticket_id))
    db.commit()


def call_next(db, business_id, line_id):
    ticket = db.execute(
        "SELECT * FROM tickets WHERE business_id = ? AND line_id = ? AND status = 'waiting' "
        "ORDER BY position, id LIMIT 1",
        (business_id, line_id),
    ).fetchone()
    if ticket is None:
        return None
    return call_ticket(db, business_id, ticket["id"])


def complete_ticket(db, business_id, ticket_id):
    db.execute(
        "UPDATE tickets SET status = 'done', finished_at = ?, called_at = COALESCE(called_at, ?) "
        "WHERE business_id = ? AND id = ? AND status IN ('waiting', 'called')",
        (now_text(), now_text(), business_id, ticket_id),
    )
    db.commit()


def leave_ticket(db, business_id, ticket_id):
    db.execute(
        "UPDATE tickets SET status = 'left', finished_at = ? "
        "WHERE business_id = ? AND id = ? AND status IN ('waiting', 'called')",
        (now_text(), business_id, ticket_id),
    )
    db.commit()


def move_ticket(db, business_id, ticket_id, line_id, before_id=None):
    """Puts a ticket in a line, just before `before_id` (or at the end).
    Moving to a new line sets it back to 'waiting'."""
    ticket = get_ticket(db, business_id, ticket_id)
    if ticket is None or ticket["status"] not in ACTIVE:
        return
    if get_line(db, business_id, line_id) is None:
        return

    others = db.execute(
        "SELECT id FROM tickets WHERE business_id = ? AND line_id = ? AND status IN ('waiting', 'called') "
        "AND id != ? ORDER BY position, id",
        (business_id, line_id, ticket_id),
    ).fetchall()
    order = [row["id"] for row in others]
    if before_id in order:
        order.insert(order.index(before_id), ticket_id)
    else:
        order.append(ticket_id)

    if line_id != ticket["line_id"]:
        db.execute("UPDATE tickets SET line_id = ?, status = 'waiting', line_joined_at = ? WHERE id = ?",
                   (line_id, now_text(), ticket_id))
    for position, some_id in enumerate(order, start=1):
        db.execute("UPDATE tickets SET position = ? WHERE business_id = ? AND id = ?",
                   (position, business_id, some_id))
    db.commit()


# ---------- what the dashboard and the customer see ----------

def minutes_since(text):
    then = datetime.fromisoformat(text)
    return int((datetime.now(timezone.utc) - then).total_seconds() // 60)


def board(db, business_id):
    """Everything the live dashboard needs, as plain lists and dicts (sent as JSON)."""
    lines = []
    for line in get_lines(db, business_id):
        tickets = db.execute(
            "SELECT * FROM tickets WHERE business_id = ? AND line_id = ? AND status IN ('waiting', 'called') "
            "ORDER BY position, id",
            (business_id, line["id"]),
        ).fetchall()
        cards = []
        for ticket in tickets:
            items = []
            for item in get_items(db, business_id, ticket["id"]):
                items.append({"name": item["name"], "quantity": item["quantity"]})
            cards.append({
                "id": ticket["id"],
                "token": ticket["token"],
                "name": ticket["name"] or "",
                "phone": ticket["phone"] or "",
                "note": ticket["note"] or "",
                "source": ticket["source"],
                "status": ticket["status"],
                "alert_stopped": bool(ticket["alert_stopped"]),
                "joined_at": ticket["joined_at"],
                "minutes": minutes_since(ticket["joined_at"]),
                "order": items,
            })
        lines.append({
            "id": line["id"],
            "name": line["name"],
            "is_entry": bool(line["is_entry"]),
            "tickets": cards,
        })
    return lines


def today_numbers(db, business):
    since = start_of_today_utc(business["timezone"])
    row = db.execute(
        "SELECT COUNT(*) AS joined, "
        "SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) AS served, "
        "SUM(CASE WHEN status IN ('waiting', 'called') THEN 1 ELSE 0 END) AS waiting "
        "FROM tickets WHERE business_id = ? AND joined_at >= ?",
        (business["id"], since),
    ).fetchone()
    waits = db.execute(
        "SELECT joined_at, called_at FROM tickets WHERE business_id = ? AND joined_at >= ? AND called_at IS NOT NULL",
        (business["id"], since),
    ).fetchall()
    total = 0
    for wait in waits:
        total += (datetime.fromisoformat(wait["called_at"]) - datetime.fromisoformat(wait["joined_at"])).total_seconds()
    average = 0
    if waits:
        average = round(total / len(waits) / 60)
    return {
        "joined": row["joined"] or 0,
        "served": row["served"] or 0,
        "waiting": row["waiting"] or 0,
        "avg_wait": average,
    }


def customer_status(db, business, ticket):
    """What the customer's ticket page shows."""
    line = get_line(db, business["id"], ticket["line_id"]) if ticket["line_id"] else None
    ahead = 0
    if ticket["status"] == "waiting" and line is not None:
        row = db.execute(
            "SELECT COUNT(*) FROM tickets WHERE business_id = ? AND line_id = ? AND status = 'waiting' "
            "AND (position < ? OR (position = ? AND id < ?))",
            (business["id"], line["id"], ticket["position"], ticket["position"], ticket["id"]),
        ).fetchone()
        ahead = row[0]
    avg = int(get_settings(db, business["id"])["avg_service_minutes"])
    label = ""
    if line is not None:
        label = line["customer_label"] or line["name"]
    return {
        "token": ticket["token"],
        "status": ticket["status"],
        "your_turn": ticket["status"] == "called",
        "alert_on": ticket["status"] == "called" and not ticket["alert_stopped"],
        "ahead": ahead,
        "wait": ahead * avg,
        "line": line["name"] if line else "",
        "label": label,
        "line_id": line["id"] if line else None,
    }
