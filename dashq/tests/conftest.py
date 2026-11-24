import os
import sys
import tempfile

import pytest

# Every test run uses its own empty data folder (set before main.py or config.py is loaded)
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="dashq-test-")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db as database                  # noqa: E402
from services import accounts, queue   # noqa: E402

# Lets tests click through the real pages without a browser (NiceGUI's "User" helper)
pytest_plugins = ["nicegui.testing.user_plugin"]


@pytest.fixture
def db(tmp_path):
    """A fresh, empty database for tests that call the Python functions directly."""
    return database.connect(str(tmp_path / "test.db"))


def make_business(db, name="Encave Cafe", email="owner@encave.test", password="password123"):
    business_id, error = accounts.create_business(db, name, email, password, "Cafe / restaurant")
    assert error is None
    return accounts.get_business(db, business_id)


def set_pages(db, business, **changes):
    """Save the customer-page settings, starting from the defaults."""
    form = {"welcome_text": "Hi", "ask_name": "required", "ask_phone": "off", "ask_email": "off",
            "show_details": "1", "token_moment": "end", "list_title": "Menu", "extras_title": "Info"}
    form.update(changes)
    form = {key: value for key, value in form.items() if value is not None}
    assert accounts.save_flow_settings(db, business["id"], form) is None
    return accounts.get_settings(db, business["id"])


def tokens_in(db, line_id):
    rows = db.execute("SELECT token FROM tickets WHERE line_id = ? AND status IN ('waiting', 'called') "
                      "ORDER BY position, id", (line_id,)).fetchall()
    return [row["token"] for row in rows]


def first_line(db, business):
    return queue.get_lines(db, business["id"])[0]["id"]
