"""Every analytics chart, drawn with matplotlib and seaborn and returned as SVG text.

Rules:
- Make figures with Figure(), never plt.figure(): pyplot keeps global state,
  which is not safe inside a web server.
- Each chart is one short function: take the DataFrame, draw, return to_svg(fig).
"""
import io
import os
import re
import time

import matplotlib
matplotlib.use("Agg")

import seaborn as sns
from matplotlib import font_manager, rcParams
from matplotlib.figure import Figure

from services.analytics import WEEKDAYS

# Use the same Inter font as the web page
FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "fonts")
for font_file in ["Inter-Regular.ttf", "Inter-Medium.ttf"]:
    font_manager.fontManager.addfont(os.path.join(FONT_DIR, font_file))

# One seaborn theme for every chart, with the colours from dashq.css
BLUE = "#1F48FF"
BLUE_LIGHT = "#C2DCFF"
DARK = "#1E1E1E"
AMBER = "#D98A3A"
VIOLET = "#5B4BC4"
MUTED = "#6B7079"
PALETTE = [BLUE, DARK, AMBER, VIOLET, "#6F8BFF", "#9CA3AF"]
SOURCE_COLORS = {"QR code": BLUE, "NFC tap": DARK, "In person": AMBER}

sns.set_theme(style="whitegrid", font="Inter", rc={
    "axes.edgecolor": "#E5E7EA", "grid.color": "#EEF0F2", "grid.linestyle": "--",
    "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
    "font.size": 10, "svg.fonttype": "path",   # letters drawn as shapes, so the font looks right anywhere
})

CACHE = {}
CACHE_SECONDS = 60


def clear_cache():
    CACHE.clear()


def to_svg(fig, name):
    buffer = io.StringIO()
    with matplotlib.rc_context({"svg.hashsalt": name}):   # different ids for each chart on the page
        fig.savefig(buffer, format="svg", transparent=True, bbox_inches="tight", pad_inches=0.05)
    svg = buffer.getvalue()
    svg = svg[svg.index("<svg"):]
    # Remove the fixed width and height, so CSS can size the chart
    return re.sub(r'<svg([^>]*?) width="[^"]*" height="[^"]*"', r"<svg\1", svg, count=1)


def new_axes(width=6.4, height=3.2):
    fig = Figure(figsize=(width, height))
    ax = fig.subplots()
    return fig, ax


# ---------- the charts ----------

def joins_per_day(tickets):
    per_day = tickets.groupby("day").size().reset_index(name="people")
    fig, ax = new_axes(8.6, 3.0)
    ax.fill_between(range(len(per_day)), per_day["people"], color=BLUE, alpha=0.12)
    sns.lineplot(x=range(len(per_day)), y=per_day["people"], ax=ax, color=BLUE, linewidth=2.2, marker="o", markersize=4)
    labels = [day.strftime("%d %b") for day in per_day["day"]]
    step = max(1, len(labels) // 8)
    ax.set_xticks(range(0, len(labels), step), labels[::step])
    ax.set_xlabel("")
    ax.set_ylabel("people")
    return to_svg(fig, "joins_per_day")


def join_sources(tickets):
    counts = tickets["source_name"].value_counts()
    fig, ax = new_axes(3.6, 3.2)
    colors = [SOURCE_COLORS.get(name, MUTED) for name in counts.index]
    wedges, labels, percents = ax.pie(counts, labels=counts.index, colors=colors, autopct="%1.0f%%", startangle=90,
           wedgeprops={"width": 0.42, "edgecolor": "white", "linewidth": 2},
           textprops={"color": MUTED, "fontsize": 10}, pctdistance=0.79)
    for text in percents:
        text.set_color("white")
    ax.axis("equal")
    return to_svg(fig, "join_sources")


def busy_heatmap(tickets):
    table = tickets.pivot_table(index="weekday", columns="hour", values="id", aggfunc="count", fill_value=0)
    table = table.reindex([day for day in WEEKDAYS if day in table.index])
    fig, ax = new_axes(8.6, 3.2)
    sns.heatmap(table, ax=ax, cmap=sns.light_palette(BLUE, as_cmap=True), linewidths=2, linecolor="white",
                annot=True, fmt="d", annot_kws={"fontsize": 8}, cbar=False)
    ax.set_xlabel("hour of day")
    ax.set_ylabel("")
    ax.tick_params(axis="y", rotation=0)
    return to_svg(fig, "busy_heatmap")


def wait_by_hour(tickets):
    waits = tickets.dropna(subset=["wait_min"]).groupby("hour")["wait_min"].mean().reset_index()
    fig, ax = new_axes(5.2, 3.2)
    sns.barplot(data=waits, x="hour", y="wait_min", ax=ax, color=BLUE_LIGHT)
    # Make the slowest hour stand out
    slowest = waits["wait_min"].idxmax()
    ax.patches[slowest].set_facecolor(BLUE)
    ax.bar_label(ax.containers[0], fmt="%.0f", fontsize=8, color=MUTED, padding=2)
    ax.set_xlabel("hour of day")
    ax.set_ylabel("avg wait (min)")
    return to_svg(fig, "wait_by_hour")


def top_items(items):
    totals = items.groupby("name")["quantity"].sum().sort_values(ascending=False).head(10).reset_index()
    fig, ax = new_axes(5.6, 3.4)
    sns.barplot(data=totals, y="name", x="quantity", ax=ax, color=BLUE, orient="h")
    ax.bar_label(ax.containers[0], fontsize=9, color=MUTED, padding=3)
    ax.set_xlabel("times picked")
    ax.set_ylabel("")
    return to_svg(fig, "top_items")


def queue_vs_wait(tickets):
    data = tickets.dropna(subset=["wait_min"])
    fig, ax = new_axes(5.6, 3.4)
    sns.scatterplot(data=data, x="queue_at_join", y="wait_min", hue="source_name", palette=SOURCE_COLORS,
                    ax=ax, s=26, alpha=0.65, edgecolor="none")
    sns.regplot(data=data, x="queue_at_join", y="wait_min", ax=ax, scatter=False, color=DARK,
                line_kws={"linewidth": 1.6, "linestyle": "--"})
    ax.set_xlabel("people already in line when they joined")
    ax.set_ylabel("wait (min)")
    ax.legend(title="", frameon=False, fontsize=9)
    return to_svg(fig, "queue_vs_wait")


def wait_distribution(tickets):
    data = tickets.dropna(subset=["wait_min"])
    fig, ax = new_axes(5.6, 3.4)
    sns.histplot(data=data, x="wait_min", ax=ax, bins=20, kde=True, color=BLUE, edgecolor="white")
    median = data["wait_min"].median()
    ax.axvline(median, color=DARK, linestyle="--", linewidth=1.4)
    ax.text(median, ax.get_ylim()[1] * 0.92, f"  median {median:.0f} min", color=DARK, fontsize=9)
    ax.set_xlabel("minutes from joining to being called")
    ax.set_ylabel("people")
    return to_svg(fig, "wait_distribution")


def outcome_by_weekday(tickets):
    data = tickets[tickets["status"].isin(["done", "left"])].copy()
    data["outcome"] = data["status"].map({"done": "Completed", "left": "Left the line"})
    fig, ax = new_axes(5.6, 3.4)
    sns.histplot(data=data, x="weekday", hue="outcome", multiple="stack", ax=ax, shrink=0.7,
                 palette={"Completed": BLUE, "Left the line": AMBER}, edgecolor="white",
                 discrete=True)
    ax.set_xticks(range(len(WEEKDAYS)))
    ax.set_xlabel("")
    ax.set_ylabel("people")
    legend = ax.get_legend()
    if legend:
        legend.set_title("")
        legend.set_frame_on(False)
    return to_svg(fig, "outcome_by_weekday")


def all_charts(data, business_id, days):
    """Returns {chart name: svg text}, or {} when there is no data yet. Cached for 60 seconds."""
    key = (business_id, days)
    cached = CACHE.get(key)
    if cached and time.time() - cached[0] < CACHE_SECONDS:
        return cached[1]

    tickets = data["tickets"]
    charts = {}
    if not tickets.empty:
        # Weekdays in the right order on every chart
        tickets["weekday"] = tickets["weekday"].astype("category").cat.set_categories(WEEKDAYS)
        charts["joins_per_day"] = joins_per_day(tickets)
        charts["join_sources"] = join_sources(tickets)
        charts["busy_heatmap"] = busy_heatmap(tickets)
        if tickets["wait_min"].notna().sum() >= 3:
            charts["wait_by_hour"] = wait_by_hour(tickets)
            charts["queue_vs_wait"] = queue_vs_wait(tickets)
            charts["wait_distribution"] = wait_distribution(tickets)
        charts["outcome_by_weekday"] = outcome_by_weekday(tickets)
        if not data["items"].empty:
            charts["top_items"] = top_items(data["items"])

    CACHE[key] = (time.time(), charts)
    return charts


def sparkline(values):
    """The small "average wait" line on the home page."""
    fig = Figure(figsize=(4.0, 1.3))
    ax = fig.subplots()
    ax.fill_between(range(len(values)), values, min(values) - 1, color=BLUE, alpha=0.15)
    ax.plot(range(len(values)), values, color=BLUE, linewidth=2.5)
    ax.set_axis_off()
    ax.margins(x=0)
    return to_svg(fig, "sparkline")
