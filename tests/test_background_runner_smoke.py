from __future__ import annotations

from pathlib import Path

from holdem_together.app import create_app
from holdem_together.background_runner import RunnerConfig, run_one_match
from holdem_together.db import Bot, BotVersion, MatchBotLog, MatchHand


PRINTING_BOT = """def decide_action(game_state: dict) -> dict:\n    print('hi', game_state.get('street'))\n    legal = {a['type']: a for a in game_state.get('legal_actions', [])}\n    if 'check' in legal:\n        return {'type': 'check'}\n    if 'call' in legal:\n        return {'type': 'call'}\n    return {'type': 'fold'}\n"""


def test_run_one_match_creates_match(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    app = create_app({"SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path.as_posix()}"})

    with app.app_context():
        from holdem_together.db import db
        
        # Ensure we have at least 2 eligible bots.
        bots = Bot.query.all()
        assert bots
        
        # Update both code and version to use PRINTING_BOT
        bots[0].status = "submitted"
        bots[0].code = PRINTING_BOT
        # Also update or add a BotVersion with the new code (run_one_match uses versions first)
        if bots[0].versions:
            bots[0].versions[0].code = PRINTING_BOT
        else:
            db.session.add(BotVersion(bot_id=bots[0].id, code_hash="test", code=PRINTING_BOT))
        
        if len(bots) == 1:
            # Clone baseline as a second bot
            b = Bot(user_id=bots[0].user_id, name="baseline2", code=PRINTING_BOT, status="submitted")
            db.session.add(b)
            db.session.commit()
            db.session.add(BotVersion(bot_id=b.id, code_hash="test", code=PRINTING_BOT))
        else:
            bots[1].status = "submitted"
            bots[1].code = PRINTING_BOT
            if bots[1].versions:
                bots[1].versions[0].code = PRINTING_BOT
            else:
                db.session.add(BotVersion(bot_id=bots[1].id, code_hash="test", code=PRINTING_BOT))
            db.session.add(bots[0])
            db.session.add(bots[1])
        
        db.session.commit()

        match_id = run_one_match(cfg=RunnerConfig(seats=2, hands=5, sleep_s=0), seed=123)
        assert match_id is not None

        rows = MatchBotLog.query.filter_by(match_id=int(match_id)).all()
        assert rows
        assert any((r.logs or "").find("hi") != -1 for r in rows)

        hands = MatchHand.query.filter_by(match_id=int(match_id)).all()
        # Match may end early if one player wins all chips
        assert 1 <= len(hands) <= 5
