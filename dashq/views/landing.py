"""The public home page at /."""
import base64

from nicegui import ui

from services.charts import sparkline
from views.common import base_page, card, eyebrow, letters_badge, logo, source_chip

WAIT_SPARKLINE = base64.b64encode(sparkline([7.6, 7.1, 7.3, 6.5, 6.4, 6.0, 5.8, 5.6]).encode()).decode()


@ui.page("/")
def home():
    base_page("white")
    ui.page_title("dashQ · Queues without an app")
    with ui.column().classes("w-full gap-0 items-center"):
        hero()
        features()
        what_you_get()
        setup_steps()
        customers()
        coming_soon()
        call_to_action()
        footer()


def wrap():
    """The centred page width used by every section."""
    return ui.column().classes("w-full max-w-6xl px-5 md:px-8 gap-6")


def hero():
    with ui.column().classes("w-full items-center bg-gradient-to-b from-soft to-white pb-16"):
        with wrap():
            with ui.row().classes("w-full items-center py-5"):
                logo()
                ui.space()
                with ui.row().classes("max-md:hidden gap-6 text-sm"):
                    for text, target in [("How it works", "#how"), ("Features", "#features"),
                                         ("Customers", "#customers"), ("Coming soon", "#coming")]:
                        ui.link(text, target).classes("text-ink no-underline hover:text-primary")
                ui.space()
                ui.button("Log in", on_click=lambda: ui.navigate.to("/app/login")) \
                    .props("outline no-caps").classes("rounded-xl bg-white text-ink")
                ui.button("Sign up", on_click=lambda: ui.navigate.to("/app/signup")).props("unelevated no-caps") \
                    .classes("rounded-xl")

            with ui.row().classes("w-full items-center gap-10 pt-10 no-wrap max-md:flex-wrap"):
                with ui.column().classes("flex-1 gap-6 min-w-[300px]"):
                    ui.label("Run your queue from a laptop. No app needed.") \
                        .classes("text-5xl md:text-6xl font-medium leading-tight tracking-tight")
                    ui.label("Customers join by QR code, NFC sticker or at the counter. They can pick from your "
                             "menu, see their place in line, and get an alert on their phone when it's their turn.") \
                        .classes("text-lg text-muted")
                    with ui.row().classes("w-full max-w-md items-center no-wrap gap-2 bg-white rounded-2xl p-2 "
                                          "border border-gray-200"):
                        email = ui.input(placeholder="Your business email").props("borderless dense").classes("flex-1 px-2")
                        ui.button("Get started", icon="north_east",
                                  on_click=lambda: ui.navigate.to(f"/app/signup?email={email.value or ''}")) \
                            .props("unelevated no-caps").classes("rounded-xl")
                    with ui.row().classes("items-center gap-6 pt-4"):
                        ui.label("STARTING WITH").classes("text-xs tracking-widest text-muted")
                        for letter, name, color in [("E", "Encave", "bg-[#8B5E3C]"), ("S", "Sociovate", "bg-ink")]:
                            with ui.row().classes("items-center gap-2"):
                                ui.label(letter).classes(f"{color} text-white text-xs rounded-md w-6 h-6 text-center leading-6")
                                ui.label(name).classes("text-xl font-semibold")
                hero_picture()


def hero_picture():
    """A small picture of the product, made from the same parts as the real board."""
    with ui.column().classes("flex-1 min-w-[300px] relative"):
        with card("w-80 p-4 gap-2 shadow-lg"):
            with ui.row().classes("w-full items-center"):
                ui.label("Ordered").classes("font-semibold")
                ui.badge("3", color="soft", text_color="ink")
            for token, name, when, source, items, called in [
                ("014", "Tanvi", "just now", "qr", ["Cold coffee", "Veg sandwich"], False),
                ("013", "Omkar", "3 min ago", "nfc", ["Cheese maggi"], False),
                ("012", "Riya", "6 min ago", "ip", [], True),
            ]:
                style = "border-l-4 border-l-negative bg-red-50" if called else "bg-white"
                if when == "just now":
                    style += " ring-2 ring-light"
                with ui.card().props("flat bordered").classes(f"w-full p-3 gap-1 rounded-xl {style}"):
                    with ui.row().classes("w-full items-center no-wrap gap-3"):
                        ui.label(token).classes("text-2xl font-light")
                        with ui.column().classes("flex-1 gap-0"):
                            ui.label(name).classes("font-medium")
                            ui.label(when).classes("text-xs text-muted")
                        source_chip(source)
                    if items:
                        with ui.row().classes("gap-1"):
                            for item in items:
                                ui.label(item).classes("text-xs bg-canvas rounded-md px-2 py-0.5")
        with ui.column().classes("absolute right-0 top-10 w-56 bg-primary text-white rounded-3xl p-5 gap-1 shadow-xl "
                                 "max-md:hidden"):
            ui.label("Encave Cafe · your token").classes("text-xs text-white/75")
            ui.label("014").classes("text-6xl font-light")
            with ui.row().classes("w-full justify-between text-xs text-white/85"):
                ui.label("2 ahead of you")
                ui.label("~8 min")
            ui.linear_progress(value=0.35, show_value=False, color="white").props("rounded track-color=blue-9")
        with ui.row().classes("absolute right-4 -bottom-6 items-center gap-3 bg-ink text-white rounded-2xl px-4 py-3 "
                              "shadow-xl max-md:hidden"):
            ui.icon("circle", color="negative").classes("animate-pulse")
            with ui.column().classes("gap-0"):
                ui.label("012, it's your turn").classes("font-semibold")
                ui.label("Sound, vibration, red screen").classes("text-xs text-white/70")


def features():
    with wrap().classes("-mt-6"):
        ui.link_target("features")
        with card("w-full p-8 gap-6 shadow-sm"):
            with ui.row().classes("w-full items-end gap-6"):
                with ui.column().classes("flex-1 gap-2"):
                    eyebrow("Triple servicing")
                    ui.label("Three ways to join").classes("text-4xl font-medium")
                ui.label("All three end up on the same board, marked QR, NFC or IP, so you can see how each "
                         "person joined.").classes("flex-1 text-muted")
            with ui.grid(columns=3).classes("w-full gap-8 max-md:grid-cols-1"):
                for icon, title, text in [
                    ("qr_code_2", "Scan a QR code", "Put it on a table, door or bill. It opens in the phone's browser."),
                    ("nfc", "Tap an NFC sticker", "Put it on the counter. The customer taps their phone on it to join."),
                    ("person_add", "Join in person", "Staff add walk-ins and phone calls from the dashboard."),
                ]:
                    with ui.column().classes("gap-2"):
                        ui.icon(icon).classes("text-primary bg-soft rounded-xl p-2 text-2xl")
                        ui.label(title).classes("font-semibold")
                        ui.label(text).classes("text-sm text-muted")


def what_you_get():
    with wrap().classes("py-20"):
        ui.link_target("how")
        with ui.column().classes("w-full items-center gap-2"):
            eyebrow("Features")
            ui.label("What you get").classes("text-4xl font-medium")
        with ui.grid(columns=3).classes("w-full gap-4 max-md:grid-cols-1"):
            with card("p-6 gap-4 bg-canvas"):
                ui.label("3 pages").classes("text-5xl font-light text-primary")
                ui.label("Details → list → links and text.").classes("text-lg")
                ui.label("Turn each page on or off.").classes("text-muted")
            with card("p-6 gap-4 bg-canvas"):
                ui.label("Several lines on one board.").classes("text-lg")
                ui.label("For example Ordered → Preparing → Ready. Customers see which line they are in.") \
                    .classes("text-muted")
                with ui.row().classes("items-center gap-2"):
                    for icon, color in [("qr_code_2", "bg-primary"), ("view_kanban", "bg-ink"), ("notifications", "bg-negative")]:
                        ui.icon(icon).classes(f"{color} text-white rounded-full p-3 text-xl")
                        if icon != "notifications":
                            ui.element("div").classes("w-6 border-t-2 border-dashed border-gray-300")
            with card("p-6 gap-3 bg-canvas"):
                ui.label("Analytics").classes("text-lg")
                ui.label("Wait times, busiest hours and most picked items, from your own data.").classes("text-muted")
                with ui.row().classes("w-full justify-between text-xs text-muted"):
                    ui.label("Average wait")
                    ui.label("sample data")
                with ui.row().classes("items-center gap-2"):
                    ui.label("6.2 min").classes("text-3xl font-light")
                    ui.chip("▼ 18%", color="green-1", text_color="positive").props("dense square")
                ui.image(f"data:image/svg+xml;base64,{WAIT_SPARKLINE}").props("fit=contain no-spinner").classes("w-full")


def setup_steps():
    with ui.column().classes("w-full items-center bg-ink text-white py-20"):
        with wrap():
            eyebrow("Setup", "text-light")
            ui.label("Three steps to start").classes("text-4xl font-medium")
            with ui.grid(columns=3).classes("w-full gap-4 max-md:grid-cols-1"):
                for number, title, text in [
                    (1, "Make your account", "Sign up with your email. You get a join link and a QR code."),
                    (2, "Set up your pages", "Choose which details to ask for, add a list of items or services, "
                                             "and add links or text. Or turn them off and only give tokens."),
                    (3, "Put up the QR code", "Print the QR code or write the link to an NFC sticker. "
                                              "Run the line from the dashboard."),
                ]:
                    with ui.column().classes("rounded-2xl bg-white/5 border border-white/10 p-6 gap-2"):
                        ui.label(str(number)).classes("w-8 h-8 rounded-full bg-primary text-center leading-8")
                        ui.label(title).classes("font-semibold text-lg")
                        ui.label(text).classes("text-white/70 text-sm")


def customers():
    with wrap().classes("py-20"):
        ui.link_target("customers")
        with ui.column().classes("w-full items-center gap-2 text-center"):
            eyebrow("First customers")
            ui.label("Who is using dashQ").classes("text-4xl font-medium")
            ui.label("Both are setting up dashQ now. These are the features they plan to use.").classes("text-muted")
        with ui.grid(columns=2).classes("w-full gap-4 max-md:grid-cols-1"):
            customer_card("EN", "Encave", "Cafe inside MIT-WPU, Pune", "bg-white",
                          "The counter gets crowded between lectures. Students will book and order from their "
                          "phone and get an alert when the food is ready.",
                          ["Booking from a QR code on each table", "Menu on the phone, ordered while joining",
                           "“Preparing” and “Ready to collect” shown to customers",
                           "Each customer's items shown on the dashboard"])
            customer_card("SO", "Sociovate", "Marketing agency for dental clinics", "bg-primary text-white",
                          "Patients see their place in line and an estimated wait. The front desk calls the next "
                          "patient from the dashboard.",
                          ["Queue management for each partner clinic", "Estimated wait times",
                           "Waiting room → With the doctor, on one board", "Walk-ins and phone bookings added by staff"])


def customer_card(letters, name, sub, colors, text, features_list):
    with ui.card().props("flat bordered").classes(f"rounded-2xl p-7 gap-4 {colors}"):
        with ui.row().classes("items-center gap-3"):
            letters_badge(letters, "bg-soft text-primary")
            with ui.column().classes("gap-0"):
                ui.label(name).classes("text-xl font-semibold")
                ui.label(sub).classes("text-sm opacity-70")
        ui.label(text).classes("opacity-80")
        for feature in features_list:
            with ui.row().classes("items-center gap-2 no-wrap"):
                ui.icon("check_circle").classes("text-lg")
                ui.label(feature)
        ui.label("Not live yet").classes("text-xs opacity-60 uppercase tracking-widest")


def coming_soon():
    with wrap().classes("pb-20"):
        ui.link_target("coming")
        with ui.column().classes("w-full items-center gap-2"):
            eyebrow("Coming soon")
            ui.label("Features coming").classes("text-4xl font-medium")
        with ui.grid(columns=4).classes("w-full gap-4 max-md:grid-cols-2"):
            for icon, title, text in [
                ("sms", "SMS alerts", "A text message when it's the customer's turn."),
                ("call", "Calling", "An automatic phone call when it's their turn."),
                ("tune", "More customisation", "More control over your pages, lines and dashboard."),
                ("storefront", "Features for your business", "Features built for how your business works."),
            ]:
                with card("p-5 gap-2"):
                    ui.icon(icon).classes("text-primary bg-soft rounded-xl p-2 text-2xl")
                    ui.label(title).classes("font-semibold")
                    ui.label(text).classes("text-sm text-muted")


def call_to_action():
    with wrap():
        with ui.row().classes("w-full items-center justify-between gap-6 rounded-3xl bg-ink text-white p-10"):
            with ui.column().classes("gap-2"):
                eyebrow("Start", "text-white/50")
                ui.label("Try dashQ").classes("text-4xl font-medium")
                ui.label("Sign up and set up your first line. It's free while in beta.").classes("text-white/70")
            with ui.row().classes("gap-3"):
                ui.button("Sign up", on_click=lambda: ui.navigate.to("/app/signup")).props("unelevated no-caps size=lg") \
                    .classes("rounded-xl")
                ui.button("See a sample", icon="north_east", on_click=lambda: ui.navigate.to("/app/login")) \
                    .props("outline no-caps size=lg").classes("rounded-xl text-white")


def footer():
    with wrap().classes("py-14"):
        with ui.row().classes("w-full items-start gap-10"):
            with ui.column().classes("flex-1 gap-2"):
                logo()
                ui.label("Queues, lists and turn alerts for cafes, clinics and counters.").classes("text-sm text-muted")
            for title, links in [
                ("Product", [("Features", "#features"), ("How it works", "#how"), ("Coming soon", "#coming")]),
                ("Made for", [("Cafes", "#customers"), ("Clinics", "#customers"), ("Agencies", "#customers")]),
                ("Account", [("Sign up", "/app/signup"), ("Log in", "/app/login")]),
            ]:
                with ui.column().classes("gap-2"):
                    ui.label(title).classes("font-semibold")
                    for text, target in links:
                        ui.link(text, target).classes("text-sm text-muted no-underline hover:text-primary")
        ui.label("© dashQ 2026").classes("w-full text-center text-xs text-muted pt-6 border-t border-gray-100")
