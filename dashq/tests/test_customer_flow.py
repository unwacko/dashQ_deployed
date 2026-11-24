"""The customer's steps (services/join_flow.py), without the web page."""
from conftest import make_business, set_pages
from services import join_flow, pages, queue


def ticket_count(db):
    return db.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]


def run_details(db, business, settings, progress, values):
    error = join_flow.read_details(settings, values, progress)
    if error is None:
        join_flow.finish_page(db, business, settings, progress, "details",
                              join_flow.pages_for(db, business, settings))
    return error


def test_default_flow_details_then_token(db):
    business = make_business(db)
    settings = set_pages(db, business)
    progress = join_flow.start(db, business, settings, "nfc")
    assert join_flow.pages_for(db, business, settings) == ["details"]
    assert ticket_count(db) == 0

    assert run_details(db, business, settings, progress, {"name": ""}) == "Please enter your name."
    assert run_details(db, business, settings, progress, {"name": "Priya"}) is None
    ticket = db.execute("SELECT * FROM tickets").fetchone()
    assert ticket["name"] == "Priya" and ticket["source"] == "nfc" and ticket["token"] == "001"
    assert progress["code"] == ticket["code"]


def test_token_right_away_then_order_saves_to_ticket(db):
    business = make_business(db)
    pages.add_item(db, business["id"], "Cold coffee")
    pages.add_item(db, business["id"], "Brownie")
    settings = set_pages(db, business, show_list="1", list_multi="1", token_moment="start")

    progress = join_flow.start(db, business, settings, "qr")
    assert ticket_count(db) == 1           # token handed out before page 1
    coffee = next(item for item in pages.get_items(db, business["id"]) if item["name"] == "Cold coffee")
    chosen = pages.read_choices(db, business["id"], {f"qty_{coffee['id']}": "2"}, True)
    ticket = join_flow.active_ticket(db, business, progress)
    queue.set_items(db, business["id"], ticket["id"], chosen)
    rows = db.execute("SELECT name, quantity FROM ticket_items").fetchall()
    assert [(row["name"], row["quantity"]) for row in rows] == [("Cold coffee", 2)]


def test_all_pages_off_just_gives_a_token(db):
    business = make_business(db)
    settings = set_pages(db, business, show_details=None)
    progress = join_flow.start(db, business, settings, "qr")
    assert progress["code"] and ticket_count(db) == 1


def test_only_safe_links_are_allowed(db):
    business = make_business(db)
    assert pages.add_extra(db, "/tmp", business["id"], "link", "Pay by UPI", "upi://pay?pa=cafe@upi",
                           with_token=True) is None
    assert pages.add_extra(db, "/tmp", business["id"], "link", "", "javascript:alert(1)") is not None
    assert [extra["title"] for extra in join_flow.shown_extras(db, business, "token")] == ["Pay by UPI"]


def test_turn_stop_alert_and_resend(db):
    business = make_business(db)
    ticket = queue.create_ticket(db, business, "qr", name="Asha")
    assert queue.customer_status(db, business, ticket)["alert_on"] is False

    queue.call_ticket(db, business["id"], ticket["id"])
    status = queue.customer_status(db, business, queue.get_ticket(db, business["id"], ticket["id"]))
    assert status["your_turn"] and status["alert_on"]

    queue.stop_alert(db, business["id"], ticket["id"])
    status = queue.customer_status(db, business, queue.get_ticket(db, business["id"], ticket["id"]))
    assert status["your_turn"] and not status["alert_on"]
    assert queue.board(db, business["id"])[0]["tickets"][0]["alert_stopped"] is True

    queue.resend_alert(db, business["id"], ticket["id"])
    status = queue.customer_status(db, business, queue.get_ticket(db, business["id"], ticket["id"]))
    assert status["alert_on"]
