import os
import sqlite3
import sys

import pytest

# Let the tests import app.py from the folder above
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app


@pytest.fixture
def app(tmp_path):
    # Each test gets a fresh, empty database in a temporary folder
    return create_app({"TESTING": True, "DATA_DIR": str(tmp_path), "WTF_CSRF_ENABLED": False})


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def customer(app):
    # A second browser: the customer's phone, with its own cookies
    return app.test_client()


@pytest.fixture
def db(app):
    # A direct connection, for checking what ended up in the database
    conn = sqlite3.connect(app.config["DATABASE"])
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    yield conn
    conn.close()


def sign_up(client, name="Encave Cafe", email="owner@encave.test", password="password123"):
    return client.post("/app/signup", data={"name": name, "email": email, "password": password, "category": "Cafe / restaurant"})


def set_pages(client, **changes):
    """Save the customer-page settings, starting from the defaults."""
    form = {"welcome_text": "Hi", "ask_name": "required", "ask_phone": "off", "ask_email": "off",
            "show_details": "1", "token_moment": "end", "list_title": "Menu", "extras_title": "Info"}
    form.update(changes)
    form = {key: value for key, value in form.items() if value is not None}
    return client.post("/app/settings/pages", data=form)
