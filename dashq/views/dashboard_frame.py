"""The frame around every dashboard page: the top bar with the big buttons, and the menu."""
from nicegui import ui

from views.common import base_page, initials, letters_badge, log_out, logo


def dashboard_frame(business, page_name, active):
    """Draws the top bar and returns the column the page fills in."""
    base_page("outer")
    ui.page_title(f"{page_name} · {business['name']}")
    with ui.column().classes("w-full min-h-screen p-3 md:p-4"):
        frame = ui.column().classes("w-full flex-1 rounded-3xl bg-canvas p-4 md:p-5 gap-4")
    with frame:
        with ui.row().classes("w-full items-center no-wrap gap-3"):
            logo("/app", 36)
            ui.label("/").classes("text-muted")
            ui.label(business["name"]).classes("font-semibold truncate")
            ui.label(f"· {page_name}").classes("text-muted max-md:hidden")
            ui.space()
            with ui.row().classes("items-center gap-2 no-wrap"):
                with ui.row().classes("items-center gap-1 px-3 py-1 rounded-full bg-white border border-gray-200"):
                    ui.icon("circle", color="positive").classes("text-[8px]")
                    ui.label("Live").classes("text-xs text-muted")
                ui.button("Customer view", icon="visibility",
                          on_click=lambda: ui.navigate.to(f"/b/{business['slug']}", new_tab=True)) \
                    .props("outline no-caps").classes("bg-white text-ink rounded-xl max-md:hidden")
                big_button("view_kanban", "Live queue", "/app", active == "board")
                big_button("bar_chart", "Analytics", "/app/analytics", active == "analytics")
                big_button("settings", "Settings", "/app/settings", active == "settings")
                with ui.button().props("flat no-caps").classes("rounded-xl"):
                    letters_badge(initials(business["name"]), "bg-soft text-primary", "w-9 h-9 text-sm")
                    ui.icon("expand_more").classes("text-muted")
                    with ui.menu().classes("rounded-xl"):
                        with ui.column().classes("px-4 py-3 gap-0"):
                            ui.label(business["name"]).classes("font-semibold")
                            ui.label(business["email"]).classes("text-sm text-muted")
                        ui.separator()
                        ui.menu_item("Business settings", on_click=lambda: ui.navigate.to("/app/settings?tab=business"))
                        ui.menu_item("Download QR code",
                                     on_click=lambda: ui.download.from_url(f"/qr/{business['slug']}.png?download=1"))
                        ui.separator()
                        ui.menu_item("Log out", on_click=log_out)
        main = ui.column().classes("w-full gap-4")
    return main


def big_button(icon, tooltip, link, is_active):
    button = ui.button(icon=icon, on_click=lambda: ui.navigate.to(link)) \
        .props("unelevated size=md").classes("rounded-xl w-11 h-11")
    if is_active:
        button.props("color=primary")
    else:
        button.props("color=white text-color=ink").classes("border border-gray-200")
    button.tooltip(tooltip)
