from holdem_together.app import create_app


def test_matches_pages_smoke():
    app = create_app()
    client = app.test_client()

    r = client.get("/matches")
    assert r.status_code == 200
