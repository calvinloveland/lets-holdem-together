from __future__ import annotations

from datetime import UTC, datetime

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint


db = SQLAlchemy()


def _utcnow() -> datetime:
    return datetime.now(UTC)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)


class Bot(db.Model):
    __tablename__ = "bots"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)

    code = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(32), nullable=False, default="draft")  # draft|valid|invalid|submitted
    last_error = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    user = db.relationship("User", backref=db.backref("bots", lazy=True))

    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_bot_user_name"),)


class BotVersion(db.Model):
    __tablename__ = "bot_versions"

    id = db.Column(db.Integer, primary_key=True)
    bot_id = db.Column(db.Integer, db.ForeignKey("bots.id"), nullable=False)
    code_hash = db.Column(db.String(64), nullable=False)
    code = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    bot = db.relationship("Bot", backref=db.backref("versions", lazy=True, order_by="BotVersion.created_at.desc()"))


class Match(db.Model):
    __tablename__ = "matches"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    seed = db.Column(db.Integer, nullable=False)
    hands = db.Column(db.Integer, nullable=False)
    seats = db.Column(db.Integer, nullable=False)

    status = db.Column(db.String(32), nullable=False, default="finished")  # queued|running|finished|error
    error = db.Column(db.Text, nullable=True)


class MatchResult(db.Model):
    __tablename__ = "match_results"

    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey("matches.id"), nullable=False, index=True)
    bot_id = db.Column(db.Integer, db.ForeignKey("bots.id"), nullable=False, index=True)
    seat = db.Column(db.Integer, nullable=False)

    hands_played = db.Column(db.Integer, nullable=False)
    chips_won = db.Column(db.Integer, nullable=False)

    match = db.relationship("Match", backref=db.backref("results", lazy=True, order_by="MatchResult.seat.asc()"))
    bot = db.relationship("Bot", backref=db.backref("match_results", lazy=True))


class MatchHand(db.Model):
    __tablename__ = "match_hands"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    match_id = db.Column(db.Integer, db.ForeignKey("matches.id"), nullable=False, index=True)
    hand_index = db.Column(db.Integer, nullable=False)
    hand_seed = db.Column(db.Integer, nullable=False)
    dealer_seat = db.Column(db.Integer, nullable=False)

    board_json = db.Column(db.Text, nullable=False)
    actions_json = db.Column(db.Text, nullable=False)
    winners_json = db.Column(db.Text, nullable=False)
    delta_stacks_json = db.Column(db.Text, nullable=False)
    side_pots_json = db.Column(db.Text, nullable=False)

    match = db.relationship("Match", backref=db.backref("hand_rows", lazy=True, order_by="MatchHand.hand_index.asc()"))

    __table_args__ = (UniqueConstraint("match_id", "hand_index", name="uq_match_hand_index"),)


class Rating(db.Model):
    __tablename__ = "ratings"

    bot_id = db.Column(db.Integer, db.ForeignKey("bots.id"), primary_key=True)
    rating = db.Column(db.Float, nullable=False, default=1500.0)
    matches_played = db.Column(db.Integer, nullable=False, default=0)

    bot = db.relationship("Bot", backref=db.backref("rating_row", uselist=False, lazy=True))


class MatchBotLog(db.Model):
    __tablename__ = "match_bot_logs"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    match_id = db.Column(db.Integer, db.ForeignKey("matches.id"), nullable=False, index=True)
    bot_id = db.Column(db.Integer, db.ForeignKey("bots.id"), nullable=False, index=True)
    seat = db.Column(db.Integer, nullable=False)

    logs = db.Column(db.Text, nullable=True)
    errors = db.Column(db.Text, nullable=True)

    match = db.relationship("Match", backref=db.backref("bot_logs", lazy=True, order_by="MatchBotLog.seat.asc()"))
    bot = db.relationship("Bot", backref=db.backref("match_bot_logs", lazy=True))

    __table_args__ = (UniqueConstraint("match_id", "bot_id", "seat", name="uq_match_bot_seat"),)
