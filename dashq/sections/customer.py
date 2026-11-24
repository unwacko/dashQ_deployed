"""The pages a customer sees after scanning the QR code or tapping the NFC sticker.

The flow is split into small pages so it works well on a phone:
  page 1 "details": name / phone / email (the business picks which)
  page 2 "list":    pick from a menu or list of services
  page 3 "extras":  links, pictures and text (payment info, rules, ...)
  then the ticket:  token, place in line, live status

The business can switch any page off, and decide when the token is handed out.
Progress is kept in the (signed) session cookie, so closing the tab by mistake
and opening the link again brings the customer back to where they were.
"""
from datetime import timedelta
import os

from flask import (Blueprint, abort, current_app, flash, redirect, render_template,
                   request, send_from_directory, session, url_for)

from db import execute, get_db
from services import pages, queue
from services.accounts import get_business_by_slug, get_settings, now_text

customer = Blueprint("customer", __name__, url_prefix="/b")


def load_business(slug):
    business = get_business_by_slug(get_db(), slug)
    if business is None:
        abort(404)
    return business


def pages_for(business, settings):
    """The pages this business shows, in order."""
    db = get_db()
    names = []
    if settings["show_details"] == "1" and any(settings[f] != "off" for f in ["ask_name", "ask_phone", "ask_email"]):
        names.append("details")
    if settings["show_list"] == "1" and pages.get_items(db, business["id"], only_available=True):
        names.append("list")
    if settings["show_extras"] == "1" and shown_extras(business, "page"):
        names.append("extras")
    return names


def shown_extras(business, where):
    result = []
    for extra in pages.get_extras(get_db(), business["id"]):
        if where == "page" and extra["show_on_page"]:
            result.append(extra)
        if where == "token" and extra["show_with_token"]:
            result.append(extra)
    return result


# ---------- remembering progress in the cookie ----------

def get_progress(slug):
    return session.get("join", {}).get(slug)


def save_progress(slug, progress):
    everything = session.get("join", {})
    everything[slug] = progress
    session["join"] = everything
    session.permanent = True          # keep it after the browser is closed (see app.py)


def forget_progress(slug):
    everything = session.get("join", {})
    everything.pop(slug, None)
    session["join"] = everything


def active_ticket(business, progress):
    if not progress or not progress.get("code"):
        return None
    ticket = queue.get_ticket_by_code(get_db(), business["id"], progress["code"])
    if ticket is None or ticket["status"] not in queue.ACTIVE:
        return None
    return ticket


def issue_ticket_if_due(business, settings, progress, finished_page):
    """Makes the ticket when the business's chosen moment has come.
    finished_page is the page just finished ('start' when the flow begins, 'end' after the last page)."""
    if progress.get("code"):
        return
    moment = settings["token_moment"]
    if finished_page == moment or finished_page == "end":
        ticket = queue.create_ticket(
            get_db(), business, progress.get("via", "qr"),
            progress.get("name", ""), progress.get("phone", ""), progress.get("email", ""),
        )
        if progress.get("items"):
            queue.set_items(get_db(), business["id"], ticket["id"], progress["items"])
        progress["code"] = ticket["code"]


def go_to(slug, progress, page_names):
    """Sends the customer to the page they are up to."""
    index = progress.get("page", 0)
    if index < len(page_names):
        return redirect(url_for("customer.join_page", slug=slug, page=page_names[index]))
    return redirect(url_for("customer.ticket", slug=slug, code=progress["code"]))


# ---------- routes ----------

@customer.route("/<slug>")
def start(slug):
    business = load_business(slug)
    settings = get_settings(get_db(), business["id"])
    progress = get_progress(slug)

    # Coming back after closing the tab: carry on where they were
    if progress:
        page_names = pages_for(business, settings)
        if progress.get("code") and active_ticket(business, progress):
            return go_to(slug, progress, page_names)
        if progress.get("code"):
            old = queue.get_ticket_by_code(get_db(), business["id"], progress["code"])
            # Just served: show the "all done" screen with a "Join again" button
            if old is not None and old["status"] == "done" and queue.minutes_since(old["finished_at"]) < 30:
                return redirect(url_for("customer.ticket", slug=slug, code=old["code"]))
        if not progress.get("code"):
            if progress.get("page", 0) >= len(page_names):
                issue_ticket_if_due(business, settings, progress, "end")
                save_progress(slug, progress)
            return go_to(slug, progress, page_names)

    via = request.args.get("via", "qr")
    if via not in ("qr", "nfc"):
        via = "qr"
    execute("INSERT INTO page_views (business_id, source, viewed_at) VALUES (?, ?, ?)",
            (business["id"], via, now_text()))

    progress = {"via": via, "page": 0}
    issue_ticket_if_due(business, settings, progress, "start")
    page_names = pages_for(business, settings)
    if not page_names:
        issue_ticket_if_due(business, settings, progress, "end")
    save_progress(slug, progress)
    return go_to(slug, progress, page_names)


@customer.route("/<slug>/join/<page>", methods=["GET", "POST"])
def join_page(slug, page):
    business = load_business(slug)
    db = get_db()
    settings = get_settings(db, business["id"])
    page_names = pages_for(business, settings)
    progress = get_progress(slug)

    if progress is None or page not in page_names:
        return redirect(url_for("customer.start", slug=slug))
    # A ticket that was finished or left: start again
    if progress.get("code") and active_ticket(business, progress) is None:
        forget_progress(slug)
        return redirect(url_for("customer.start", slug=slug))

    ticket = active_ticket(business, progress)
    index = page_names.index(page)
    error = None

    if request.method == "POST":
        if page == "details":
            error = read_details(settings, progress)
            if error is None and ticket is not None:
                queue.update_details(db, business["id"], ticket["id"],
                                     progress.get("name"), progress.get("phone"), progress.get("email"))
        elif page == "list":
            multi = settings["list_multi"] == "1"
            chosen = pages.read_choices(db, business["id"], request.form, multi)
            if not chosen:
                error = "Please choose at least one option."
            else:
                progress["items"] = [list(choice) for choice in chosen]
                if ticket is not None:
                    queue.set_items(db, business["id"], ticket["id"], chosen)

        if error is None:
            progress["page"] = index + 1
            issue_ticket_if_due(business, settings, progress, page)
            if progress["page"] >= len(page_names):
                issue_ticket_if_due(business, settings, progress, "end")
            save_progress(slug, progress)
            return go_to(slug, progress, page_names)
        flash(error, "error")

    # Let the customer go back to earlier pages
    progress["page"] = index
    save_progress(slug, progress)

    items = []
    if page == "list":
        items = pages.items_by_category(pages.get_items(db, business["id"], only_available=True))
    chosen = {}
    for item_id, name, quantity in progress.get("items", []):
        chosen[item_id] = quantity

    return render_template(
        "customer/join.html",
        business=business, settings=settings, page=page, step=index + 1, total=len(page_names) + 1,
        page_names=page_names, progress=progress, ticket=ticket, groups=items, chosen=chosen,
        extras=shown_extras(business, "page"),
        back=url_for("customer.join_page", slug=slug, page=page_names[index - 1]) if index > 0 else None,
    )


def read_details(settings, progress):
    labels = {"name": "your name", "phone": "your phone number", "email": "your email"}
    for field in ["name", "phone", "email"]:
        choice = settings["ask_" + field]
        value = request.form.get(field, "").strip()
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


@customer.route("/<slug>/t/<code>")
def ticket(slug, code):
    business = load_business(slug)
    db = get_db()
    ticket_row = queue.get_ticket_by_code(db, business["id"], code)
    if ticket_row is None:
        abort(404)
    progress = get_progress(slug) or {}
    settings = get_settings(db, business["id"])
    page_names = pages_for(business, settings)
    # Token handed out early, but pages still left to fill in
    pages_left = progress.get("code") == code and progress.get("page", 0) < len(page_names)
    return render_template(
        "customer/ticket.html",
        business=business, ticket=ticket_row, status=queue.customer_status(db, business, ticket_row),
        items=queue.get_items(db, business["id"], ticket_row["id"]),
        extras=shown_extras(business, "token"), pages_left=pages_left,
        continue_url=url_for("customer.start", slug=slug),
    )


@customer.route("/<slug>/t/<code>/live")
def ticket_live(slug, code):
    # The part of the ticket page that refreshes itself every few seconds (htmx)
    business = load_business(slug)
    ticket_row = queue.get_ticket_by_code(get_db(), business["id"], code)
    if ticket_row is None:
        abort(404)
    return render_template("customer/_status.html", business=business, ticket=ticket_row,
                           status=queue.customer_status(get_db(), business, ticket_row))


@customer.route("/<slug>/t/<code>/stop-alert", methods=["POST"])
def stop_alert(slug, code):
    business = load_business(slug)
    ticket_row = queue.get_ticket_by_code(get_db(), business["id"], code)
    if ticket_row is None:
        abort(404)
    queue.stop_alert(get_db(), business["id"], ticket_row["id"])
    return ticket_live(slug, code)


@customer.route("/<slug>/t/<code>/leave", methods=["POST"])
def leave(slug, code):
    business = load_business(slug)
    ticket_row = queue.get_ticket_by_code(get_db(), business["id"], code)
    if ticket_row is not None:
        queue.leave_ticket(get_db(), business["id"], ticket_row["id"])
    forget_progress(slug)
    flash("You left the line. Scan again any time to rejoin.", "ok")
    return redirect(url_for("customer.start", slug=slug))


@customer.route("/<slug>/again", methods=["POST"])
def again(slug):
    forget_progress(slug)
    return redirect(url_for("customer.start", slug=slug))


@customer.route("/<slug>/img/<filename>")
def image(slug, filename):
    business = load_business(slug)
    if not pages.has_image(get_db(), business["id"], filename):
        abort(404)
    folder = pages.folder_for(current_app.config["DATA_DIR"], business["id"])
    return send_from_directory(folder, os.path.basename(filename), max_age=timedelta(days=1))
