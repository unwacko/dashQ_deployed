from conftest import sign_up


def test_empty_analytics_then_sample_data(client, db):
    sign_up(client)
    client.post("/app/settings/list/add", data={"name": "Cold coffee"})
    page = client.get("/app/analytics")
    assert b"Fill with sample data" in page.data

    client.post("/app/analytics/sample")
    assert db.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] > 100
    page = client.get("/app/analytics?days=30")
    assert page.status_code == 200
    # Every chart is an inline SVG drawn by matplotlib
    assert page.data.count(b"<svg") >= 8
    assert b"Not enough data yet" not in page.data


def test_demo_businesses(app):
    from db import get_db
    from services.sample_data import make_demo_businesses
    with app.app_context():
        report = make_demo_businesses(get_db())
    assert any("Encave" in line for line in report)
    client = app.test_client()
    assert client.post("/app/demo/encave").status_code == 302
    board = client.get("/app")
    assert b"Ready to collect" in board.data and b"Cold coffee" in board.data
