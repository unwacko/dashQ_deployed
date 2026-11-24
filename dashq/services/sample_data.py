"""Sample data, so the charts and the board have something to show in a demo.

seed_history()          30 days of made-up past customers for one business
make_demo_businesses()  the two sample customers on the landing page: Encave and Sociovate

- Busy hours are lunch (12-2) and evening (5-7). Weekends are quieter.
- About half join by QR, a quarter by NFC, the rest in person.
- Waits grow when more people are already in line. Some people leave.
"""
import secrets
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np

from services import accounts, pages, queue

HOURLY_ARRIVALS = {9: 2, 10: 3, 11: 5, 12: 8, 13: 9, 14: 5, 15: 3, 16: 4, 17: 7, 18: 8, 19: 5, 20: 2}

NAMES = ["Asha", "Ravi", "Meera", "Kabir", "Priya", "Arjun", "Sara", "Vikram", "Neha", "Rohan",
         "Isha", "Dev", "Anaya", "Kiran", "Zoya", "Aman", "Tanvi", "Yash", "Riya", "Omkar"]

DEMO_PASSWORD = "demo-pass-2026"     # only for the two sample accounts


def to_text(moment):
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


def seed_history(db, business_id, days=30, seed=7):
    """Adds the fake history and returns how many tickets were made."""
    rng = np.random.default_rng(seed + business_id)
    business = accounts.get_business(db, business_id)
    avg_service = float(accounts.get_settings(db, business_id)["avg_service_minutes"])
    items = pages.get_items(db, business_id)
    lines = queue.get_lines(db, business_id)
    zone = ZoneInfo(business["timezone"])
    now = datetime.now(zone)
    made = 0

    for days_ago in range(days, 0, -1):
        day = (now - timedelta(days=days_ago)).date()
        busy = 0.6 if day.weekday() >= 5 else 1.0
        busy = busy * rng.uniform(0.8, 1.2) * min(1.0, 5 / avg_service)   # slow services get fewer people
        token_number = 0
        free_at = None          # when the counter is free again

        for hour, rate in HOURLY_ARRIVALS.items():
            arrivals = sorted(rng.uniform(0, 60, rng.poisson(rate * busy)))
            for minute in arrivals:
                joined = datetime(day.year, day.month, day.day, hour, 0, tzinfo=zone) + timedelta(minutes=float(minute))
                if free_at is None or free_at < joined:
                    free_at = joined
                called = free_at + timedelta(minutes=float(rng.uniform(0, 2)))
                service = max(1.0, rng.normal(avg_service, avg_service / 3))
                finished = called + timedelta(minutes=service)
                free_at = finished

                status = "done"
                if rng.random() < 0.06:
                    status = "left"
                token_number += 1
                source = rng.choice(["qr", "nfc", "ip"], p=[0.5, 0.25, 0.25])
                cursor = db.execute(
                    "INSERT INTO tickets (business_id, line_id, token, code, source, name, status, position, "
                    "joined_at, line_joined_at, called_at, finished_at) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)",
                    (business_id, lines[-1]["id"], str(token_number).zfill(3), secrets.token_urlsafe(9), source,
                     rng.choice(NAMES), status, to_text(joined), to_text(joined),
                     to_text(called) if status == "done" else None, to_text(finished)),
                )
                if items:
                    how_many = min(len(items), int(rng.integers(1, 4)))
                    for index in rng.choice(len(items), size=how_many, replace=False):
                        item = items[int(index)]
                        db.execute(
                            "INSERT INTO ticket_items (business_id, ticket_id, item_id, name, quantity) VALUES (?, ?, ?, ?, ?)",
                            (business_id, cursor.lastrowid, item["id"], item["name"], int(rng.integers(1, 3))),
                        )
                made += 1
    db.commit()
    return made


def add_live_customers(db, business, people):
    """A few people waiting right now, so the board isn't empty in a demo.
    people is a list of (line number, name, source, [item names])."""
    lines = queue.get_lines(db, business["id"])
    items = {item["name"]: item for item in pages.get_items(db, business["id"])}
    for line_number, name, source, item_names in people:
        ticket = queue.create_ticket(db, business, source, name=name, line_id=lines[line_number]["id"])
        chosen = [(items[n]["id"], n, 1) for n in item_names if n in items]
        queue.set_items(db, business["id"], ticket["id"], chosen)


def make_demo_businesses(db):
    report = []
    if accounts.find_by_email(db, "encave@demo.dashq.in") is None:
        business_id = make_encave(db)
        report.append(f"Encave: {seed_history(db, business_id)} past tickets")
    if accounts.find_by_email(db, "sociovate@demo.dashq.in") is None:
        business_id = make_sociovate(db)
        report.append(f"Sociovate: {seed_history(db, business_id)} past tickets")
    report.append(f"Log in with encave@demo.dashq.in or sociovate@demo.dashq.in, password {DEMO_PASSWORD}")
    return report


def make_encave(db):
    business_id, error = accounts.create_business(db, "Encave Cafe", "encave@demo.dashq.in", DEMO_PASSWORD, "Cafe / restaurant")
    db.execute("UPDATE businesses SET address = ? WHERE id = ?", ("MIT-WPU campus, Kothrud, Pune", business_id))
    settings = {
        "welcome_text": "Order here. We'll alert you when your food is ready.",
        "ask_name": "required", "ask_phone": "off", "ask_email": "off",
        "show_details": "1", "show_list": "1", "list_title": "What would you like?", "list_multi": "1",
        "show_extras": "1", "extras_title": "Paying", "token_moment": "details", "avg_service_minutes": "4",
    }
    for key, value in settings.items():
        accounts.set_setting(db, business_id, key, value)

    first = queue.get_lines(db, business_id)[0]
    queue.update_line(db, business_id, first["id"], "Ordered", "Order received. We'll start it soon.")
    queue.add_line(db, business_id, "Preparing", "We're making your food.")
    queue.add_line(db, business_id, "Ready to collect", "Your food is ready. Collect it at the counter.")

    menu = [
        ("Coffee", "Cold coffee", "₹90", "Thick, sweet, lots of ice"),
        ("Coffee", "Cappuccino", "₹80", ""),
        ("Coffee", "Masala chai", "₹30", ""),
        ("Food", "Veg sandwich", "₹70", "Grilled, with green chutney"),
        ("Food", "Cheese maggi", "₹60", ""),
        ("Food", "Paneer wrap", "₹110", ""),
        ("Food", "French fries", "₹80", "Peri-peri on request"),
        ("Sweet", "Brownie", "₹70", "Warm, with chocolate sauce"),
    ]
    for category, name, price, description in menu:
        pages.add_item(db, business_id, name, description, category, price)
    db.execute(
        "INSERT INTO extras (business_id, kind, title, body, show_with_token, position) VALUES (?, 'text', ?, ?, 1, 0)",
        (business_id, "Pay at the counter", "UPI and cash are both fine. Show your token when you collect."),
    )
    db.commit()

    business = accounts.get_business(db, business_id)
    add_live_customers(db, business, [
        (0, "Tanvi", "qr", ["Cold coffee", "Veg sandwich"]),
        (0, "Omkar", "nfc", ["Cheese maggi"]),
        (0, "Riya", "qr", ["Masala chai", "Brownie"]),
        (1, "Yash", "ip", ["Paneer wrap", "French fries"]),
        (1, "Isha", "qr", ["Cappuccino"]),
        (2, "Kabir", "nfc", ["Cold coffee"]),
    ])
    return business_id


def make_sociovate(db):
    business_id, error = accounts.create_business(db, "Sociovate Dental Partners", "sociovate@demo.dashq.in", DEMO_PASSWORD, "Clinic")
    settings = {
        "welcome_text": "Check in here. We'll alert you when the doctor is ready.",
        "ask_name": "required", "ask_phone": "required", "ask_email": "off",
        "show_details": "1", "show_list": "0", "show_extras": "0",
        "token_moment": "end", "avg_service_minutes": "15",
    }
    for key, value in settings.items():
        accounts.set_setting(db, business_id, key, value)
    first = queue.get_lines(db, business_id)[0]
    queue.update_line(db, business_id, first["id"], "Waiting room", "Please take a seat. You're in line.")
    queue.add_line(db, business_id, "With the doctor", "Please go in, the doctor is ready for you.")
    db.commit()

    business = accounts.get_business(db, business_id)
    add_live_customers(db, business, [
        (0, "Meera", "qr", []), (0, "Arjun", "ip", []), (0, "Sara", "nfc", []), (1, "Vikram", "qr", []),
    ])
    return business_id
