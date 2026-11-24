from conftest import set_pages, sign_up


def ticket_count(db):
    return db.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]


def test_default_flow_details_then_token(client, customer, db):
    sign_up(client)
    response = customer.get("/b/encave-cafe?via=nfc")
    assert response.headers["Location"].endswith("/b/encave-cafe/join/details")
    assert ticket_count(db) == 0

    # Name is required by default
    assert b"Please enter your name" in customer.post("/b/encave-cafe/join/details", data={"name": ""}).data
    response = customer.post("/b/encave-cafe/join/details", data={"name": "Priya"})
    assert "/b/encave-cafe/t/" in response.headers["Location"]

    ticket = db.execute("SELECT * FROM tickets").fetchone()
    assert ticket["name"] == "Priya" and ticket["source"] == "nfc" and ticket["token"] == "001"
    page = customer.get(response.headers["Location"])
    assert b"001" in page.data


def test_closing_the_tab_resumes_where_you_were(client, customer, db):
    sign_up(client)
    client.post("/app/settings/list/add", data={"name": "Cold coffee", "price": "90"})
    set_pages(client, show_list="1", list_multi="1")
    customer.get("/b/encave-cafe")
    customer.post("/b/encave-cafe/join/details", data={"name": "Priya"})
    # Opening the link again (the cookie remembers) goes to the list page, not page 1
    response = customer.get("/b/encave-cafe")
    assert response.headers["Location"].endswith("/join/list")


def test_token_right_away_then_order_saves_to_ticket(client, customer, db):
    sign_up(client)
    client.post("/app/settings/list/add", data={"name": "Cold coffee"})
    client.post("/app/settings/list/add", data={"name": "Brownie"})
    set_pages(client, show_list="1", list_multi="1", token_moment="start")

    customer.get("/b/encave-cafe")
    assert ticket_count(db) == 1           # token handed out before page 1
    customer.post("/b/encave-cafe/join/details", data={"name": "Kabir"})
    items = db.execute("SELECT id FROM list_items ORDER BY id").fetchall()
    customer.post("/b/encave-cafe/join/list", data={f"qty_{items[0]['id']}": "2", f"qty_{items[1]['id']}": "0"})

    ticket = db.execute("SELECT * FROM tickets").fetchone()
    assert ticket["name"] == "Kabir"
    chosen = db.execute("SELECT name, quantity FROM ticket_items").fetchall()
    assert [(row["name"], row["quantity"]) for row in chosen] == [("Cold coffee", 2)]


def test_all_pages_off_just_gives_a_token(client, customer, db):
    sign_up(client)
    set_pages(client, show_details=None)
    response = customer.get("/b/encave-cafe?via=qr")
    assert "/t/" in response.headers["Location"]
    assert ticket_count(db) == 1


def test_extras_page_and_with_token(client, customer, db):
    sign_up(client)
    client.post("/app/settings/extras/add", data={"kind": "link", "title": "Pay by UPI", "body": "upi://pay?pa=cafe@upi", "show_with_token": "1"})
    client.post("/app/settings/extras/add", data={"kind": "link", "body": "javascript:alert(1)"})
    set_pages(client, show_extras="1")
    customer.get("/b/encave-cafe")
    page = customer.post("/b/encave-cafe/join/details", data={"name": "Asha"}, follow_redirects=True)
    assert b"Pay by UPI" in page.data
    assert db.execute("SELECT COUNT(*) FROM extras").fetchone()[0] == 1   # the javascript: link was refused
    page = customer.post("/b/encave-cafe/join/extras", follow_redirects=True)
    assert b"Your token" in page.data and b"Pay by UPI" in page.data


def test_customer_sees_their_turn_and_can_leave(client, customer, db):
    sign_up(client)
    customer.get("/b/encave-cafe")
    ticket_url = customer.post("/b/encave-cafe/join/details", data={"name": "Asha"}).headers["Location"]
    ticket = db.execute("SELECT * FROM tickets").fetchone()

    assert b'data-turn="0"' in customer.get(ticket_url + "/live").data
    client.post(f"/app/ticket/{ticket['id']}/call")
    assert b'data-turn="1"' in customer.get(ticket_url + "/live").data
    assert b"It's your turn" in customer.get(ticket_url + "/live").data

    customer.post(ticket_url + "/leave")
    assert db.execute("SELECT status FROM tickets").fetchone()["status"] == "left"
