from conftest import make_business
from services import analytics, charts, pages
from services.sample_data import make_demo_businesses, seed_history


def test_empty_analytics_then_sample_data(db):
    business = make_business(db)
    pages.add_item(db, business["id"], "Cold coffee")
    assert analytics.summary(analytics.load(db, business, 30))["total"] == 0

    seed_history(db, business["id"])
    data = analytics.load(db, business, 30)
    assert analytics.summary(data)["total"] > 100
    pictures = charts.all_charts(data, business["id"], 30)
    assert len(pictures) == 8 and all(svg.startswith("<svg") for svg in pictures.values())


def test_demo_businesses(db):
    report = make_demo_businesses(db)
    assert any("Encave" in line for line in report)
    assert any(item["name"] == "Cold coffee" for item in pages.get_items(db, 1))
