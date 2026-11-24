"""The business dashboard: the live board, settings and analytics.

The board is plain HTML made by Jinja. htmx asks for /app/live every 3 seconds
and swaps the new HTML in; auto-animate makes the changes slide smoothly.
Every button (Call, Done, Move, ...) posts to a route here, which does the
work and sends back the fresh board.
"""
import shutil

from flask import (Blueprint, Response, abort, current_app, flash, g, redirect, render_template,
                   request, session, url_for)

from auth import login_required
from db import get_db
from services import accounts, analytics, charts, pages, queue
from services.qr import make_qr_png

dashboard = Blueprint("dashboard", __name__, url_prefix="/app")


def join_link(via):
    return url_for("customer.start", slug=g.business["slug"], via=via, _external=True)


def live_html(just_called=None):
    db = get_db()
    return render_template(
        "dashboard/_live.html",
        lines=queue.board(db, g.business["id"]),
        list_items=pages.get_items(db, g.business["id"], only_available=True),
        numbers=queue.today_numbers(db, g.business),
        just_called=just_called,
    )


def read_number(text):
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


# ---------- the board ----------

@dashboard.route("")
@login_required
def board():
    db = get_db()
    return render_template(
        "dashboard/board.html",
        lines=queue.board(db, g.business["id"]),
        list_items=pages.get_items(db, g.business["id"], only_available=True),
        numbers=queue.today_numbers(db, g.business),
        just_called=None,
        welcome=request.args.get("welcome"),
        qr_link=join_link("qr"),
        nfc_link=join_link("nfc"),
        active="board",
    )


@dashboard.route("/live")
@login_required
def live():
    return live_html()


@dashboard.route("/line/<int:line_id>/next", methods=["POST"])
@login_required
def call_next(line_id):
    ticket = queue.call_next(get_db(), g.business["id"], line_id)
    return live_html(just_called=ticket)


@dashboard.route("/ticket/<int:ticket_id>/call", methods=["POST"])
@login_required
def call(ticket_id):
    ticket = queue.call_ticket(get_db(), g.business["id"], ticket_id)
    return live_html(just_called=ticket)


@dashboard.route("/ticket/<int:ticket_id>/resend-alert", methods=["POST"])
@login_required
def resend_alert(ticket_id):
    queue.resend_alert(get_db(), g.business["id"], ticket_id)
    return live_html()


@dashboard.route("/ticket/<int:ticket_id>/done", methods=["POST"])
@login_required
def done(ticket_id):
    queue.complete_ticket(get_db(), g.business["id"], ticket_id)
    return live_html()


@dashboard.route("/ticket/<int:ticket_id>/remove", methods=["POST"])
@login_required
def remove(ticket_id):
    queue.leave_ticket(get_db(), g.business["id"], ticket_id)
    return live_html()


@dashboard.route("/ticket/<int:ticket_id>/move", methods=["POST"])
@login_required
def move(ticket_id):
    line_id = read_number(request.form.get("line_id"))
    before_id = read_number(request.form.get("before_id"))
    if line_id is not None:
        queue.move_ticket(get_db(), g.business["id"], ticket_id, line_id, before_id)
    return live_html()


@dashboard.route("/line/<int:line_id>/add", methods=["POST"])
@login_required
def add_in_person(line_id):
    if queue.get_line(get_db(), g.business["id"], line_id) is None:
        abort(404)
    ticket = queue.create_ticket(
        get_db(), g.business, "ip",
        name=request.form.get("name", ""), phone=request.form.get("phone", ""),
        note=request.form.get("note", ""), line_id=line_id,
    )
    # Items ticked in the small list under the form
    chosen = pages.read_choices(get_db(), g.business["id"], request.form, multi=True)
    if chosen:
        queue.set_items(get_db(), g.business["id"], ticket["id"], chosen)
    return live_html()


@dashboard.route("/qr.png")
@login_required
def qr_png():
    via = request.args.get("via", "qr")
    if via not in ("qr", "nfc"):
        via = "qr"
    response = Response(make_qr_png(join_link(via)), mimetype="image/png")
    if request.args.get("download"):
        response.headers["Content-Disposition"] = f'attachment; filename="dashq-{g.business["slug"]}.png"'
    return response


# ---------- analytics ----------

@dashboard.route("/analytics")
@login_required
def analytics_page():
    days = read_number(request.args.get("days")) or 30
    if days not in (7, 30, 90):
        days = 30
    db = get_db()
    data = analytics.load(db, g.business, days)
    return render_template(
        "dashboard/analytics.html",
        days=days, summary=analytics.summary(data), charts=charts.all_charts(data, g.business["id"], days),
        active="analytics",
    )


@dashboard.route("/analytics/sample", methods=["POST"])
@login_required
def add_sample_data():
    from services.sample_data import seed_history
    seed_history(get_db(), g.business["id"])
    charts.clear_cache()
    flash("Added 30 days of sample history so you can see the charts.", "ok")
    return redirect(url_for("dashboard.analytics_page"))


# ---------- settings ----------

SETTINGS_TABS = ["pages", "list", "extras", "lines", "business"]


@dashboard.route("/settings")
@dashboard.route("/settings/<tab>")
@login_required
def settings(tab="pages"):
    if tab not in SETTINGS_TABS:
        tab = "pages"
    db = get_db()
    business_id = g.business["id"]
    return render_template(
        "dashboard/settings.html",
        tab=tab, active="settings",
        settings=accounts.get_settings(db, business_id),
        items=pages.get_items(db, business_id),
        extras=pages.get_extras(db, business_id),
        lines=queue.get_lines(db, business_id),
        categories=accounts.CATEGORIES,
        qr_link=join_link("qr"), nfc_link=join_link("nfc"),
    )


def back_to(tab, error=None, ok=None):
    if error:
        flash(error, "error")
    elif ok:
        flash(ok, "ok")
    return redirect(url_for("dashboard.settings", tab=tab))


@dashboard.route("/settings/pages", methods=["POST"])
@login_required
def save_pages():
    error = accounts.save_flow_settings(get_db(), g.business["id"], request.form)
    return back_to("pages", error, "Customer pages saved.")


@dashboard.route("/settings/list/add", methods=["POST"])
@login_required
def add_item():
    form = request.form
    error = pages.add_item(get_db(), g.business["id"], form.get("name", ""), form.get("description", ""),
                           form.get("category", ""), form.get("price", ""))
    return back_to("list", error, "Item added.")


@dashboard.route("/settings/list/<int:item_id>", methods=["POST"])
@login_required
def edit_item(item_id):
    if request.form.get("action") == "delete":
        pages.delete_item(get_db(), g.business["id"], item_id)
        return back_to("list", ok="Item deleted.")
    error = pages.update_item(get_db(), g.business["id"], item_id, request.form)
    return back_to("list", error, "Item saved.")


@dashboard.route("/settings/extras/add", methods=["POST"])
@login_required
def add_extra():
    upload = request.files.get("picture")
    file_bytes = upload.read() if upload else b""
    error = pages.add_extra(
        get_db(), current_app.config["DATA_DIR"], g.business["id"], request.form.get("kind", ""),
        request.form.get("title", ""), request.form.get("body", ""), file_bytes,
        with_token=bool(request.form.get("show_with_token")),
    )
    return back_to("extras", error, "Added.")


@dashboard.route("/settings/extras/<int:extra_id>", methods=["POST"])
@login_required
def edit_extra(extra_id):
    if request.form.get("action") == "delete":
        pages.delete_extra(get_db(), current_app.config["DATA_DIR"], g.business["id"], extra_id)
        return back_to("extras", ok="Deleted.")
    pages.update_extra(get_db(), g.business["id"], extra_id, request.form)
    return back_to("extras", ok="Saved.")


@dashboard.route("/settings/lines/add", methods=["POST"])
@login_required
def add_line():
    error = queue.add_line(get_db(), g.business["id"], request.form.get("name", ""),
                           request.form.get("customer_label", ""))
    return back_to("lines", error, "Line added. It's now a column on your board.")


@dashboard.route("/settings/lines/<int:line_id>", methods=["POST"])
@login_required
def edit_line(line_id):
    db = get_db()
    action = request.form.get("action")
    error = None
    if action == "delete":
        error = queue.delete_line(db, g.business["id"], line_id)
    elif action == "left":
        queue.move_line(db, g.business["id"], line_id, -1)
    elif action == "right":
        queue.move_line(db, g.business["id"], line_id, 1)
    elif action == "entry":
        queue.set_entry_line(db, g.business["id"], line_id)
    else:
        error = queue.update_line(db, g.business["id"], line_id, request.form.get("name", ""),
                                  request.form.get("customer_label", ""))
    return back_to("lines", error, "Lines updated.")


@dashboard.route("/settings/business", methods=["POST"])
@login_required
def save_business():
    error = accounts.save_business_details(get_db(), g.business["id"], request.form)
    return back_to("business", error, "Business details saved.")


@dashboard.route("/settings/password", methods=["POST"])
@login_required
def save_password():
    error = accounts.change_password(get_db(), g.business["id"], request.form.get("current", ""),
                                     request.form.get("new", ""))
    return back_to("business", error, "Password changed.")


@dashboard.route("/settings/delete", methods=["POST"])
@login_required
def delete_account():
    if g.business["email"].endswith("@demo.dashq.in"):
        return back_to("business", "The sample accounts can't be deleted.")
    if request.form.get("confirm", "").strip() != g.business["slug"]:
        return back_to("business", "Type your business link name exactly to delete the account.")
    accounts.delete_business(get_db(), g.business["id"])
    shutil.rmtree(pages.folder_for(current_app.config["DATA_DIR"], g.business["id"]), ignore_errors=True)
    session.clear()
    flash("Your account and all its data were deleted.", "ok")
    return redirect(url_for("auth.login"))
