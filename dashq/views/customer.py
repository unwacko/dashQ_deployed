"""What a customer sees on their phone after scanning the QR code or tapping the NFC sticker.

/b/<slug>                 works out where the customer is up to and sends them there
/b/<slug>/join/<page>     page 1 details, page 2 list, page 3 extras
/b/<slug>/t/<code>        their ticket: token, place in line, live status, alert

Progress is kept in the browser's storage (tied to a signed cookie), so closing
the tab by mistake and opening the link again brings them back to where they were.
"""
from fastapi.responses import RedirectResponse
from nicegui import app, ui

from db import get_db
from services import join_flow, pages, queue
from services.accounts import get_business_by_slug, get_settings
from views.common import base_page, card, flash_later, initials, letters_badge, show_error

# ---------- remembering progress ----------

def get_progress(slug):
    return app.storage.user.get("join", {}).get(slug)


def save_progress(slug, progress):
    everything = dict(app.storage.user.get("join", {}))
    everything[slug] = progress
    app.storage.user["join"] = everything


def forget_progress(slug):
    everything = dict(app.storage.user.get("join", {}))
    everything.pop(slug, None)
    app.storage.user["join"] = everything


def go_to(slug, progress, page_names):
    """Sends the customer to the page they are up to."""
    index = progress.get("page", 0)
    if index < len(page_names):
        return RedirectResponse(f"/b/{slug}/join/{page_names[index]}")
    return RedirectResponse(f"/b/{slug}/t/{progress['code']}")


# ---------- the layout around every customer page ----------

def customer_layout(business):
    base_page()
    outer = ui.column().classes("w-full max-w-md mx-auto min-h-screen px-4 py-5 gap-4")
    with outer:
        with ui.row().classes("items-center gap-3 no-wrap"):
            letters_badge(initials(business["name"]))
            with ui.column().classes("gap-0"):
                ui.label(business["name"]).classes("text-lg font-semibold leading-tight")
                if business["address"]:
                    ui.label(business["address"]).classes("text-sm text-muted")
        body = ui.column().classes("w-full gap-4 flex-1")
        with ui.row().classes("w-full justify-center text-xs text-muted gap-1"):
            ui.label("Made with")
            ui.link("dashQ", "/").classes("text-muted")
    return body


def not_found():
    base_page()
    with ui.column().classes("w-full items-center justify-center min-h-screen gap-2"):
        ui.label("404").classes("text-6xl font-light text-primary")
        ui.label("We can't find that page").classes("text-xl")
        ui.label("The link may be old or mistyped.").classes("text-muted")
        ui.button("Go to the home page", on_click=lambda: ui.navigate.to("/")).props("unelevated no-caps")


def show_extras(business, extras):
    """Links, pictures and text from the business."""
    links = [extra for extra in extras if extra["kind"] == "link"]
    if links:
        with card("w-full p-0 gap-0"):
            for extra in links:
                with ui.link(target=extra["body"], new_tab=True).classes("w-full no-underline text-ink"):
                    with ui.row().classes("w-full items-center px-4 py-3 no-wrap border-b border-gray-100"):
                        ui.icon("link").classes("text-primary bg-soft rounded-lg p-2")
                        ui.label(extra["title"]).classes("flex-1 font-medium")
                        ui.icon("north_east").classes("text-muted")
    for extra in extras:
        if extra["kind"] == "text":
            with card("w-full p-4 gap-1"):
                if extra["title"]:
                    ui.label(extra["title"]).classes("font-semibold")
                ui.label(extra["body"]).classes("text-muted whitespace-pre-line")
    for extra in extras:
        if extra["kind"] == "image":
            ui.image(f"/b/{business['slug']}/img/{extra['filename']}").classes("w-full rounded-2xl")
            if extra["title"]:
                ui.label(extra["title"]).classes("text-sm text-muted")


# ---------- /b/<slug> ----------

@ui.page("/b/{slug}")
def start(slug: str, via: str = "qr"):
    db = get_db()
    business = get_business_by_slug(db, slug)
    if business is None:
        return not_found()
    settings = get_settings(db, business["id"])
    page_names = join_flow.pages_for(db, business, settings)
    progress = get_progress(slug)

    # Coming back after closing the tab: carry on where they were
    if progress:
        if progress.get("code") and join_flow.active_ticket(db, business, progress):
            return go_to(slug, progress, page_names)
        if progress.get("code"):
            old = queue.get_ticket_by_code(db, business["id"], progress["code"])
            # Just served: show the "done" screen with a "Join again" button
            if old is not None and old["status"] == "done" and queue.minutes_since(old["finished_at"]) < 30:
                return RedirectResponse(f"/b/{slug}/t/{old['code']}")
        if not progress.get("code"):
            if progress.get("page", 0) >= len(page_names):
                join_flow.issue_ticket_if_due(db, business, settings, progress, "end")
                save_progress(slug, progress)
            return go_to(slug, progress, page_names)

    progress = join_flow.start(db, business, settings, via)
    save_progress(slug, progress)
    return go_to(slug, progress, page_names)


# ---------- /b/<slug>/join/<page> ----------

@ui.page("/b/{slug}/join/{page}")
def join_page(slug: str, page: str):
    db = get_db()
    business = get_business_by_slug(db, slug)
    if business is None:
        return not_found()
    settings = get_settings(db, business["id"])
    page_names = join_flow.pages_for(db, business, settings)
    progress = get_progress(slug)

    if progress is None or page not in page_names:
        return RedirectResponse(f"/b/{slug}")
    # A ticket that was finished or left: start again
    if progress.get("code") and join_flow.active_ticket(db, business, progress) is None:
        forget_progress(slug)
        return RedirectResponse(f"/b/{slug}")

    ticket = join_flow.active_ticket(db, business, progress)
    index = page_names.index(page)
    progress["page"] = index            # lets the customer go back to earlier pages
    save_progress(slug, progress)
    step, total = index + 1, len(page_names) + 1

    body = customer_layout(business)
    with body:
        # Progress bar: one segment per page, plus the ticket
        with ui.row().classes("w-full gap-1 no-wrap"):
            for number in range(1, total + 1):
                color = "bg-primary" if number <= step else "bg-gray-300"
                ui.element("div").classes(f"h-1.5 flex-1 rounded-full {color}")

        # If the token was already handed out, show it on every page
        if ticket:
            with ui.link(target=f"/b/{slug}/t/{ticket['code']}").classes("w-full no-underline"):
                with ui.row().classes("w-full items-center justify-between bg-ink text-white rounded-2xl px-4 py-3"):
                    with ui.column().classes("gap-0"):
                        ui.label("You're in line · token").classes("text-xs text-white/70")
                        ui.label(ticket["token"]).classes("text-2xl font-medium")
                    ui.label("View status →").classes("text-sm text-white/80")

        answers = {}
        if page == "details":
            details_page(settings, progress, ticket, answers)
        elif page == "list":
            list_page(db, business, settings, progress, answers)
        else:
            ui.label(settings["extras_title"]).classes("text-2xl font-medium")
            show_extras(business, join_flow.shown_extras(db, business, "page"))

        def submit():
            error = None
            if page == "details":
                values = {field: box.value for field, box in answers.items()}
                error = join_flow.read_details(settings, values, progress)
                if error is None and ticket is not None:
                    queue.update_details(db, business["id"], ticket["id"],
                                         progress.get("name"), progress.get("phone"), progress.get("email"))
            elif page == "list":
                chosen = read_list_answers(db, business, settings, answers)
                if not chosen:
                    error = "Please choose at least one option."
                else:
                    progress["items"] = [list(choice) for choice in chosen]
                    if ticket is not None:
                        queue.set_items(db, business["id"], ticket["id"], chosen)
            if error:
                show_error(error)
                return
            join_flow.finish_page(db, business, settings, progress, page, page_names)
            save_progress(slug, progress)
            if progress["page"] < len(page_names):
                ui.navigate.to(f"/b/{slug}/join/{page_names[progress['page']]}")
            else:
                ui.navigate.to(f"/b/{slug}/t/{progress['code']}")

        ui.space()
        gets_token_now = not ticket and (settings["token_moment"] == page or step == total - 1)
        with ui.column().classes("w-full gap-2 sticky bottom-3"):
            ui.button("Get my token" if gets_token_now else "Continue", icon="arrow_forward", on_click=submit) \
                .props("unelevated size=lg no-caps").classes("w-full rounded-xl")
            if index > 0:
                ui.button("Back", on_click=lambda: ui.navigate.to(f"/b/{slug}/join/{page_names[index - 1]}")) \
                    .props("outline size=lg no-caps").classes("w-full rounded-xl bg-white")


def details_page(settings, progress, ticket, answers):
    ui.label(settings["welcome_text"] or "Join the line").classes("text-2xl font-medium")
    ui.label("Add your details so the team knows it's you." if ticket else "Takes a few seconds. No app, no sign-up.") \
        .classes("text-muted")
    with card("w-full p-4 gap-3"):
        for field, label, kind, place in [("name", "Your name", "text", "e.g. Priya"),
                                          ("phone", "Phone number", "tel", "e.g. 98765 43210"),
                                          ("email", "Email", "email", "you@example.com")]:
            choice = settings["ask_" + field]
            if choice == "off":
                continue
            if choice == "optional":
                label += " (optional)"
            answers[field] = ui.input(label, placeholder=place, value=progress.get(field, "")) \
                .props(f"outlined type={kind} maxlength=120").classes("w-full")


def list_page(db, business, settings, progress, answers):
    multi = settings["list_multi"] == "1"
    ui.label(settings["list_title"]).classes("text-2xl font-medium")
    ui.label("Pick as many as you like." if multi else "Pick one.").classes("text-muted")
    chosen = {item_id: quantity for item_id, name, quantity in progress.get("items", [])}
    groups = pages.items_by_category(pages.get_items(db, business["id"], only_available=True))

    if not multi:
        options = {}
        for category, items in groups:
            for item in items:
                options[item["id"]] = item["name"] + (f"  ·  {item['price']}" if item["price"] else "")
        current = next((item_id for item_id in chosen), None)
        with card("w-full p-3"):
            answers["choice"] = ui.radio(options, value=current).classes("w-full")
        return

    for category, items in groups:
        ui.label(category.upper()).classes("text-xs font-semibold tracking-widest text-muted mt-2")
        with card("w-full p-0 gap-0"):
            for item in items:
                with ui.row().classes("w-full items-center px-4 py-3 no-wrap border-b border-gray-100 gap-3"):
                    with ui.column().classes("flex-1 gap-0"):
                        ui.label(item["name"]).classes("font-medium")
                        if item["description"]:
                            ui.label(item["description"]).classes("text-sm text-muted")
                    if item["price"]:
                        ui.label(item["price"]).classes("text-sm text-muted")
                    answers[item["id"]] = quantity_stepper(chosen.get(item["id"], 0))


def quantity_stepper(start):
    """−  n  +  for picking how many."""
    with ui.row().classes("items-center gap-0 no-wrap border border-gray-300 rounded-full"):
        ui.button("−", on_click=lambda: number.set_value(max(0, int(number.value or 0) - 1))) \
            .props("flat round dense no-caps").classes("text-lg")
        number = ui.number(value=start, min=0, max=20, precision=0) \
            .props("borderless dense input-class=text-center").classes("w-10")
        ui.button("+", on_click=lambda: number.set_value(min(20, int(number.value or 0) + 1))) \
            .props("flat round dense no-caps").classes("text-lg")
    return number


def read_list_answers(db, business, settings, answers):
    """Turns the list page into [(item_id, name, quantity)]."""
    form = {}
    if settings["list_multi"] == "1":
        for item_id, box in answers.items():
            form[f"qty_{item_id}"] = str(int(box.value or 0))
    elif answers["choice"].value is not None:
        form["choice"] = str(answers["choice"].value)
    return pages.read_choices(db, business["id"], form, settings["list_multi"] == "1")


# ---------- /b/<slug>/t/<code>: the ticket ----------

@ui.page("/b/{slug}/t/{code}")
def ticket_page(slug: str, code: str):
    db = get_db()
    business = get_business_by_slug(db, slug)
    ticket = queue.get_ticket_by_code(db, business["id"], code) if business else None
    if ticket is None:
        return not_found()
    settings = get_settings(db, business["id"])
    page_names = join_flow.pages_for(db, business, settings)
    progress = get_progress(slug) or {}
    pages_left = progress.get("code") == code and progress.get("page", 0) < len(page_names)
    was_active = ticket["status"] in queue.ACTIVE

    body = customer_layout(business)
    # The alarm: a WAV file made by Python (services/sound.py). Phones only play sound after a tap.
    alarm = ui.audio("/alert.wav", controls=False, autoplay=False).classes("hidden")
    alert = {"on": False, "flash": False}

    @ui.refreshable
    def status_section():
        row = queue.get_ticket_by_code(db, business["id"], code)
        status = queue.customer_status(db, business, row)
        alert["on"] = status["alert_on"]
        show_status(business, row, status, stop_alert)

    def stop_alert():
        row = queue.get_ticket_by_code(db, business["id"], code)
        queue.stop_alert(db, business["id"], row["id"])
        alarm.pause()
        set_flash(False)
        refresh()

    last_seen = {"snapshot": None}

    def refresh():
        """Runs every 3 seconds. Only redraws when something changed."""
        row = queue.get_ticket_by_code(db, business["id"], code)
        status = queue.customer_status(db, business, row)
        snapshot = (row["status"], row["alert_stopped"], status["ahead"], status["label"], status["line"])
        if snapshot == last_seen["snapshot"]:
            return
        alert_was_on = alert["on"]
        last_seen["snapshot"] = snapshot
        # The visit just ended (done, or removed by staff): reload to show the "done" page
        if was_active and row["status"] not in queue.ACTIVE:
            ui.navigate.reload()
            return
        status_section.refresh()
        if alert["on"] and not alert_was_on:
            alarm.play()
        if not alert["on"]:
            set_flash(False)

    def set_flash(red):
        alert["flash"] = red
        if red:
            ui.query("body").classes(add="bg-red-600", remove="bg-canvas bg-red-100")
        else:
            ui.query("body").classes(add="bg-canvas", remove="bg-red-600 bg-red-100")

    def flash_tick():
        """Flashes the screen red while it's their turn."""
        if not alert["on"]:
            return
        if alert["flash"]:
            ui.query("body").classes(add="bg-red-100", remove="bg-red-600 bg-canvas")
        else:
            ui.query("body").classes(add="bg-red-600", remove="bg-red-100 bg-canvas")
        alert["flash"] = not alert["flash"]

    def beep_tick():
        """Keeps beeping every 6 seconds while it's their turn."""
        if alert["on"]:
            alarm.play()

    with body:
        with ui.column().classes("w-full gap-4"):
            status_section()
        last_seen["snapshot"] = None
        if was_active:
            ui.timer(3, refresh)
            ui.timer(0.6, flash_tick)
            ui.timer(6, beep_tick)

            def sound_on():
                alarm.play()            # this first tap is what lets the phone play sound later
                sound_button.set_text("Sound alerts are on")
                sound_button.props("icon=volume_up color=positive")

            sound_button = ui.button("Tap to turn on sound alerts", icon="volume_up", on_click=sound_on) \
                .props("outline no-caps").classes("w-full rounded-xl bg-white")

            if pages_left:
                ui.button("Finish your order", icon="arrow_forward", on_click=lambda: ui.navigate.to(f"/b/{slug}")) \
                    .props("unelevated size=lg no-caps").classes("w-full rounded-xl")

            items = queue.get_items(db, business["id"], ticket["id"])
            if items:
                with card("w-full p-0 gap-0"):
                    ui.label("Your order").classes("font-semibold px-4 pt-3 pb-2")
                    for item in items:
                        with ui.row().classes("w-full justify-between px-4 py-2 border-t border-gray-100"):
                            ui.label(item["name"])
                            ui.label(f"× {item['quantity']}").classes("text-muted")

            extras = join_flow.shown_extras(db, business, "token")
            if extras:
                show_extras(business, extras)

            ui.space()

            with ui.dialog() as confirm, card("p-5 gap-3"):
                ui.label("Leave the line? You'll lose your place.").classes("font-medium")
                with ui.row().classes("justify-end w-full"):
                    ui.button("Stay", on_click=confirm.close).props("flat no-caps")
                    ui.button("Leave", on_click=lambda: leave(slug, code), color="negative").props("unelevated no-caps")
            ui.button("Leave the line", on_click=confirm.open).props("outline no-caps size=lg") \
                .classes("w-full rounded-xl bg-white text-ink")
    refresh()


def show_status(business, ticket, status, stop_alert):
    slug = business["slug"]
    if ticket["status"] == "called":
        color = "bg-negative" if status["alert_on"] else "bg-ink"
        with ui.column().classes(f"w-full items-center text-center text-white rounded-2xl p-6 gap-1 {color}"):
            ui.label(f"TOKEN {status['token']}").classes("text-xs tracking-widest text-white/80")
            ui.label("It's your turn").classes("text-4xl font-medium")
            ui.label("Please come to the counter" + (f" · {status['line']}" if status["line"] else "") + ".") \
                .classes("text-white/90")
            if status["alert_on"]:
                ui.button("Stop alert", on_click=stop_alert) \
                    .props("unelevated no-caps size=lg color=white text-color=negative").classes("mt-3 rounded-xl px-8")
            else:
                ui.label("Alert stopped.").classes("text-sm text-white/80 mt-2")

    elif ticket["status"] == "done":
        with card("w-full items-center text-center p-8 gap-2"):
            ui.icon("check_circle", color="positive").classes("text-6xl")
            ui.label("Done. Thank you.").classes("text-2xl font-medium")
            ui.label(f"Token {status['token']} at {business['name']}.").classes("text-muted")
            ui.button("Join again", on_click=lambda: again(slug)).props("outline no-caps").classes("mt-3 rounded-xl")

    elif ticket["status"] == "left":
        with card("w-full items-center text-center p-8 gap-2"):
            ui.label("You're no longer in the line").classes("text-2xl font-medium")
            ui.button("Join again", on_click=lambda: again(slug)).props("unelevated no-caps").classes("mt-3 rounded-xl")

    else:
        with card("w-full p-0 gap-0"):
            with ui.column().classes("w-full items-center p-6 gap-1"):
                ui.label("YOUR TOKEN").classes("text-xs tracking-widest text-muted")
                ui.label(status["token"]).classes("text-7xl font-light tracking-tight")
                ui.chip(status["label"], color="soft", text_color="primary").props("dense")
            with ui.row().classes("w-full no-wrap border-t border-gray-100"):
                with ui.column().classes("flex-1 p-4 gap-0 border-r border-gray-100"):
                    ui.label("Ahead of you").classes("text-xs text-muted")
                    ui.label(f"{status['ahead']} {'person' if status['ahead'] == 1 else 'people'}").classes("text-2xl")
                with ui.column().classes("flex-1 p-4 gap-0"):
                    ui.label("About").classes("text-xs text-muted")
                    ui.label(f"{status['wait']} min").classes("text-2xl")
            closeness = 1.0 if status["ahead"] == 0 else 1 / (status["ahead"] + 1)
            with ui.column().classes("w-full px-4 pb-4 gap-1"):
                with ui.row().classes("w-full justify-between text-xs text-muted"):
                    ui.label("How close you are")
                    ui.label("You're next" if status["ahead"] == 0 else f"{status['ahead']} to go")
                ui.linear_progress(value=max(closeness, 0.06), show_value=False, color="primary") \
                    .props("rounded size=8px")
        ui.label("Keep this page open. It will make a sound and turn red when it's your turn.") \
            .classes("text-sm text-muted text-center w-full")


def leave(slug, code):
    db = get_db()
    business = get_business_by_slug(db, slug)
    ticket = queue.get_ticket_by_code(db, business["id"], code)
    if ticket is not None:
        queue.leave_ticket(db, business["id"], ticket["id"])
    forget_progress(slug)
    flash_later("You left the line. Scan again any time to rejoin.")
    ui.navigate.to(f"/b/{slug}")


def again(slug):
    forget_progress(slug)
    ui.navigate.to(f"/b/{slug}")
