from conftest import make_business
from services import accounts


def test_anyone_can_sign_up(db):
    business = make_business(db)
    assert business["slug"] == "encave-cafe"
    # Every business starts with one line that new customers join
    lines = db.execute("SELECT * FROM lines WHERE business_id = ?", (business["id"],)).fetchall()
    assert len(lines) == 1 and lines[0]["is_entry"] == 1


def test_duplicate_email_and_short_password_are_refused(db):
    make_business(db)
    assert accounts.create_business(db, "Other", "owner@encave.test", "password123", "Other")[1]
    assert accounts.create_business(db, "Other", "new@x.test", "short", "Other")[1]


def test_wrong_password_and_lockout(db):
    make_business(db)
    for attempt in range(5):
        business, error = accounts.check_login(db, "owner@encave.test", "nope-nope")
        assert "Wrong email or password" in error
    business, error = accounts.check_login(db, "owner@encave.test", "password123")
    assert "Too many wrong attempts" in error


def test_delete_account_removes_everything(db):
    business = make_business(db)
    accounts.delete_business(db, business["id"])
    assert db.execute("SELECT COUNT(*) FROM businesses").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM lines").fetchone()[0] == 0
