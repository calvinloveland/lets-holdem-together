"""Comprehensive tests for services module."""
from __future__ import annotations

from pathlib import Path

import pytest

from holdem_together.app import create_app
from holdem_together.db import Bot, BotVersion, Rating, User, db
from holdem_together.services import (
    BASELINE_BOT_CODE,
    ensure_seed_data,
    ensure_ratings_exist,
    _hash_code,
)


@pytest.fixture
def app(tmp_path: Path):
    """Create test app with temp database."""
    db_path = tmp_path / "test.sqlite3"
    app = create_app({
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path.as_posix()}",
        "TESTING": True,
    })
    yield app


class TestHashCode:
    """Tests for code hashing."""

    def test_hash_returns_string(self):
        h = _hash_code("test code")
        assert isinstance(h, str)

    def test_hash_is_sha256_length(self):
        h = _hash_code("test code")
        assert len(h) == 64  # SHA256 hex digest

    def test_same_code_same_hash(self):
        h1 = _hash_code("def decide_action(gs): return {'type': 'check'}")
        h2 = _hash_code("def decide_action(gs): return {'type': 'check'}")
        assert h1 == h2

    def test_different_code_different_hash(self):
        h1 = _hash_code("code1")
        h2 = _hash_code("code2")
        assert h1 != h2

    def test_hash_empty_string(self):
        h = _hash_code("")
        assert isinstance(h, str)
        assert len(h) == 64

    def test_hash_unicode(self):
        h = _hash_code("def decide_action(gs): # комментарий\n    return {'type': 'check'}")
        assert isinstance(h, str)
        assert len(h) == 64


class TestBaselineBotCode:
    """Tests for the baseline bot code constant."""

    def test_baseline_code_exists(self):
        assert BASELINE_BOT_CODE is not None
        assert len(BASELINE_BOT_CODE) > 0

    def test_baseline_code_has_decide_action(self):
        assert "decide_action" in BASELINE_BOT_CODE

    def test_baseline_code_is_valid(self):
        from holdem_together.bot_sandbox import validate_bot_code
        ok, err = validate_bot_code(BASELINE_BOT_CODE)
        assert ok, err


class TestEnsureSeedData:
    """Tests for seed data creation."""

    def test_creates_baseline_user(self, app):
        with app.app_context():
            # Check if seed data already exists (app creates it)
            baseline = User.query.filter_by(name="baseline").first()
            if baseline:
                # Already seeded, just verify
                assert baseline is not None
            else:
                # Need to create from scratch
                ensure_seed_data()
                user = User.query.filter_by(name="baseline").first()
                assert user is not None

    def test_creates_baseline_bot(self, app):
        with app.app_context():
            # Seed data is already created by app, verify it's correct
            ensure_seed_data()
            
            bots = Bot.query.all()
            assert len(bots) >= 1
            
            baseline_bot = Bot.query.filter_by(name="baseline_check_call").first()
            assert baseline_bot is not None
            assert baseline_bot.code == BASELINE_BOT_CODE

    def test_creates_bot_version(self, app):
        with app.app_context():
            # Seed data is already created by app
            ensure_seed_data()
            
            versions = BotVersion.query.all()
            assert len(versions) >= 1

    def test_creates_rating(self, app):
        with app.app_context():
            # Seed data is already created by app
            ensure_seed_data()
            
            ratings = Rating.query.all()
            assert len(ratings) >= 1
            # At least one rating should be default 1500
            assert any(r.rating == 1500.0 for r in ratings)

    def test_idempotent(self, app):
        with app.app_context():
            # Run ensure_seed_data multiple times
            ensure_seed_data()
            count1 = User.query.count()
            bot_count1 = Bot.query.count()
            
            ensure_seed_data()
            count2 = User.query.count()
            bot_count2 = Bot.query.count()
            
            # Counts should not change
            assert count1 == count2
            assert bot_count1 == bot_count2
            
            # Should have exactly one baseline user
            baseline_users = User.query.filter_by(name="baseline").all()
            assert len(baseline_users) == 1

    def test_baseline_user_created(self, app):
        with app.app_context():
            ensure_seed_data()
            
            # Should have baseline user
            baseline = User.query.filter_by(name="baseline").first()
            assert baseline is not None


class TestEnsureRatingsExist:
    """Tests for ratings initialization."""

    def test_creates_missing_ratings(self, app):
        with app.app_context():
            # Create a bot without rating
            user = User.query.first() or User(name="test")
            if not User.query.first():
                db.session.add(user)
                db.session.commit()
            
            bot = Bot(
                user_id=user.id,
                name="no_rating_bot",
                code="def decide_action(gs): return {'type': 'check'}",
                status="valid",
            )
            db.session.add(bot)
            db.session.commit()
            bot_id = bot.id
            
            # Remove rating if exists
            rating = db.session.get(Rating, bot_id)
            if rating:
                db.session.delete(rating)
                db.session.commit()
            
            ensure_ratings_exist()
            
            rating = db.session.get(Rating, bot_id)
            assert rating is not None
            assert rating.rating == 1500.0

    def test_preserves_existing_ratings(self, app):
        with app.app_context():
            # Create a bot with custom rating
            user = User.query.first() or User(name="test")
            if not User.query.first():
                db.session.add(user)
                db.session.commit()
            
            bot = Bot(
                user_id=user.id,
                name="rated_bot",
                code="def decide_action(gs): return {'type': 'check'}",
                status="valid",
            )
            db.session.add(bot)
            db.session.commit()
            
            rating = Rating(bot_id=bot.id, rating=1800.0, matches_played=10)
            db.session.add(rating)
            db.session.commit()
            
            ensure_ratings_exist()
            
            rating = db.session.get(Rating, bot.id)
            assert rating.rating == 1800.0
            assert rating.matches_played == 10

    def test_handles_multiple_bots(self, app):
        with app.app_context():
            user = User.query.first() or User(name="test")
            if not User.query.first():
                db.session.add(user)
                db.session.commit()
            
            # Create multiple bots
            for i in range(3):
                bot = Bot(
                    user_id=user.id,
                    name=f"multi_bot_{i}",
                    code="def decide_action(gs): return {'type': 'check'}",
                    status="valid",
                )
                db.session.add(bot)
            db.session.commit()
            
            # Remove all ratings
            for r in Rating.query.all():
                db.session.delete(r)
            db.session.commit()
            
            ensure_ratings_exist()
            
            # All bots should have ratings
            bots = Bot.query.all()
            for bot in bots:
                rating = db.session.get(Rating, bot.id)
                assert rating is not None

    def test_empty_database(self, app):
        with app.app_context():
            # Clear everything
            for version in BotVersion.query.all():
                db.session.delete(version)
            for rating in Rating.query.all():
                db.session.delete(rating)
            for bot in Bot.query.all():
                db.session.delete(bot)
            db.session.commit()
            
            # Should not raise
            ensure_ratings_exist()


class TestServiceIntegration:
    """Integration tests for services."""

    def test_full_setup_flow(self, app):
        with app.app_context():
            # Clear database
            for version in BotVersion.query.all():
                db.session.delete(version)
            for rating in Rating.query.all():
                db.session.delete(rating)
            for bot in Bot.query.all():
                db.session.delete(bot)
            for user in User.query.all():
                db.session.delete(user)
            db.session.commit()
            
            # Run both setup functions
            ensure_seed_data()
            ensure_ratings_exist()
            
            # Verify complete state
            users = User.query.all()
            bots = Bot.query.all()
            ratings = Rating.query.all()
            versions = BotVersion.query.all()
            
            assert len(users) >= 1
            assert len(bots) >= 1
            assert len(ratings) >= 1
            assert len(versions) >= 1

    def test_baseline_bot_is_playable(self, app):
        with app.app_context():
            # Ensure seed data
            ensure_seed_data()
            
            bot = Bot.query.filter_by(name="baseline_check_call").first()
            assert bot is not None
            
            # Validate the code
            from holdem_together.bot_sandbox import validate_bot_code, run_bot_action_fast
            from holdem_together.game_state import make_bot_visible_state
            
            ok, err = validate_bot_code(bot.code)
            assert ok, err
            
            # Run it
            gs = make_bot_visible_state(
                seed=1,
                street="preflop",
                dealer_seat=0,
                actor_seat=0,
                hole_cards=["As", "Kd"],
                board_cards=[],
                stacks=[1000, 1000],
                contributed_this_street=[10, 20],
                contributed_total=[10, 20],
                action_history=[],
                legal_actions=[{"type": "fold"}, {"type": "call"}, {"type": "check"}],
                active_seats=[0, 1],
            )
            
            result = run_bot_action_fast(bot.code, gs)
            assert result.ok
            assert result.action["type"] in ("check", "call", "fold")
