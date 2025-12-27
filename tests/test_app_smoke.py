from holdem_together.app import create_app


def test_app_smoke():
    app = create_app()
    client = app.test_client()
    r = client.get("/")
    assert r.status_code == 200
