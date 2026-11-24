"""Clicks through the real pages with NiceGUI's User helper (no browser needed)."""
from nicegui.testing import User

import db as database
from services import accounts, queue


async def test_sign_up_lands_on_the_board(user: User):
    await user.open("/app/signup")
    user.find("Business name").type("Kiran Salon")
    user.find("Email").type("kiran@salon.test")
    user.find("Password (at least 8 characters)").type("password123")
    user.find("Create account").click()
    await user.should_see("Your queue is ready")
    await user.should_see("Call next")


async def test_dashboard_needs_login(user: User):
    await user.open("/app/settings")
    await user.should_see("Log in")


async def test_customer_joins_and_gets_their_turn(user: User):
    db = database.get_db()
    business_id, error = accounts.create_business(db, "Asha Clinic", "asha@clinic.test", "password123", "Clinic")
    business = accounts.get_business(db, business_id)

    await user.open(f"/b/{business['slug']}?via=nfc")
    user.find("Your name").type("Priya")
    user.find("Get my token").click()
    await user.should_see("YOUR TOKEN")
    ticket = db.execute("SELECT * FROM tickets WHERE business_id = ?", (business_id,)).fetchone()
    assert ticket["name"] == "Priya" and ticket["source"] == "nfc"

    queue.call_ticket(db, business_id, ticket["id"])
    await user.open(f"/b/{business['slug']}/t/{ticket['code']}")
    await user.should_see("It's your turn")
    user.find("Stop alert").click()
    await user.should_see("Alert stopped.")
    assert queue.get_ticket(db, business_id, ticket["id"])["alert_stopped"] == 1


async def test_home_page(user: User):
    await user.open("/")
    await user.should_see("Features coming")
    await user.should_see("SMS alerts")
