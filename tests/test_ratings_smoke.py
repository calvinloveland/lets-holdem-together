from __future__ import annotations

from pathlib import Path

from holdem_together.app import create_app
from holdem_together.background_runner import RunnerConfig, run_one_match
from holdem_together.db import Bot, Rating, db


def test_ratings_update_after_match(tmp_path: Path):
    db_path = tmp_path / "elo.sqlite3"
    app = create_app({"SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path.as_posix()}"})

    with app.app_context():
        bots = Bot.query.all()
        assert bots
        # Ensure two submitted bots.
        bots[0].status = "submitted"
        if len(bots) == 1:
            b2 = Bot(user_id=bots[0].user_id, name="b2", code=bots[0].code, status="submitted")
            db.session.add(b2)
            db.session.commit()
            bots = Bot.query.all()
        else:
            bots[1].status = "submitted"
            db.session.add(bots[0])
            db.session.add(bots[1])
            db.session.commit()

        # Snapshot ratings.
        before = {r.bot_id: r.rating for r in Rating.query.all()}
        mid = run_one_match(cfg=RunnerConfig(seats=2, hands=5, sleep_s=0), seed=4242)
        assert mid is not None
        after = {r.bot_id: r.rating for r in Rating.query.all()}

        # At least one rating should have moved.
        assert before != after
