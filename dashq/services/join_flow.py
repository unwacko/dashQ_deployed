"""The steps a customer goes through after scanning the QR code or tapping the NFC sticker.

  page 1 "details": name / phone / email (the business picks which)
  page 2 "list":    pick from a menu or list of services
  page 3 "extras":  links, pictures and text
  then the ticket:  token, place in line, live status

The business can switch any page off, and choose when the token is handed out.
"progress" is a small dict kept in the customer's browser storage:
  {"via": "qr", "page": 1, "name": "Asha", "items": [[id, name, qty]], "code": "..."}
"""
from services import pages, queue
from services.accounts import now_text


def pages_for(db, business, settings):
    """The pages this business shows, in order."""
    names = []
    asks_something = any(settings[field] != "off" for field in ["ask_name", "ask_phone", "ask_email"])
    if settings["show_details"] == "1" and asks_something:
        names.append("details")
    if settings["show_list"] == "1" and pages.get_items(db, business["id"], only_available=True):
        names.append("list")
    if settings["show_extras"] == "1" and shown_extras(db, business, "page"):
        names.append("extras")
    return names


def shown_extras(db, business, where):
    """Links, pictures and text shown on page 3 ("page") or next to the token ("token")."""
    result = []
    for extra in pages.get_extras(db, business["id"]):
        if where == "page" and extra["show_on_page"]:
            result.append(extra)
        if where == "token" and extra["show_with_token"]:
            result.append(extra)
    return result


def active_ticket(db, business, progress):
    """The customer's ticket if they are still in the line, else None."""
    if not progress or not progress.get("code"):
        return None
    ticket = queue.get_ticket_by_code(db, business["id"], progress["code"])
    if ticket is None or ticket["status"] not in queue.ACTIVE:
        return None
    return ticket


def issue_ticket_if_due(db, business, settings, progress, finished_page):
    """Makes the ticket when the business's chosen moment has come.
    finished_page is the page just finished ('start' when the flow begins, 'end' after the last page)."""
    if progress.get("code"):
        return
    moment = settings["token_moment"]
    if finished_page == moment or finished_page == "end":
        ticket = queue.create_ticket(
            db, business, progress.get("via", "qr"),
            progress.get("name", ""), progress.get("phone", ""), progress.get("email", ""),
        )
        if progress.get("items"):
            queue.set_items(db, business["id"], ticket["id"], progress["items"])
        progress["code"] = ticket["code"]


def start(db, business, settings, via):
    """A new visit: count the page view and make a fresh progress dict."""
    if via not in ("qr", "nfc"):
        via = "qr"
    db.execute("INSERT INTO page_views (business_id, source, viewed_at) VALUES (?, ?, ?)",
               (business["id"], via, now_text()))
    db.commit()
    progress = {"via": via, "page": 0}
    issue_ticket_if_due(db, business, settings, progress, "start")
    if not pages_for(db, business, settings):
        issue_ticket_if_due(db, business, settings, progress, "end")
    return progress


def read_details(settings, values, progress):
    """Checks the details page. values = {"name": ..., "phone": ..., "email": ...}.
    Saves them into progress and returns an error message or None."""
    labels = {"name": "your name", "phone": "your phone number", "email": "your email"}
    for field in ["name", "phone", "email"]:
        choice = settings["ask_" + field]
        value = (values.get(field) or "").strip()
        if choice == "off":
            continue
        if choice == "required" and value == "":
            return "Please enter " + labels[field] + "."
        if field == "phone" and value and not value.replace("+", "").replace(" ", "").isdigit():
            return "Please enter a phone number using digits only."
        if field == "email" and value and "@" not in value:
            return "Please enter a valid email."
        progress[field] = value[:120]
    return None


def finish_page(db, business, settings, progress, page, page_names):
    """Moves on after a page was filled in correctly."""
    progress["page"] = page_names.index(page) + 1
    issue_ticket_if_due(db, business, settings, progress, page)
    if progress["page"] >= len(page_names):
        issue_ticket_if_due(db, business, settings, progress, "end")
