"""Sign up, log in and the sample-business buttons. Anyone can make an account."""
from nicegui import ui

from db import get_db
from services import accounts
from views.common import base_page, card, log_in, logo, show_error

DEMO_EMAILS = {"encave": "encave@demo.dashq.in", "sociovate": "sociovate@demo.dashq.in"}


def auth_layout():
    """Left: what dashQ does. Right: the form (returned as a column to fill)."""
    base_page("outer")
    with ui.row().classes("w-full min-h-screen items-stretch no-wrap p-4 gap-4"):
        with ui.column().classes("max-md:hidden w-1/2 rounded-3xl bg-ink text-white p-10 justify-between"):
            logo()
            with ui.column().classes("gap-3"):
                ui.label("Queue management for your counter").classes("text-4xl font-medium leading-tight")
                ui.label("Customers join by QR code, NFC sticker or in person. You see everyone on one board.") \
                    .classes("text-white/70 text-lg")
            with ui.column().classes("gap-2"):
                for icon, text in [("qr_code_2", "Scan a QR code to join"), ("nfc", "Tap an NFC sticker to join"),
                                   ("person_add", "Add walk-ins from the dashboard")]:
                    with ui.row().classes("items-center gap-3"):
                        ui.icon(icon).classes("text-light text-xl")
                        ui.label(text).classes("text-white/80")
        right = ui.column().classes("flex-1 items-center justify-center rounded-3xl bg-white p-6")
    return right


@ui.page("/app/login")
def login_page():
    right = auth_layout()
    with right, ui.column().classes("w-full max-w-sm gap-4"):
        ui.label("Log in").classes("text-3xl font-medium")
        ui.label("Use your account, or open a sample business below.").classes("text-muted")
        email = ui.input("Email").props("outlined type=email autocomplete=email").classes("w-full")
        password = ui.input("Password", password=True, password_toggle_button=True) \
            .props("outlined autocomplete=current-password").classes("w-full")

        def submit():
            business, error = accounts.check_login(get_db(), email.value or "", password.value or "")
            if error:
                show_error(error)
                return
            log_in(business["id"])
            ui.navigate.to("/app")

        password.on("keydown.enter", submit)
        ui.button("Log in", on_click=submit).props("unelevated size=lg no-caps").classes("w-full rounded-xl")
        with ui.row().classes("w-full justify-center gap-1 text-sm text-muted"):
            ui.label("New here?")
            ui.link("Sign up", "/app/signup").classes("text-primary")

        ui.separator()
        ui.label("SAMPLE BUSINESSES").classes("text-xs tracking-widest text-muted self-center")
        with ui.row().classes("w-full gap-3 no-wrap"):
            demo_button("encave", "Encave Cafe", "Cafe · menu and orders", "coffee")
            demo_button("sociovate", "Sociovate", "Dental clinic · waiting room", "medical_services")


def demo_button(which, title, sub, icon):
    def open_demo():
        business = accounts.find_by_email(get_db(), DEMO_EMAILS[which])
        if business is None:
            show_error("The sample businesses aren't set up yet. Restart the app to create them.")
            return
        log_in(business["id"])
        ui.navigate.to("/app")

    with card("flex-1 cursor-pointer hover:shadow-md p-3").on("click", open_demo):
        ui.icon(icon).classes("text-primary text-2xl")
        ui.label(title).classes("font-semibold")
        ui.label(sub).classes("text-xs text-muted")


@ui.page("/app/signup")
def signup_page(email: str = ""):
    right = auth_layout()
    with right, ui.column().classes("w-full max-w-sm gap-4"):
        ui.label("Sign up").classes("text-3xl font-medium")
        ui.label("Free while in beta. You get a QR code after signing up.").classes("text-muted")
        name = ui.input("Business name", placeholder="e.g. Encave Cafe").props("outlined maxlength=80").classes("w-full")
        category = ui.select(accounts.CATEGORIES, label="Type of business", value=accounts.CATEGORIES[0]) \
            .props("outlined").classes("w-full")
        email_box = ui.input("Email", value=email).props("outlined type=email autocomplete=email").classes("w-full")
        password = ui.input("Password (at least 8 characters)", password=True, password_toggle_button=True) \
            .props("outlined autocomplete=new-password").classes("w-full")

        def submit():
            business_id, error = accounts.create_business(
                get_db(), name.value or "", email_box.value or "", password.value or "", category.value or "")
            if error:
                show_error(error)
                return
            log_in(business_id)
            ui.navigate.to("/app?welcome=1")

        ui.button("Create account", icon="arrow_forward", on_click=submit) \
            .props("unelevated size=lg no-caps").classes("w-full rounded-xl")
        with ui.row().classes("w-full justify-center gap-1 text-sm text-muted"):
            ui.label("Already have an account?")
            ui.link("Log in", "/app/login").classes("text-primary")
