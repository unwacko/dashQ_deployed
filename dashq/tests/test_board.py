from conftest import first_line, make_business, tokens_in
from services import pages, queue


def test_in_person_call_next_and_done(db):
    business = make_business(db)
    line = first_line(db, business)
    queue.create_ticket(db, business, "ip", name="Ravi", line_id=line)
    queue.create_ticket(db, business, "ip", name="Meera", line_id=line)

    called = queue.call_next(db, business["id"], line)
    assert called["token"] == "001" and called["status"] == "called" and called["called_at"]
    queue.complete_ticket(db, business["id"], called["id"])
    assert tokens_in(db, line) == ["002"]


def test_reorder_and_move_between_lines(db):
    business = make_business(db)
    queue.add_line(db, business["id"], "Ready")
    first, second = [line["id"] for line in queue.get_lines(db, business["id"])]
    ids = [queue.create_ticket(db, business, "ip", name=name, line_id=first)["id"] for name in "ABC"]

    queue.move_ticket(db, business["id"], ids[2], first, ids[0])          # drag C to the top
    assert tokens_in(db, first) == ["003", "001", "002"]

    queue.call_ticket(db, business["id"], ids[1])                         # call B, then move it
    queue.move_ticket(db, business["id"], ids[1], second)
    assert tokens_in(db, second) == ["002"]
    assert queue.get_ticket(db, business["id"], ids[1])["status"] == "waiting"


def test_deleting_a_line_moves_its_people(db):
    business = make_business(db)
    queue.add_line(db, business["id"], "Ready")
    first, second = [line["id"] for line in queue.get_lines(db, business["id"])]
    queue.create_ticket(db, business, "ip", name="Zoya", line_id=second)
    assert queue.delete_line(db, business["id"], second) is None
    assert tokens_in(db, first) == ["001"]
    assert queue.delete_line(db, business["id"], first) is not None       # the last line stays


def test_businesses_cannot_touch_each_other(db):
    cafe = make_business(db, "Cafe A", "a@x.test")
    clinic = make_business(db, "Clinic B", "b@x.test")
    ticket = queue.create_ticket(db, cafe, "ip", name="Secret")
    queue.complete_ticket(db, clinic["id"], ticket["id"])
    assert queue.get_ticket(db, cafe["id"], ticket["id"])["status"] == "waiting"
    assert all(not line["tickets"] for line in queue.board(db, clinic["id"]))
    assert queue.create_ticket(db, clinic, "ip", line_id=first_line(db, cafe))["line_id"] != first_line(db, cafe)


def test_add_in_person_with_list_items(db):
    business = make_business(db)
    pages.add_item(db, business["id"], "Cold coffee")
    item = pages.get_items(db, business["id"])[0]
    ticket = queue.create_ticket(db, business, "ip", name="Ravi")
    chosen = pages.read_choices(db, business["id"], {f"qty_{item['id']}": "2"}, multi=True)
    queue.set_items(db, business["id"], ticket["id"], chosen)
    assert queue.board(db, business["id"])[0]["tickets"][0]["order"] == [{"name": "Cold coffee", "quantity": 2}]
