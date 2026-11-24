"""Analytics: 8 charts drawn by matplotlib and seaborn (services/charts.py), shown as pictures."""
import base64

from nicegui import run, ui

from db import get_db
from services import analytics, charts
from services.sample_data import seed_history
from views.common import card, flash_later, require_login, section_title
from views.dashboard_frame import dashboard_frame

CHARTS = [
    ("joins_per_day", "People joining per day", "Line chart · every channel together", 2),
    ("join_sources", "How people join", "Pie chart · QR code, NFC tap, in person", 1),
    ("busy_heatmap", "Busiest times", "Heatmap · people joining by weekday and hour", 2),
    ("wait_by_hour", "Wait time by hour", "Bar chart · the darkest bar is your slowest hour", 1),
    ("top_items", "Most selected from your list", "Bar chart · top 10 items or services", 1),
    ("queue_vs_wait", "Longer line, longer wait?", "Scatter plot · each dot is one customer, dashed line is the trend", 1),
    ("wait_distribution", "How long people wait", "Histogram with a smooth curve · dashed line is the median", 1),
    ("outcome_by_weekday", "Completed vs left the line", "Stacked bars · by weekday", 1),
]


def make_everything(business, days):
    """Runs in a separate thread, so drawing the charts doesn't hold up other users."""
    data = analytics.load(get_db(), business, days)
    return analytics.summary(data), charts.all_charts(data, business["id"], days)


@ui.page("/app/analytics", response_timeout=30)
async def analytics_page(days: int = 30):
    business = require_login()
    if business is None:
        return
    if days not in (7, 30, 90):
        days = 30
    main = dashboard_frame(business, "Analytics", "analytics")

    with main:
        with ui.row().classes("w-full items-center"):
            ui.toggle({7: "Last 7 days", 30: "Last 30 days", 90: "Last 90 days"}, value=days,
                      on_change=lambda event: ui.navigate.to(f"/app/analytics?days={event.value}")) \
                .props("no-caps unelevated toggle-color=primary").classes("bg-white rounded-xl")
            ui.space()
            sample_slot = ui.row()
        spinner = ui.spinner(size="lg").classes("self-center mt-10")

    summary, pictures = await run.io_bound(make_everything, business, days)
    spinner.delete()

    def add_sample():
        seed_history(get_db(), business["id"])
        charts.clear_cache()
        flash_later("Added 30 days of sample history so you can see the charts.")
        ui.navigate.reload()

    with sample_slot:
        if summary["total"] == 0:
            ui.button("Fill with sample data", icon="bolt", on_click=add_sample) \
                .props("outline no-caps").classes("bg-white rounded-xl")

    with main:
        with card("w-full p-0"):
            with ui.grid(columns=4).classes("w-full gap-0"):
                number("group", "People joined", summary["total"], "", f"last {days} days")
                number("schedule", "Average wait", summary["avg_wait"], "min", "joining → being called")
                number("flag", "Busiest hour", summary["busiest_hour"], "", "most people joined then")
                number("list", "Most picked", summary["top_item"], "",
                       f"{summary['completed']}% of people were completed")

        if summary["total"] == 0:
            with card("w-full items-center text-center p-12 gap-1"):
                section_title(f"No customers yet in the last {days} days")
                ui.label("Charts appear as soon as people join. Want a preview? Fill with sample data.") \
                    .classes("text-muted")
            return

        with ui.grid(columns=3).classes("w-full gap-4"):
            for name, title, sub, width in CHARTS:
                with card(f"p-4 gap-2 {'col-span-2' if width == 2 else ''}"):
                    section_title(title, sub)
                    svg = pictures.get(name)
                    if svg:
                        encoded = base64.b64encode(svg.encode()).decode()
                        ui.image(f"data:image/svg+xml;base64,{encoded}").props("fit=contain no-spinner").classes("w-full")
                    else:
                        ui.label("Not enough data yet.").classes("text-muted text-sm p-8 self-center")


def number(icon, label, value, unit, hint):
    with ui.column().classes("p-4 gap-0 border-r border-gray-100"):
        with ui.row().classes("items-center gap-1 text-muted"):
            ui.icon(icon).classes("text-sm")
            ui.label(label).classes("text-xs")
        with ui.row().classes("items-baseline gap-1"):
            ui.label(str(value)).classes("text-3xl font-light truncate")
            if unit:
                ui.label(unit).classes("text-sm")
        ui.label(hint).classes("text-xs text-muted")
