"""Businesses, their settings and logins.

Anyone can sign up. There is no superadmin: every business owns its own data.
Every function takes `db` (an open sqlite3 connection) first. No Flask imports
here, so the tests can call these functions directly.
"""
import re
from datetime import datetime, timedelta, timezone

from werkzeug.security import check_password_hash, generate_password_hash

# Settings every new business starts with. All values are stored as text.
# ask_* fields are "off", "optional" or "required".
DEFAULT_SETTINGS = {
    "welcome_text": "Join the line.",
    "ask_name": "required",
    "ask_phone": "optional",
    "ask_email": "off",
    "show_details": "1",        # page 1
    "show_list": "0",           # page 2
    "list_title": "Pick what you need",
    "list_multi": "1",          # 1 = many items with quantities, 0 = choose one
    "show_extras": "0",         # page 3
    "extras_title": "Before you go",
    # When the customer gets their token: start / details / list / end
    "token_moment": "end",
    "avg_service_minutes": "5",
    "theme": "teal",
}

FIELD_CHOICES = ["off", "optional", "required"]
TOKEN_MOMENTS = ["start", "details", "list", "end"]
CATEGORIES = ["Cafe / restaurant", "Clinic", "Salon / spa", "Retail", "Agency / services", "Events", "Other"]

MAX_FAILED_LOGINS = 5
LOCK_MINUTES = 10


def now_text():
    # All times are saved in UTC as text, e.g. 2026-11-22T06:30:00+00:00
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def minutes_from_now_text(minutes):
    later = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return later.isoformat(timespec="seconds")


# ---------- sign up ----------

def make_slug(name):
    # "Encave Cafe!" -> "encave-cafe"
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if slug == "":
        slug = "business"
    return slug[:40]


def unique_slug(db, name):
    base = make_slug(name)
    slug = base
    number = 2
    while db.execute("SELECT 1 FROM businesses WHERE slug = ?", (slug,)).fetchone():
        slug = base + "-" + str(number)
        number += 1
    return slug


def find_by_email(db, email):
    email = email.strip().lower()
    return db.execute("SELECT * FROM businesses WHERE email = ?", (email,)).fetchone()


def get_business(db, business_id):
    return db.execute("SELECT * FROM businesses WHERE id = ?", (business_id,)).fetchone()


def get_business_by_slug(db, slug):
    return db.execute("SELECT * FROM businesses WHERE slug = ?", (slug,)).fetchone()


def check_email_and_password(email, password):
    if "@" not in email or "." not in email or len(email) > 120:
        return "Please enter a valid email address."
    if len(password) < 8:
        return "Your password must be at least 8 characters."
    return None


def create_business(db, name, email, password, category=""):
    """Returns (business_id, error). Exactly one of them is None."""
    name = name.strip()
    email = email.strip().lower()

    if name == "" or len(name) > 80:
        return None, "Please enter your business name (up to 80 characters)."
    error = check_email_and_password(email, password)
    if error:
        return None, error
    if find_by_email(db, email):
        return None, "An account with this email already exists."

    cursor = db.execute(
        "INSERT INTO businesses (name, slug, email, password_hash, category, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (name, unique_slug(db, name), email, generate_password_hash(password), category[:40], now_text()),
    )
    business_id = cursor.lastrowid

    for key, value in DEFAULT_SETTINGS.items():
        db.execute("INSERT INTO settings (business_id, key, value) VALUES (?, ?, ?)",
                   (business_id, key, value))

    # Every business starts with one line, which new customers join
    db.execute(
        "INSERT INTO lines (business_id, name, position, is_entry, customer_label) VALUES (?, ?, 0, 1, ?)",
        (business_id, "Waiting", "You're in the line"),
    )
    db.commit()
    return business_id, None


# ---------- log in ----------

def check_login(db, email, password):
    """Returns (business, error). Exactly one of them is None."""
    business = find_by_email(db, email)
    if business is None:
        return None, "Wrong email or password."

    if business["locked_until"] and business["locked_until"] > now_text():
        return None, "Too many wrong attempts. Please try again in 10 minutes."

    if not check_password_hash(business["password_hash"], password):
        failed = business["failed_logins"] + 1
        locked_until = None
        if failed >= MAX_FAILED_LOGINS:
            locked_until = minutes_from_now_text(LOCK_MINUTES)
            failed = 0
        db.execute("UPDATE businesses SET failed_logins = ?, locked_until = ? WHERE id = ?",
                   (failed, locked_until, business["id"]))
        db.commit()
        return None, "Wrong email or password."

    db.execute("UPDATE businesses SET failed_logins = 0, locked_until = NULL WHERE id = ?",
               (business["id"],))
    db.commit()
    return business, None


# ---------- settings ----------

def get_settings(db, business_id):
    settings = dict(DEFAULT_SETTINGS)
    rows = db.execute("SELECT key, value FROM settings WHERE business_id = ?", (business_id,)).fetchall()
    for row in rows:
        settings[row["key"]] = row["value"]
    return settings


def set_setting(db, business_id, key, value):
    db.execute("INSERT OR REPLACE INTO settings (business_id, key, value) VALUES (?, ?, ?)",
               (business_id, key, value))


def read_whole_number(text, smallest, biggest):
    # Returns the number, or None if the text isn't a whole number in range
    try:
        number = int(text)
    except (TypeError, ValueError):
        return None
    if number < smallest or number > biggest:
        return None
    return number


def save_flow_settings(db, business_id, form):
    """The 'Customer pages' settings. Returns an error or None."""
    welcome = form.get("welcome_text", "").strip()
    if len(welcome) > 300:
        return "The welcome text can be up to 300 characters."

    values = {"welcome_text": welcome}
    for field in ["ask_name", "ask_phone", "ask_email"]:
        choice = form.get(field, "off")
        if choice not in FIELD_CHOICES:
            choice = "off"
        values[field] = choice

    # A checkbox is only sent when it is ticked
    for page in ["show_details", "show_list", "show_extras", "list_multi"]:
        values[page] = "1" if form.get(page) else "0"

    moment = form.get("token_moment", "end")
    if moment not in TOKEN_MOMENTS:
        moment = "end"
    values["token_moment"] = moment
    values["list_title"] = form.get("list_title", "").strip()[:80] or "Pick what you need"
    values["extras_title"] = form.get("extras_title", "").strip()[:80] or "Before you go"

    for key, value in values.items():
        set_setting(db, business_id, key, value)
    db.commit()
    return None


def save_business_details(db, business_id, form):
    name = form.get("name", "").strip()
    if name == "" or len(name) > 80:
        return "Please enter your business name (up to 80 characters)."
    avg = read_whole_number(form.get("avg_service_minutes"), 1, 120)
    if avg is None:
        return "Average service time must be from 1 to 120 minutes."

    # The slug does not change with the name, so printed QR codes and NFC stickers keep working
    db.execute(
        "UPDATE businesses SET name = ?, category = ?, phone = ?, address = ? WHERE id = ?",
        (name, form.get("category", "")[:40], form.get("phone", "").strip()[:20],
         form.get("address", "").strip()[:200], business_id),
    )
    set_setting(db, business_id, "avg_service_minutes", str(avg))
    db.commit()
    return None


def change_password(db, business_id, current, new):
    business = get_business(db, business_id)
    if not check_password_hash(business["password_hash"], current):
        return "Your current password is wrong."
    if len(new) < 8:
        return "Your new password must be at least 8 characters."
    db.execute("UPDATE businesses SET password_hash = ? WHERE id = ?",
               (generate_password_hash(new), business_id))
    db.commit()
    return None


def delete_business(db, business_id):
    # ON DELETE CASCADE removes every line, ticket, item and setting with it
    db.execute("DELETE FROM businesses WHERE id = ?", (business_id,))
    db.commit()
