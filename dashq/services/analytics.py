"""Turns the tickets table into pandas DataFrames for the analytics page.

load() reads everything once. summary() gives the numbers for the top cards.
The charts themselves are drawn in charts.py.
"""
from datetime import datetime, timedelta, timezone

import pandas as pd

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
SOURCE_NAMES = {"qr": "QR code", "nfc": "NFC tap", "ip": "In person"}


def load(db, business, days):
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
    tickets = pd.read_sql_query(
        "SELECT id, source, status, joined_at, called_at, finished_at FROM tickets "
        "WHERE business_id = ? AND joined_at >= ?",
        db, params=(business["id"], since),
    )
    items = pd.read_sql_query(
        "SELECT ticket_items.name, ticket_items.quantity FROM ticket_items "
        "JOIN tickets ON tickets.id = ticket_items.ticket_id "
        "WHERE tickets.business_id = ? AND tickets.joined_at >= ?",
        db, params=(business["id"], since),
    )

    # Text times -> real times in the business's own timezone
    for column in ["joined_at", "called_at", "finished_at"]:
        tickets[column] = pd.to_datetime(tickets[column], utc=True, format="ISO8601").dt.tz_convert(business["timezone"])

    tickets["wait_min"] = (tickets["called_at"] - tickets["joined_at"]).dt.total_seconds() / 60
    tickets["service_min"] = (tickets["finished_at"] - tickets["called_at"]).dt.total_seconds() / 60
    tickets["hour"] = tickets["joined_at"].dt.hour
    tickets["weekday"] = tickets["joined_at"].dt.day_of_week.map(lambda number: WEEKDAYS[number])
    tickets["day"] = tickets["joined_at"].dt.date
    tickets["source_name"] = tickets["source"].map(SOURCE_NAMES)
    tickets["queue_at_join"] = people_ahead(tickets)
    return {"tickets": tickets, "items": items, "days": days}


def people_ahead(tickets):
    """For each ticket: how many people were already waiting when it joined."""
    # A person stops waiting when called (or when they leave the line)
    stopped_waiting = tickets["called_at"].fillna(tickets["finished_at"])
    counts = []
    for row in tickets.itertuples():
        joined_before = tickets["joined_at"] < row.joined_at
        still_waiting = stopped_waiting.isna() | (stopped_waiting > row.joined_at)
        counts.append(int((joined_before & still_waiting).sum()))
    return counts


def summary(data):
    tickets = data["tickets"]
    if tickets.empty:
        return {"total": 0, "avg_wait": 0, "busiest_hour": "—", "top_item": "—", "completed": 0}

    busiest = tickets["hour"].value_counts().idxmax()
    top_item = "—"
    if not data["items"].empty:
        top_item = data["items"].groupby("name")["quantity"].sum().idxmax()
    done = (tickets["status"] == "done").sum()
    return {
        "total": len(tickets),
        "avg_wait": round(tickets["wait_min"].mean(), 1) if tickets["wait_min"].notna().any() else 0,
        "busiest_hour": f"{busiest % 12 or 12} {'am' if busiest < 12 else 'pm'}",
        "top_item": top_item,
        "completed": round(done / len(tickets) * 100),
    }
