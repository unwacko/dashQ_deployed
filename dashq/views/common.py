"""Pieces every page uses: colours, the logo, the logged-in business, small badges.

Styling is done with NiceGUI's Python methods:
  .classes("...")  Tailwind utility classes, e.g. "text-xl font-bold"
  .props("...")    Quasar options, e.g. "outlined dense"
"""
from nicegui import app, ui

from db import get_db
from services import accounts

# Brand colours. After this, "primary", "ink", "light" etc. work as colour names:
# ui.button(color="primary"), .classes("bg-light text-ink")
app.colors(
    primary="#1F48FF",      # dark blue
    ink="#1E1E1E",          # dark grey
    light="#C2DCFF",        # light blue
    soft="#EEF4FF",         # very light blue
    outer="#E6E7EA",        # grey around the dashboard frame
    canvas="#F4F5F6",       # inside the frame
    muted="#6B7079",
    positive="#15803D",
    negative="#DC2626",
    warning="#B45309",
)

SOURCES = {
    "qr": ("QR", "qr_code_2", "primary"),
    "nfc": ("NFC", "nfc", "ink"),
    "ip": ("IP", "person", "warning"),
}


def base_page(background="canvas"):
    """Called first on every page: page background, and any message saved before moving here."""
    ui.query("body").classes(f"bg-{background} text-ink antialiased")
    ui.query(".nicegui-content").classes("p-0 gap-0")
    message = app.storage.user.pop("flash", None)
    if message:
        ui.notify(message, type="positive", position="top")


def flash_later(message):
    """A message to show on the next page (ui.notify would be lost when the page changes)."""
    app.storage.user["flash"] = message


def logo(link="/", height=40):
    """The dashQ logo (a drawing that is 2.2 times wider than it is tall)."""
    with ui.link(target=link).classes("no-underline"):
        ui.image("/static/img/logo.svg").props("fit=contain no-spinner") \
            .style(f"height: {height}px; width: {round(height * 2.2)}px")


def source_chip(source):
    label, icon, color = SOURCES.get(source, SOURCES["qr"])
    ui.chip(label, icon=icon, color=color).props("outline dense square size=sm").classes("text-xs")


def initials(name):
    words = [word for word in name.split() if word]
    return "".join(word[0] for word in words[:2]).upper() or "?"


def letters_badge(letters, colors="bg-primary text-white", size="w-11 h-11 text-base"):
    """A rounded square with initials in it, e.g. EC for Encave Cafe."""
    ui.label(letters).classes(f"{colors} {size} rounded-xl flex items-center justify-center font-semibold shrink-0")


def card(classes=""):
    """A white rounded card with a thin border."""
    return ui.card().props("flat bordered").classes(f"rounded-2xl bg-white {classes}")


def section_title(text, sub=""):
    ui.label(text).classes("text-base font-semibold")
    if sub:
        ui.label(sub).classes("text-sm text-muted")


def eyebrow(text, color="text-primary"):
    ui.label(text.upper()).classes(f"text-xs font-semibold tracking-widest {color}")


def show_error(message):
    if message:
        ui.notify(message, type="negative", position="top")


def show_ok(message):
    ui.notify(message, type="positive", position="top")


# ---------- the logged-in business ----------

def current_business():
    """The logged-in business, or None. The id is kept in the browser's storage (a signed cookie)."""
    business_id = app.storage.user.get("business_id")
    if business_id is None:
        return None
    business = accounts.get_business(get_db(), business_id)
    if business is None:
        app.storage.user.pop("business_id", None)
    return business


def require_login():
    """Use at the top of a dashboard page. Returns the business, or sends you to log in."""
    business = current_business()
    if business is None:
        ui.navigate.to("/app/login")
    return business


def log_in(business_id):
    app.storage.user.clear()
    app.storage.user["business_id"] = business_id


def log_out():
    app.storage.user.pop("business_id", None)
    ui.navigate.to("/")


def time_ago(minutes):
    if minutes == 0:
        return "just now"
    if minutes < 60:
        return f"{minutes} min ago"
    return f"{minutes // 60} h {minutes % 60} min ago"
