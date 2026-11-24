"""Settings: customer pages, the list/menu, links/pictures/text, the board's lines, and the business."""
import shutil

from fastapi import Request
from nicegui import app, ui

import config
from db import get_db
from services import accounts, pages, queue
from views.common import card, flash_later, require_login, section_title, show_error, show_ok
from views.dashboard_frame import dashboard_frame

TABS = [
    ("pages", "Pages & token", "description"),
    ("list", "List / menu", "list"),
    ("extras", "Links, pictures, text", "link"),
    ("lines", "Lines", "view_kanban"),
    ("business", "Business", "business"),
]
TOKEN_MOMENTS = {"start": "Right away (before page 1)", "details": "After page 1",
                 "list": "After page 2", "end": "At the end"}


@ui.page("/app/settings")
def settings_page(request: Request, tab: str = "pages"):
    business = require_login()
    if business is None:
        return
    if tab not in [name for name, label, icon in TABS]:
        tab = "pages"
    base_url = str(request.base_url).rstrip("/")
    main = dashboard_frame(business, "Settings", "settings")

    @ui.refreshable
    def body():
        current = accounts.get_business(get_db(), business["id"])
        {"pages": pages_tab, "list": list_tab, "extras": extras_tab, "lines": lines_tab,
         "business": business_tab}[tab](current, body.refresh, base_url)

    with main, ui.row().classes("w-full items-start no-wrap gap-4"):
        with card("w-60 p-2 gap-0 shrink-0"):
            for name, label, icon in TABS:
                active = "bg-soft text-primary" if name == tab else "text-ink"
                with ui.link(target=f"/app/settings?tab={name}").classes("w-full no-underline"):
                    with ui.row().classes(f"w-full items-center gap-2 px-3 py-2 rounded-lg hover:bg-canvas {active}"):
                        ui.icon(icon).classes("text-lg")
                        ui.label(label).classes("text-sm")
        with ui.column().classes("flex-1 gap-4 min-w-0"):
            body()


# ---------- pages & token ----------

def pages_tab(business, refresh, base_url):
    db = get_db()
    settings = accounts.get_settings(db, business["id"])
    items = pages.get_items(db, business["id"])
    extras = pages.get_extras(db, business["id"])
    slug = business["slug"]

    with card("w-full p-5 gap-3"):
        with ui.row().classes("w-full items-start"):
            with ui.column().classes("flex-1 gap-0"):
                section_title("What customers see after scanning",
                              "Pages are split up so they're easy on a phone. Switch any page off, "
                              "and choose when the token is handed out.")
            ui.button("Open", icon="open_in_new", on_click=lambda: ui.navigate.to(f"/b/{slug}", new_tab=True)) \
                .props("outline no-caps").classes("rounded-lg")
        with ui.row().classes("w-full no-wrap gap-2"):
            for number, title, sub, on in [
                ("Page 1", "Details", "Name, phone, email", settings["show_details"] == "1"),
                ("Page 2", "List", f"{len(items)} item{'s' if len(items) != 1 else ''}", settings["show_list"] == "1"),
                ("Page 3", "Extras", f"{len(extras)} link/picture/text", settings["show_extras"] == "1"),
            ]:
                with ui.column().classes("flex-1 gap-0 p-3 rounded-xl border border-gray-200 "
                                         + ("bg-white" if on else "bg-canvas opacity-50")):
                    ui.label(number).classes("text-xs text-muted")
                    ui.label(title).classes("font-semibold")
                    ui.label(sub).classes("text-xs text-muted")
            with ui.column().classes("flex-1 gap-0 p-3 rounded-xl bg-primary text-white"):
                ui.label("Token given").classes("text-xs text-white/70")
                ui.label({"start": "Right away", "details": "After page 1", "list": "After page 2",
                          "end": "At the end"}[settings["token_moment"]]).classes("font-semibold")
                ui.label("Live place in line").classes("text-xs text-white/70")

    with card("w-full p-5 gap-3"):
        section_title("Pages")
        welcome = ui.input("Welcome text", value=settings["welcome_text"]).props("outlined maxlength=300").classes("w-full")

        show_details = ui.switch("Page 1 · Details: ask for the customer's details", value=settings["show_details"] == "1")
        choices = {}
        with ui.column().classes("w-full pl-4 border-l-2 border-gray-200 gap-1"):
            for field, label, hint in [("ask_name", "Name", "Shown on your board."),
                                       ("ask_phone", "Phone number", "Only if you need to reach them."),
                                       ("ask_email", "Email", "For receipts or follow-ups.")]:
                with ui.row().classes("w-full items-center"):
                    with ui.column().classes("flex-1 gap-0"):
                        ui.label(label).classes("font-medium")
                        ui.label(hint).classes("text-xs text-muted")
                    choices[field] = ui.toggle({"off": "Off", "optional": "Optional", "required": "Required"},
                                               value=settings[field]).props("no-caps unelevated toggle-color=primary")

        show_list = ui.switch("Page 2 · List: a menu or list of services to pick from", value=settings["show_list"] == "1")
        with ui.row().classes("w-full pl-4 border-l-2 border-gray-200 items-center gap-4"):
            list_title = ui.input("Title on the page", value=settings["list_title"]).props("outlined dense maxlength=80")
            list_multi = ui.switch("Many items with quantities (off = pick just one)", value=settings["list_multi"] == "1")

        show_extras = ui.switch("Page 3 · Links, pictures & text", value=settings["show_extras"] == "1")
        with ui.row().classes("w-full pl-4 border-l-2 border-gray-200"):
            extras_title = ui.input("Title on the page", value=settings["extras_title"]).props("outlined dense maxlength=80")

        with ui.row().classes("w-full items-center"):
            with ui.column().classes("flex-1 gap-0"):
                ui.label("When do they get their token?").classes("font-medium")
                ui.label("They join the line at this moment. Later pages still save to their ticket.") \
                    .classes("text-xs text-muted")
            moment = ui.select(TOKEN_MOMENTS, value=settings["token_moment"]).props("outlined dense").classes("w-60")

        def save():
            form = {"welcome_text": welcome.value or "", "list_title": list_title.value or "",
                    "extras_title": extras_title.value or "", "token_moment": moment.value}
            for field, toggle in choices.items():
                form[field] = toggle.value
            for name, switch in [("show_details", show_details), ("show_list", show_list),
                                 ("show_extras", show_extras), ("list_multi", list_multi)]:
                if switch.value:
                    form[name] = "1"
            error = accounts.save_flow_settings(get_db(), business["id"], form)
            if error:
                show_error(error)
                return
            show_ok("Customer pages saved.")
            refresh()

        ui.button("Save pages", on_click=save).props("unelevated no-caps").classes("self-end rounded-lg")

    with card("w-full p-5 gap-3"):
        section_title("Your links")
        with ui.row().classes("w-full items-center no-wrap gap-5"):
            ui.image(f"/qr/{slug}.png").classes("w-36 h-36 rounded-xl border border-gray-200")
            with ui.column().classes("flex-1 gap-2"):
                ui.input("QR code link", value=f"{base_url}/b/{slug}").props("outlined dense readonly").classes("w-full")
                ui.input("NFC sticker link (write it onto any NTAG sticker with a free NFC app)",
                         value=f"{base_url}/b/{slug}?via=nfc").props("outlined dense readonly").classes("w-full")
                ui.button("Download QR", icon="download",
                          on_click=lambda: ui.download.from_url(f"/qr/{slug}.png?download=1")) \
                    .props("outline no-caps").classes("rounded-lg")


# ---------- list / menu ----------

def list_tab(business, refresh, base_url):
    db = get_db()
    settings = accounts.get_settings(db, business["id"])
    items = pages.get_items(db, business["id"])

    with card("w-full p-5 gap-3"):
        with ui.row().classes("w-full items-start"):
            with ui.column().classes("flex-1 gap-0"):
                section_title("List / menu", "What customers pick on page 2. It shows up on each card on your board.")
            page_chip(settings["show_list"] == "1", "Page 2")

        with ui.row().classes("w-full items-center gap-2"):
            name = ui.input("Item, e.g. Cold coffee").props("outlined dense maxlength=60").classes("flex-[2]")
            category = ui.input("Category, e.g. Drinks").props("outlined dense maxlength=30").classes("flex-1")
            price = ui.input("Price, e.g. ₹90").props("outlined dense maxlength=15").classes("w-28")
            description = ui.input("Short description (optional)").props("outlined dense maxlength=140").classes("flex-[2]")

            def add():
                error = pages.add_item(get_db(), business["id"], name.value or "", description.value or "",
                                       category.value or "", price.value or "")
                if error:
                    show_error(error)
                    return
                show_ok("Item added.")
                refresh()

            ui.button("Add", icon="add", on_click=add).props("unelevated no-caps").classes("rounded-lg")

        if not items:
            empty("No items yet. Add your first one above.")
        for item in items:
            with ui.row().classes("w-full items-center no-wrap gap-2 border-t border-gray-100 pt-2"):
                boxes = {
                    "name": ui.input(value=item["name"]).props("outlined dense maxlength=60").classes("flex-[2]"),
                    "category": ui.input(value=item["category"] or "").props("outlined dense maxlength=30").classes("flex-1"),
                    "price": ui.input(value=item["price"] or "").props("outlined dense maxlength=15").classes("w-24"),
                    "description": ui.input(value=item["description"] or "").props("outlined dense maxlength=140").classes("flex-[2]"),
                }
                available = ui.switch(value=bool(item["available"])).tooltip("Available")

                def save(item_id=item["id"], boxes=boxes, available=available):
                    form = {key: box.value or "" for key, box in boxes.items()}
                    if available.value:
                        form["available"] = "1"
                    error = pages.update_item(get_db(), business["id"], item_id, form)
                    show_error(error) if error else show_ok("Item saved.")

                def delete(item_id=item["id"]):
                    pages.delete_item(get_db(), business["id"], item_id)
                    show_ok("Item deleted.")
                    refresh()

                ui.button("Save", on_click=save).props("outline dense no-caps").classes("rounded-lg px-3")
                ui.button(icon="delete_outline", on_click=delete).props("flat round dense color=negative")


# ---------- links, pictures, text ----------

def extras_tab(business, refresh, base_url):
    db = get_db()
    settings = accounts.get_settings(db, business["id"])
    extras = pages.get_extras(db, business["id"])
    upload = {"bytes": b""}

    with card("w-full p-5 gap-3"):
        with ui.row().classes("w-full items-start"):
            with ui.column().classes("flex-1 gap-0"):
                section_title("Links, pictures & text",
                              "Shown on page 3, and (if you tick it) next to the customer's token.")
            page_chip(settings["show_extras"] == "1", "Page 3")

        with ui.grid(columns=2).classes("w-full gap-3"):
            kind = ui.select({"link": "Link (payment page, UPI, map, Instagram…)",
                              "image": "Picture (menu photo, QR for payment…)",
                              "text": "Text (rules, instructions…)"}, value="link", label="Type").props("outlined dense")
            title = ui.input("Title, e.g. Pay with UPI").props("outlined dense maxlength=80")
            body = ui.textarea("Link or text (links start with https://, http:// or upi://)") \
                .props("outlined dense maxlength=1000 rows=2").classes("col-span-2")

            async def got_file(event):
                upload["bytes"] = await event.file.read()

            ui.upload(label="Picture (only for the picture type)", on_upload=got_file, auto_upload=True,
                      max_file_size=4 * 1024 * 1024, max_files=1) \
                .props("accept='image/jpeg,image/png,image/webp' flat bordered").classes("w-full")
            with_token = ui.switch("Also show with the token (visible while they wait)")

        def add():
            error = pages.add_extra(get_db(), config.DATA_DIR, business["id"], kind.value, title.value or "",
                                    body.value or "", upload["bytes"], with_token=with_token.value)
            if error:
                show_error(error)
                return
            show_ok("Added.")
            refresh()

        ui.button("Add", icon="add", on_click=add).props("unelevated no-caps").classes("self-start rounded-lg")

        if not extras:
            empty("Nothing yet. Add a payment link or a picture above.")
        for extra in extras:
            with ui.row().classes("w-full items-center no-wrap gap-3 border-t border-gray-100 pt-2"):
                if extra["kind"] == "image":
                    ui.image(f"/b/{business['slug']}/img/{extra['filename']}").classes("w-12 h-12 rounded-lg")
                else:
                    ui.chip(extra["kind"].capitalize(), icon="link" if extra["kind"] == "link" else "notes") \
                        .props("dense square outline")
                ui.label(extra["body"] or "").classes("text-sm text-muted truncate w-48")
                title_box = ui.input(value=extra["title"] or "").props("outlined dense maxlength=80").classes("flex-1")
                on_page = ui.switch("Page 3", value=bool(extra["show_on_page"]))
                on_token = ui.switch("With token", value=bool(extra["show_with_token"]))

                def save(extra_id=extra["id"], title_box=title_box, on_page=on_page, on_token=on_token):
                    form = {"title": title_box.value or ""}
                    if on_page.value:
                        form["show_on_page"] = "1"
                    if on_token.value:
                        form["show_with_token"] = "1"
                    pages.update_extra(get_db(), business["id"], extra_id, form)
                    show_ok("Saved.")

                def delete(extra_id=extra["id"]):
                    pages.delete_extra(get_db(), config.DATA_DIR, business["id"], extra_id)
                    show_ok("Deleted.")
                    refresh()

                ui.button("Save", on_click=save).props("outline dense no-caps").classes("rounded-lg px-3")
                ui.button(icon="delete_outline", on_click=delete).props("flat round dense color=negative")


# ---------- lines ----------

def lines_tab(business, refresh, base_url):
    db = get_db()
    lines = queue.get_lines(db, business["id"])

    def run(action, *args):
        error = action(get_db(), business["id"], *args)
        if error:
            show_error(error)
            return
        show_ok("Lines updated.")
        refresh()

    with card("w-full p-5 gap-3"):
        section_title("Lines on your dashboard",
                      "Each line is a column on your board, e.g. Ordering → Preparing → Ready. "
                      "Customers see the “customer message” of the line they're in.")
        for position, line in enumerate(lines):
            with ui.row().classes("w-full items-center no-wrap gap-2 border-t border-gray-100 pt-2"):
                name = ui.input("Line name", value=line["name"]).props("outlined dense maxlength=40").classes("w-48")
                label = ui.input("Customer message", value=line["customer_label"] or "",
                                 placeholder="e.g. Your food is ready. Collect it at the counter.") \
                    .props("outlined dense maxlength=80").classes("flex-1")
                if line["is_entry"]:
                    ui.chip("Joins here", icon="check", color="green-1", text_color="positive").props("dense square")
                else:
                    ui.button("Make entry", on_click=lambda line_id=line["id"]: run(queue.set_entry_line, line_id)) \
                        .props("outline dense no-caps").classes("rounded-lg px-2")
                ui.button(icon="arrow_back", on_click=lambda line_id=line["id"]: run(queue.move_line, line_id, -1)) \
                    .props("flat round dense").set_enabled(position > 0)
                ui.button(icon="arrow_forward", on_click=lambda line_id=line["id"]: run(queue.move_line, line_id, 1)) \
                    .props("flat round dense").set_enabled(position < len(lines) - 1)
                ui.button("Save", on_click=lambda line_id=line["id"], name=name, label=label:
                          run(queue.update_line, line_id, name.value or "", label.value or "")) \
                    .props("outline dense no-caps").classes("rounded-lg px-3")
                ui.button(icon="delete_outline", on_click=lambda line_id=line["id"]: run(queue.delete_line, line_id)) \
                    .props("flat round dense color=negative").set_enabled(len(lines) > 1)

        with ui.row().classes("w-full items-center no-wrap gap-2 pt-2"):
            new_name = ui.input("New line, e.g. Waiting for food").props("outlined dense maxlength=40").classes("w-60")
            new_label = ui.input("Customer message, e.g. We're cooking your order") \
                .props("outlined dense maxlength=80").classes("flex-1")

            def add():
                error = queue.add_line(get_db(), business["id"], new_name.value or "", new_label.value or "")
                if error:
                    show_error(error)
                    return
                show_ok("Line added. It's now a column on your board.")
                refresh()

            ui.button("Add line", icon="add", on_click=add).props("unelevated no-caps").classes("rounded-lg")


# ---------- business ----------

def business_tab(business, refresh, base_url):
    db = get_db()
    settings = accounts.get_settings(db, business["id"])

    with card("w-full p-5 gap-3"):
        section_title("Business details")
        with ui.grid(columns=2).classes("w-full gap-3"):
            name = ui.input("Business name", value=business["name"]).props("outlined dense maxlength=80")
            category = ui.select(accounts.CATEGORIES, label="Type of business",
                                 value=business["category"] if business["category"] in accounts.CATEGORIES else None) \
                .props("outlined dense")
            phone = ui.input("Phone", value=business["phone"] or "").props("outlined dense maxlength=20")
            avg = ui.number("Average minutes per customer (for the wait estimate)",
                            value=int(settings["avg_service_minutes"]), min=1, max=120, precision=0) \
                .props("outlined dense")
            address = ui.input("Address", value=business["address"] or "").props("outlined dense maxlength=200") \
                .classes("col-span-2")
            ui.input("Your link (stays the same if you rename the business, so printed QR codes keep working)",
                     value=f"{base_url}/b/{business['slug']}").props("outlined dense readonly").classes("col-span-2")

        def save():
            form = {"name": name.value or "", "category": category.value or "", "phone": phone.value or "",
                    "address": address.value or "", "avg_service_minutes": str(int(avg.value or 0))}
            error = accounts.save_business_details(get_db(), business["id"], form)
            if error:
                show_error(error)
                return
            show_ok("Business details saved.")

        ui.button("Save details", on_click=save).props("unelevated no-caps").classes("self-end rounded-lg")

    with card("w-full p-5 gap-3"):
        section_title("Password")
        with ui.grid(columns=2).classes("w-full gap-3"):
            current = ui.input("Current password", password=True).props("outlined dense autocomplete=current-password")
            new = ui.input("New password (at least 8 characters)", password=True) \
                .props("outlined dense autocomplete=new-password")

        def change():
            error = accounts.change_password(get_db(), business["id"], current.value or "", new.value or "")
            if error:
                show_error(error)
                return
            current.set_value("")
            new.set_value("")
            show_ok("Password changed.")

        ui.button("Change password", on_click=change).props("outline no-caps").classes("self-end rounded-lg")

    with card("w-full p-5 gap-3 border-red-200"):
        ui.label("Delete account").classes("text-base font-semibold text-negative")
        ui.label("Deletes your business, lines, lists, pictures and every ticket. This can't be undone.") \
            .classes("text-sm text-muted")
        confirm = ui.input(f"Type {business['slug']} to confirm").props("outlined dense autocomplete=off").classes("w-80")

        def delete():
            if business["email"].endswith("@demo.dashq.in"):
                show_error("The sample accounts can't be deleted.")
                return
            if (confirm.value or "").strip() != business["slug"]:
                show_error("Type your business link name exactly to delete the account.")
                return
            accounts.delete_business(get_db(), business["id"])
            shutil.rmtree(pages.folder_for(config.DATA_DIR, business["id"]), ignore_errors=True)
            app.storage.user.pop("business_id", None)
            flash_later("Your account and all its data were deleted.")
            ui.navigate.to("/app/login")

        ui.button("Delete everything", icon="delete", color="negative", on_click=delete) \
            .props("unelevated no-caps").classes("self-start rounded-lg")


def page_chip(is_on, page):
    if is_on:
        ui.chip(f"{page} is on", color="green-1", text_color="positive").props("dense square")
    else:
        ui.chip(f"{page} is off").props("dense square outline")


def empty(text):
    ui.label(text).classes("w-full text-center text-sm text-muted border border-dashed border-gray-300 rounded-xl p-4")
