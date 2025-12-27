from __future__ import annotations

import hashlib

from .db import Bot, BotVersion, Rating, User, db


BASELINE_BOT_CODE = """def decide_action(game_state: dict) -> dict:\n    # Always check if possible, otherwise call, otherwise fold.\n    legal = {a[\"type\"]: a for a in game_state.get(\"legal_actions\", [])}\n    if \"check\" in legal:\n        return {\"type\": \"check\"}\n    if \"call\" in legal:\n        return {\"type\": \"call\"}\n    return {\"type\": \"fold\"}\n"""


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def ensure_seed_data() -> None:
    if User.query.count() == 0:
        user = User(name="baseline")
        db.session.add(user)
        db.session.commit()

    baseline_user = User.query.filter_by(name="baseline").first()
    assert baseline_user is not None

    if Bot.query.count() == 0:
        bot = Bot(user_id=baseline_user.id, name="baseline_check_call", code=BASELINE_BOT_CODE, status="valid")
        db.session.add(bot)
        db.session.commit()

        version = BotVersion(bot_id=bot.id, code_hash=_hash_code(BASELINE_BOT_CODE), code=BASELINE_BOT_CODE)
        db.session.add(version)
        db.session.commit()

        if db.session.get(Rating, bot.id) is None:
            db.session.add(Rating(bot_id=bot.id, rating=1500.0, matches_played=0))
            db.session.commit()


def ensure_ratings_exist() -> None:
    bots = Bot.query.all()
    for b in bots:
        if db.session.get(Rating, b.id) is None:
            db.session.add(Rating(bot_id=b.id, rating=1500.0, matches_played=0))
    db.session.commit()
