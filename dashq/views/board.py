"""The live board: one column per line, one card per customer.

Every 3 seconds a timer checks the database. If anything changed (someone joined,
another staff member pressed a button), the board is redrawn.
Cards can be dragged to change their place or moved to another line.
"""
from fastapi import Request
from nicegui import ui

from db import get_db
from services import pages, queue
from views.common import card, eyebrow, require_login, source_chip, time_ago
from views.dashboard_frame import dashboard_frame


@ui.page("/app")
def board_page(request: Request, welcome: str = ""):
    business = require_login()
    if business is None:
        return
    db = get_db()
    business_id = business["id"]
    base_url = str(request.base_url).rstrip("/")
    main = dashboard_frame(business, "Live queue", "board")
    state = {"dragging": None, "snapshot": None}

    # ---------- actions (each one changes the database, then redraws) ----------

    def call(ticket_id):
        ticket = queue.call_ticket(db, business_id, ticket_id)
        announce(ticket)
        redraw()

    def call_next(line_id):
        ticket = queue.call_next(db, business_id, line_id)
        announce(ticket)
        redraw()

    def announce(ticket):
        if ticket is not None:
            ui.notify(f"Calling {ticket['token']}  {ticket['name'] or ''}", icon="campaign",
                      position="bottom-right", color="ink", timeout=4000)

    def done(ticket_id):
        queue.complete_ticket(db, business_id, ticket_id)
        redraw()

    def remove(ticket_id):
        queue.leave_ticket(db, business_id, ticket_id)
        redraw()

    def resend(ticket_id):
        queue.resend_alert(db, business_id, ticket_id)
        redraw()

    def move(ticket_id, line_id, before_id=None):
        queue.move_ticket(db, business_id, ticket_id, line_id, before_id)
        redraw()

    def drop(line_id, before_id=None):
        """A dragged card was dropped on a line (or on a card, to go just above it)."""
        ticket_id = state["dragging"]
        state["dragging"] = None
        if ticket_id is not None and ticket_id != before_id:
            move(ticket_id, line_id, before_id)

    def add_person(line_id, name, phone, note, quantities):
        ticket = queue.create_ticket(db, business, "ip", name=name or "", phone=phone or "",
                                     note=note or "", line_id=line_id)
        form = {f"qty_{item_id}": str(int(box.value or 0)) for item_id, box in quantities.items()}
        chosen = pages.read_choices(db, business_id, form, multi=True)
        if chosen:
            queue.set_items(db, business_id, ticket["id"], chosen)
        redraw()

    # ---------- drawing ----------

    @ui.refreshable
    def stats():
        numbers = queue.today_numbers(db, business)
        lines = queue.board(db, business_id)
        with card("w-full p-0"):
            with ui.grid(columns=4).classes("w-full gap-0"):
                stat("group", "Waiting now", numbers["waiting"], "in line",
                     f"across {len(lines)} line{'s' if len(lines) != 1 else ''}")
                stat("flag", "Joined today", numbers["joined"], "people", "QR, NFC and in person")
                stat("check", "Completed today", numbers["served"], "done", "marked done by your team")
                stat("schedule", "Average wait today", numbers["avg_wait"], "min", "from joining to being called")

    @ui.refreshable
    def lanes():
        lines = queue.board(db, business_id)
        items = pages.get_items(db, business_id, only_available=True)
        with ui.row().classes("w-full items-start no-wrap gap-4 overflow-x-auto pb-2"):
            for line in lines:
                lane(line, lines, items)

    def lane(line, lines, items):
        with card("flex-1 min-w-[280px] p-0 gap-0") \
                .on("dragover.prevent", lambda: None) \
                .on("drop", lambda line_id=line["id"]: drop(line_id)):
            with ui.column().classes("w-full p-3 gap-2"):
                with ui.row().classes("w-full items-center gap-2"):
                    ui.label(line["name"]).classes("font-semibold")
                    ui.badge(str(len(line["tickets"])), color="soft", text_color="ink")
                    if line["is_entry"]:
                        ui.badge("New joins", color="soft", text_color="primary")
                ui.button("Call next", icon="campaign", on_click=lambda line_id=line["id"]: call_next(line_id)) \
                    .props("unelevated no-caps").classes("w-full rounded-lg") \
                    .set_enabled(bool(line["tickets"]))
            with ui.column().classes("w-full px-3 gap-2 min-h-[60px]"):
                for ticket in line["tickets"]:
                    ticket_card(ticket, line, lines)
                if not line["tickets"]:
                    ui.label("Empty. Drag a card here or add someone below.") \
                        .classes("w-full text-center text-sm text-muted border border-dashed border-gray-300 rounded-xl p-4")
            ui.button("Add in person", icon="add",
                      on_click=lambda line_id=line["id"]: add_dialog(line_id, items)) \
                .props("flat no-caps").classes("m-2 text-primary self-start")

    def ticket_card(ticket, line, lines):
        called = ticket["status"] == "called"
        border = "border-l-4 border-l-negative bg-red-50" if called else "bg-white"
        if ticket["minutes"] == 0 and not called:
            border += " ring-2 ring-light"          # just joined
        with ui.card().props("flat bordered draggable").classes(f"w-full p-3 gap-2 rounded-xl cursor-grab {border}") \
                .on("dragstart", lambda ticket_id=ticket["id"]: state.update(dragging=ticket_id)) \
                .on("dragend", lambda: state.update(dragging=None) if state["dragging"] else None) \
                .on("dragover.prevent", lambda: None) \
                .on("drop.stop", lambda line_id=line["id"], before_id=ticket["id"]: drop(line_id, before_id)):
            with ui.row().classes("w-full items-start no-wrap gap-3"):
                ui.label(ticket["token"]).classes("text-2xl font-light")
                with ui.column().classes("flex-1 gap-0 min-w-0"):
                    ui.label(ticket["name"] or "Guest").classes("font-medium truncate")
                    ui.label(time_ago(ticket["minutes"]) + (f" · {ticket['phone']}" if ticket["phone"] else "")) \
                        .classes("text-xs text-muted")
                source_chip(ticket["source"])
            if ticket["order"]:
                with ui.row().classes("gap-1"):
                    for item in ticket["order"]:
                        quantity = f"{item['quantity']}× " if item["quantity"] > 1 else ""
                        ui.label(quantity + item["name"]).classes("text-xs bg-canvas rounded-md px-2 py-0.5")
            if ticket["note"]:
                ui.label(f"“{ticket['note']}”").classes("text-sm text-muted")
            if ticket["alert_stopped"]:
                ui.label("Customer stopped the alert").classes("text-sm text-muted")
            with ui.row().classes("w-full items-center no-wrap gap-1"):
                if called and ticket["alert_stopped"]:
                    ui.button("Resend alert", icon="notifications_active",
                              on_click=lambda ticket_id=ticket["id"]: resend(ticket_id)) \
                        .props("outline dense no-caps size=sm color=negative").classes("rounded-lg px-2")
                elif called:
                    ui.chip("Called", icon="notifications", color="red-1", text_color="negative") \
                        .props("dense square")
                else:
                    ui.button("Call", on_click=lambda ticket_id=ticket["id"]: call(ticket_id)) \
                        .props("outline dense no-caps size=sm").classes("rounded-lg px-3 text-ink")
                ui.button("Done", icon="check", on_click=lambda ticket_id=ticket["id"]: done(ticket_id)) \
                    .props("unelevated dense no-caps size=sm").classes("rounded-lg px-2")
                if len(lines) > 1:
                    options = {other["id"]: (f"In {other['name']}" if other["id"] == line["id"] else f"→ {other['name']}")
                               for other in lines}
                    ui.select(options, value=line["id"],
                              on_change=lambda event, ticket_id=ticket["id"]: move(ticket_id, event.value)
                              if event.value != event.previous_value else None) \
                        .props("dense outlined options-dense").classes("flex-1 min-w-0 text-xs")
                else:
                    ui.space()
                ui.button(icon="delete_outline", on_click=lambda t=ticket: confirm_remove(t)) \
                    .props("flat round dense size=sm").classes("text-muted").tooltip("Remove from line")

    def confirm_remove(ticket):
        with ui.dialog() as dialog, card("p-5 gap-3"):
            ui.label(f"Remove {ticket['token']} from the line?").classes("font-medium")
            with ui.row().classes("w-full justify-end"):
                ui.button("Cancel", on_click=dialog.close).props("flat no-caps")
                ui.button("Remove", color="negative",
                          on_click=lambda: (dialog.close(), remove(ticket["id"]))).props("unelevated no-caps")
        dialog.open()

    def add_dialog(line_id, items):
        """Add someone standing at the counter (or on the phone). The list shows in small."""
        with ui.dialog() as dialog, card("p-5 gap-3 w-[420px] max-w-full"):
            ui.label("Add in person").classes("text-lg font-semibold")
            name = ui.input("Name").props("outlined dense maxlength=60").classes("w-full")
            phone = ui.input("Phone (optional)").props("outlined dense maxlength=20").classes("w-full")
            note = ui.input("Note (optional)").props("outlined dense maxlength=200").classes("w-full")
            quantities = {}
            if items:
                ui.label("Items").classes("text-xs text-muted mt-1")
                with ui.grid(columns=2).classes("w-full gap-x-4 gap-y-1"):
                    for item in items:
                        with ui.row().classes("items-center justify-between no-wrap gap-1"):
                            ui.label(item["name"]).classes("text-xs text-muted truncate")
                            quantities[item["id"]] = ui.number(value=0, min=0, max=20, precision=0) \
                                .props("dense outlined input-class=text-center input-style='font-size:11px'") \
                                .classes("w-14")
            with ui.row().classes("w-full justify-end"):
                ui.button("Cancel", on_click=dialog.close).props("flat no-caps")
                ui.button("Add", on_click=lambda: (dialog.close(), add_person(
                    line_id, name.value, phone.value, note.value, quantities))).props("unelevated no-caps")
        dialog.open()

    def redraw():
        state["snapshot"] = snapshot()
        stats.refresh()
        lanes.refresh()

    def snapshot():
        """A short summary of the board, to tell if anything changed."""
        rows = db.execute(
            "SELECT id, line_id, status, position, alert_stopped, name FROM tickets "
            "WHERE business_id = ? AND status IN ('waiting', 'called') ORDER BY id", (business_id,)).fetchall()
        lines = db.execute("SELECT id, name, position FROM lines WHERE business_id = ?", (business_id,)).fetchall()
        items = db.execute("SELECT COUNT(*) FROM ticket_items WHERE business_id = ?", (business_id,)).fetchone()[0]
        minute = queue.now_text()[:16]       # also redraw once a minute, for "3 min ago"
        return [tuple(row) for row in rows], [tuple(row) for row in lines], items, minute

    def check_for_changes():
        if state["dragging"] is not None:
            return                  # don't redraw under someone's mouse
        if snapshot() != state["snapshot"]:
            redraw()

    # ---------- the page ----------

    with main:
        if welcome:
            welcome_card(business, base_url)
        stats()
        lanes()
    state["snapshot"] = snapshot()
    ui.timer(3, check_for_changes)


def stat(icon, label, value, unit, hint):
    with ui.column().classes("p-4 gap-0 border-r border-gray-100"):
        with ui.row().classes("items-center gap-1 text-muted"):
            ui.icon(icon).classes("text-sm")
            ui.label(label).classes("text-xs")
        with ui.row().classes("items-baseline gap-1"):
            ui.label(str(value)).classes("text-3xl font-light")
            ui.label(unit).classes("text-sm")
        ui.label(hint).classes("text-xs text-muted")


def welcome_card(business, base_url):
    slug = business["slug"]
    with card("w-full p-5"):
        with ui.row().classes("w-full gap-6 no-wrap items-center"):
            with ui.column().classes("flex-1 gap-2"):
                eyebrow("Welcome to dashQ")
                ui.label("Your queue is ready. Set up these three things:").classes("text-xl font-medium")
                for number, text, link in [
                    (1, "Choose what customers fill in (name, phone, list)", "/app/settings?tab=pages"),
                    (2, "Add lines, e.g. Ordered → Preparing → Ready", "/app/settings?tab=lines"),
                    (3, "Print the QR code or write the NFC link to a sticker", f"/qr/{slug}.png?download=1"),
                ]:
                    with ui.link(target=link).classes("w-full no-underline text-ink"):
                        with ui.row().classes("w-full items-center gap-3 p-2 rounded-lg hover:bg-canvas"):
                            ui.label(str(number)).classes("w-6 h-6 rounded-full bg-soft text-primary text-center text-sm")
                            ui.label(text).classes("flex-1")
                            ui.icon("chevron_right").classes("text-muted")
            ui.image(f"/qr/{slug}.png").classes("w-32 h-32 rounded-xl border border-gray-200")
            with ui.column().classes("w-72 gap-1"):
                ui.label("QR link").classes("text-xs text-muted")
                ui.input(value=f"{base_url}/b/{slug}").props("outlined dense readonly").classes("w-full")
                ui.label("NFC sticker link").classes("text-xs text-muted")
                ui.input(value=f"{base_url}/b/{slug}?via=nfc").props("outlined dense readonly").classes("w-full")
