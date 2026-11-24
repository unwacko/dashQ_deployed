from conftest import sign_up


def add(client, line_id, name):
    return client.post(f"/app/line/{line_id}/add", data={"name": name})


def tokens_in(db, line_id):
    rows = db.execute("SELECT token FROM tickets WHERE line_id = ? AND status IN ('waiting', 'called') "
                      "ORDER BY position, id", (line_id,)).fetchall()
    return [row["token"] for row in rows]


def test_in_person_call_next_and_done(client, db):
    sign_up(client)
    line = db.execute("SELECT id FROM lines").fetchone()["id"]
    add(client, line, "Ravi")
    add(client, line, "Meera")
    assert db.execute("SELECT source FROM tickets").fetchone()["source"] == "ip"

    response = client.post(f"/app/line/{line}/next")
    assert b"Calling" in response.data and b"001" in response.data
    first = db.execute("SELECT * FROM tickets WHERE token = '001'").fetchone()
    assert first["status"] == "called" and first["called_at"]

    client.post(f"/app/ticket/{first['id']}/done")
    assert db.execute("SELECT status FROM tickets WHERE id = ?", (first["id"],)).fetchone()["status"] == "done"
    assert tokens_in(db, line) == ["002"]


def test_reorder_and_move_between_lines(client, db):
    sign_up(client)
    client.post("/app/settings/lines/add", data={"name": "Ready"})
    first, second = [row["id"] for row in db.execute("SELECT id FROM lines ORDER BY position").fetchall()]
    for name in ["A", "B", "C"]:
        add(client, first, name)
    ids = [row["id"] for row in db.execute("SELECT id FROM tickets ORDER BY id").fetchall()]

    # Drag C to the top
    client.post(f"/app/ticket/{ids[2]}/move", data={"line_id": first, "before_id": ids[0]})
    assert tokens_in(db, first) == ["003", "001", "002"]

    # Call B, then move it to "Ready": it goes back to waiting there
    client.post(f"/app/ticket/{ids[1]}/call")
    client.post(f"/app/ticket/{ids[1]}/move", data={"line_id": second})
    assert tokens_in(db, second) == ["002"]
    assert db.execute("SELECT status FROM tickets WHERE id = ?", (ids[1],)).fetchone()["status"] == "waiting"


def test_deleting_a_line_moves_its_people(client, db):
    sign_up(client)
    client.post("/app/settings/lines/add", data={"name": "Ready"})
    first, second = [row["id"] for row in db.execute("SELECT id FROM lines ORDER BY position").fetchall()]
    add(client, second, "Zoya")
    client.post(f"/app/settings/lines/{second}", data={"action": "delete"})
    assert tokens_in(db, first) == ["001"]
    # The last line can't be deleted
    client.post(f"/app/settings/lines/{first}", data={"action": "delete"})
    assert db.execute("SELECT COUNT(*) FROM lines").fetchone()[0] == 1


def test_businesses_cannot_touch_each_other(app, db):
    owner_a = app.test_client()
    owner_b = app.test_client()
    sign_up(owner_a, name="Cafe A", email="a@x.test")
    sign_up(owner_b, name="Clinic B", email="b@x.test")
    line_a = db.execute("SELECT id FROM lines WHERE business_id = 1").fetchone()["id"]
    add(owner_a, line_a, "Secret")
    ticket = db.execute("SELECT id FROM tickets").fetchone()["id"]

    assert b"Secret" not in owner_b.get("/app/live").data
    owner_b.post(f"/app/ticket/{ticket}/done")
    owner_b.post(f"/app/line/{line_a}/add", data={"name": "Intruder"})
    assert db.execute("SELECT status FROM tickets WHERE id = ?", (ticket,)).fetchone()["status"] == "waiting"
    assert db.execute("SELECT COUNT(*) FROM tickets WHERE business_id = 2").fetchone()[0] == 0


def test_add_in_person_with_list_items(client, db):
    sign_up(client)
    client.post("/app/settings/list/add", data={"name": "Cold coffee"})
    line = db.execute("SELECT id FROM lines").fetchone()["id"]
    item = db.execute("SELECT id FROM list_items").fetchone()["id"]
    board = client.get("/app/live").data
    assert f'name="qty_{item}"'.encode() in board              # the small list is in the form
    client.post(f"/app/line/{line}/add", data={"name": "Ravi", f"qty_{item}": "2"})
    row = db.execute("SELECT name, quantity FROM ticket_items").fetchone()
    assert (row["name"], row["quantity"]) == ("Cold coffee", 2)


def test_customer_stops_alert_and_staff_resend(client, customer, db):
    sign_up(client)
    line = db.execute("SELECT id FROM lines").fetchone()["id"]
    add(client, line, "Ravi")
    ticket = db.execute("SELECT * FROM tickets").fetchone()
    client.post(f"/app/ticket/{ticket['id']}/call")
    slug = db.execute("SELECT slug FROM businesses").fetchone()["slug"]
    live = f"/b/{slug}/t/{ticket['code']}/live"
    assert b'data-turn="1"' in customer.get(live).data and b"Stop alert" in customer.get(live).data

    page = customer.post(f"/b/{slug}/t/{ticket['code']}/stop-alert").data
    assert b'data-turn="0"' in page and b"Alert stopped" in page
    assert b"Resend alert" in client.get("/app/live").data

    client.post(f"/app/ticket/{ticket['id']}/resend-alert")
    assert b'data-turn="1"' in customer.get(live).data
    assert b"Resend alert" not in client.get("/app/live").data
