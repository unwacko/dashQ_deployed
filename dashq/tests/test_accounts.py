from conftest import sign_up


def test_anyone_can_sign_up_and_lands_on_the_board(client, db):
    response = sign_up(client)
    assert response.status_code == 302
    assert "/app" in response.headers["Location"]
    business = db.execute("SELECT * FROM businesses").fetchone()
    assert business["slug"] == "encave-cafe"
    # Every business starts with one line that new customers join
    lines = db.execute("SELECT * FROM lines WHERE business_id = ?", (business["id"],)).fetchall()
    assert len(lines) == 1 and lines[0]["is_entry"] == 1


def test_duplicate_email_and_short_password_are_refused(client):
    sign_up(client)
    assert sign_up(client).status_code == 400
    assert sign_up(client, email="new@x.test", password="short").status_code == 400


def test_wrong_password_and_lockout(client):
    sign_up(client)
    client.post("/app/logout")
    for attempt in range(5):
        response = client.post("/app/login", data={"email": "owner@encave.test", "password": "nope-nope"})
        assert b"Wrong email or password" in response.data
    response = client.post("/app/login", data={"email": "owner@encave.test", "password": "password123"})
    assert b"Too many wrong attempts" in response.data


def test_dashboard_needs_login(client):
    assert client.get("/app").status_code == 302
    assert client.get("/app/settings").status_code == 302


def test_delete_account_removes_everything(client, db):
    sign_up(client)
    client.post("/b/encave-cafe")
    client.post("/app/settings/delete", data={"confirm": "wrong"})
    assert db.execute("SELECT COUNT(*) FROM businesses").fetchone()[0] == 1
    client.post("/app/settings/delete", data={"confirm": "encave-cafe"})
    assert db.execute("SELECT COUNT(*) FROM businesses").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM lines").fetchone()[0] == 0
