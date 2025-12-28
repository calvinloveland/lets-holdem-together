"""Comprehensive tests for Flask routes."""
from __future__ import annotations

from pathlib import Path

import pytest

from holdem_together.app import create_app
from holdem_together.db import Bot, BotVersion, Match, MatchResult, Rating, User, db


@pytest.fixture
def app(tmp_path: Path):
    """Create test app with temp database."""
    db_path = tmp_path / "test.sqlite3"
    app = create_app({
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path.as_posix()}",
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
    })
    yield app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def app_ctx(app):
    """Create app context."""
    with app.app_context():
        yield


class TestIndexRoute:
    """Tests for the index page."""

    def test_index_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_index_contains_bots(self, client, app):
        with app.app_context():
            # Seed data creates at least one bot
            bots = Bot.query.all()
            assert len(bots) >= 1

        response = client.get("/")
        assert response.status_code == 200
        # Check that page contains bot-related content
        assert b"bot" in response.data.lower() or b"Bot" in response.data


class TestMatchesRoutes:
    """Tests for match listing routes."""

    def test_matches_index_returns_200(self, client):
        response = client.get("/matches")
        assert response.status_code == 200

    def test_matches_index_empty(self, client):
        response = client.get("/matches")
        assert response.status_code == 200


class TestBotNewRoute:
    """Tests for bot creation."""

    def test_bot_new_get(self, client):
        response = client.get("/bots/new")
        assert response.status_code == 200

    def test_bot_new_post_creates_bot(self, client, app):
        response = client.post("/bots/new", data={
            "user_name": "test_user",
            "bot_name": "test_bot",
            "code": "def decide_action(gs): return {'type': 'check'}",
        }, follow_redirects=False)
        
        # Should redirect to bot detail
        assert response.status_code == 302
        
        with app.app_context():
            bot = Bot.query.filter_by(name="test_bot").first()
            assert bot is not None
            assert bot.status == "draft"

    def test_bot_new_post_default_user(self, client, app):
        response = client.post("/bots/new", data={
            "bot_name": "anon_bot",
        }, follow_redirects=False)
        
        assert response.status_code == 302
        
        with app.app_context():
            bot = Bot.query.filter_by(name="anon_bot").first()
            assert bot is not None
            user = User.query.get(bot.user_id)
            assert user.name == "anonymous"


class TestBotDetailRoute:
    """Tests for bot detail page."""

    def test_bot_detail_get(self, client, app):
        with app.app_context():
            bot = Bot.query.first()
            bot_id = bot.id
        
        response = client.get(f"/bots/{bot_id}")
        assert response.status_code == 200

    def test_bot_detail_404(self, client):
        response = client.get("/bots/99999")
        assert response.status_code == 404

    def test_bot_save_action(self, client, app):
        with app.app_context():
            bot = Bot.query.first()
            bot_id = bot.id
        
        response = client.post(f"/bots/{bot_id}", data={
            "action": "save",
            "code": "def decide_action(gs): return {'type': 'fold'}",
        })
        assert response.status_code == 200
        
        with app.app_context():
            bot = Bot.query.get(bot_id)
            assert "fold" in bot.code

    def test_bot_validate_valid_code(self, client, app):
        with app.app_context():
            bot = Bot.query.first()
            bot_id = bot.id
        
        response = client.post(f"/bots/{bot_id}", data={
            "action": "validate",
            "code": "def decide_action(game_state): return {'type': 'check'}",
        })
        assert response.status_code == 200
        assert b"Valid" in response.data
        
        with app.app_context():
            bot = Bot.query.get(bot_id)
            assert bot.status == "valid"

    def test_bot_validate_invalid_code(self, client, app):
        with app.app_context():
            bot = Bot.query.first()
            bot_id = bot.id
        
        response = client.post(f"/bots/{bot_id}", data={
            "action": "validate",
            "code": "x = 1",  # Missing decide_action
        })
        assert response.status_code == 200
        assert b"Invalid" in response.data
        
        with app.app_context():
            bot = Bot.query.get(bot_id)
            assert bot.status == "invalid"

    def test_bot_submit_valid_code(self, client, app):
        with app.app_context():
            bot = Bot.query.first()
            bot_id = bot.id
        
        response = client.post(f"/bots/{bot_id}", data={
            "action": "submit",
            "code": "def decide_action(game_state): return {'type': 'check'}",
        })
        assert response.status_code == 200
        
        with app.app_context():
            bot = Bot.query.get(bot_id)
            assert bot.status == "submitted"
            # Should create a version
            versions = BotVersion.query.filter_by(bot_id=bot_id).all()
            assert len(versions) >= 1

    def test_bot_submit_invalid_code_blocked(self, client, app):
        with app.app_context():
            bot = Bot.query.first()
            bot_id = bot.id
        
        response = client.post(f"/bots/{bot_id}", data={
            "action": "submit",
            "code": "x = 1",  # Invalid
        })
        assert response.status_code == 200
        assert b"Fix" in response.data or b"error" in response.data.lower()
        
        with app.app_context():
            bot = Bot.query.get(bot_id)
            assert bot.status != "submitted"


class TestBotDemoRoute:
    """Tests for demo matches."""

    def test_bot_demo_runs(self, client, app):
        # First create a valid bot
        with app.app_context():
            user = User.query.first()
            bot = Bot(
                user_id=user.id,
                name="demo_bot",
                code="def decide_action(gs): return {'type': 'check'}",
                status="valid",
            )
            db.session.add(bot)
            db.session.commit()
            bot_id = bot.id

        response = client.post(f"/bots/{bot_id}", data={
            "action": "demo",
            "code": "def decide_action(gs): return {'type': 'check'}",
        })
        assert response.status_code == 200

    def test_bot_demo_with_invalid_code(self, client, app):
        with app.app_context():
            bot = Bot.query.first()
            bot_id = bot.id
        
        response = client.post(f"/bots/{bot_id}", data={
            "action": "demo",
            "code": "x = 1",  # Invalid
        })
        assert response.status_code == 200
        # Should not run demo with invalid code


class TestMatchDetailRoute:
    """Tests for match detail page."""

    def test_match_detail_404(self, client):
        response = client.get("/matches/99999")
        assert response.status_code == 404

    def test_match_detail_with_match(self, client, app):
        with app.app_context():
            # Create a match
            match = Match(seed=42, hands=5, seats=2, status="finished")
            db.session.add(match)
            db.session.commit()
            match_id = match.id
        
        response = client.get(f"/matches/{match_id}")
        assert response.status_code == 200


class TestRatingIntegration:
    """Tests for rating integration in routes."""

    def test_index_creates_missing_ratings(self, client, app):
        with app.app_context():
            # Create a bot without rating
            user = User.query.first()
            bot = Bot(
                user_id=user.id,
                name="no_rating_bot",
                code="def decide_action(gs): return {'type': 'check'}",
                status="valid",
            )
            db.session.add(bot)
            db.session.commit()
            bot_id = bot.id
            
            # Remove any auto-created rating
            rating = db.session.get(Rating, bot_id)
            if rating:
                db.session.delete(rating)
                db.session.commit()

        # Access index
        response = client.get("/")
        assert response.status_code == 200

        with app.app_context():
            # Rating should now exist
            rating = db.session.get(Rating, bot_id)
            assert rating is not None
            assert rating.rating == 1500.0


class TestAPIResponses:
    """Tests for API-like responses."""

    def test_invalid_bot_id_type(self, client):
        response = client.get("/bots/not-a-number")
        assert response.status_code == 404

    def test_match_invalid_id_type(self, client):
        response = client.get("/matches/not-a-number")
        assert response.status_code == 404


class TestFormValidation:
    """Tests for form handling."""

    def test_empty_code_handled(self, client, app):
        with app.app_context():
            bot = Bot.query.first()
            bot_id = bot.id
        
        response = client.post(f"/bots/{bot_id}", data={
            "action": "save",
            "code": "",
        })
        assert response.status_code == 200

    def test_missing_action_handled(self, client, app):
        with app.app_context():
            bot = Bot.query.first()
            bot_id = bot.id
        
        response = client.post(f"/bots/{bot_id}", data={
            "code": "def decide_action(gs): return {'type': 'check'}",
        })
        # Should handle missing action gracefully
        assert response.status_code == 200


class TestSecurityBasics:
    """Basic security tests."""

    def test_xss_in_bot_name_escaped(self, client, app):
        response = client.post("/bots/new", data={
            "user_name": "hacker",
            "bot_name": "<script>alert('xss')</script>",
        }, follow_redirects=True)
        
        # Script should be escaped, not executed
        assert b"<script>" not in response.data or b"&lt;script&gt;" in response.data

    def test_sql_injection_in_name(self, client, app):
        response = client.post("/bots/new", data={
            "user_name": "'; DROP TABLE users; --",
            "bot_name": "normal_bot",
        }, follow_redirects=True)
        
        # App should still work
        assert response.status_code == 200
        
        with app.app_context():
            # Users table should still exist
            users = User.query.all()
            assert len(users) >= 1
