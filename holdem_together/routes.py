from __future__ import annotations

import hashlib
import random
import json

from flask import Blueprint, redirect, render_template, request, url_for
from sqlalchemy import func

from .bot_sandbox import BotRunResult, run_bot_action, run_bot_action_fast, validate_bot_code
from .db import Bot, BotVersion, Match, MatchBotLog, MatchHand, MatchResult, Rating, User, db
from .ratings import EloConfig, clamp_rating, update_elo_pairwise
from .game_state import make_bot_visible_state, normalize_action
from .tournament import MatchConfig, run_match


bp = Blueprint("web", __name__)


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


@bp.get("/")
def index():
    # Ensure every bot has a rating row (lazy safety for older DBs).
    for b in Bot.query.all():
        if db.session.get(Rating, b.id) is None:
            db.session.add(Rating(bot_id=b.id, rating=1500.0, matches_played=0))
    db.session.commit()

    bots = (
        db.session.query(Bot)
        .outerjoin(Rating, Rating.bot_id == Bot.id)
        .order_by(Rating.rating.desc().nullslast(), Bot.updated_at.desc())
        .all()
    )

    rows = (
        db.session.query(
            MatchResult.bot_id,
            func.sum(MatchResult.chips_won).label("chips"),
            func.count(MatchResult.id).label("matches"),
        )
        .group_by(MatchResult.bot_id)
        .all()
    )
    agg = {int(r.bot_id): {"chips": int(r.chips or 0), "matches": int(r.matches or 0)} for r in rows}

    rating_map = {int(r.bot_id): float(r.rating) for r in Rating.query.all()}
    return render_template("index.html", bots=bots, agg=agg, rating_map=rating_map)


@bp.get("/matches")
def matches_index():
    matches = Match.query.order_by(Match.created_at.desc()).limit(100).all()
    return render_template("matches.html", matches=matches)


@bp.get("/matches/<int:match_id>")
def match_detail(match_id: int):
    match = Match.query.get_or_404(match_id)
    results = MatchResult.query.filter_by(match_id=match_id).order_by(MatchResult.chips_won.desc()).all()

    logs_rows = MatchBotLog.query.filter_by(match_id=match_id).all()
    logs_by_seat: dict[int, dict[str, str]] = {}
    for lr in logs_rows:
        logs_by_seat[int(lr.seat)] = {
            "logs": lr.logs or "",
            "errors": lr.errors or "",
        }

    hands = MatchHand.query.filter_by(match_id=match_id).order_by(MatchHand.hand_index.asc()).all()
    hand_rows = [
        {
            "hand_index": int(h.hand_index),
            "hand_seed": int(h.hand_seed),
            "dealer_seat": int(h.dealer_seat),
            "board_json": h.board_json,
            "actions_json": h.actions_json,
            "winners_json": h.winners_json,
            "delta_stacks_json": h.delta_stacks_json,
            "side_pots_json": h.side_pots_json,
        }
        for h in hands
    ]

    return render_template(
        "match_detail.html",
        match=match,
        results=results,
        logs_by_seat=logs_by_seat,
        hands=hand_rows,
    )


@bp.route("/bots/new", methods=["GET", "POST"])
def bots_new():
    if request.method == "POST":
        user_name = (request.form.get("user_name") or "").strip() or "anonymous"
        bot_name = (request.form.get("bot_name") or "").strip() or "my_bot"

        user = User.query.filter_by(name=user_name).first()
        if user is None:
            user = User(name=user_name)
            db.session.add(user)
            db.session.commit()

        code = request.form.get("code") or "def decide_action(game_state: dict) -> dict:\n    return {\"type\": \"check\"}\n"
        bot = Bot(user_id=user.id, name=bot_name, code=code, status="draft")
        db.session.add(bot)
        db.session.commit()
        return redirect(url_for("web.bot_detail", bot_id=bot.id))

    return render_template("bot_new.html")


@bp.route("/bots/<int:bot_id>", methods=["GET", "POST"])
def bot_detail(bot_id: int):
    bot = Bot.query.get_or_404(bot_id)

    msg = None
    demo = None

    if request.method == "POST":
        action = request.form.get("action")
        code = request.form.get("code") or ""
        bot.code = code

        ok, err = validate_bot_code(code)
        if ok:
            bot.status = "valid"
            bot.last_error = None
        else:
            bot.status = "invalid"
            bot.last_error = err

        if action == "save":
            msg = "Saved."

        elif action == "validate":
            msg = "Valid." if ok else "Invalid."

        elif action == "submit":
            if ok:
                bot.status = "submitted"
                ch = _hash_code(code)
                db.session.add(BotVersion(bot_id=bot.id, code_hash=ch, code=code))
                msg = "Submitted."
            else:
                msg = "Fix validation errors before submitting."

        elif action == "demo":
            if ok:
                # Demo match = multi-hand table with up to 6 bots.
                # Include this bot plus other valid/submitted bots.
                other_bots = (
                    Bot.query.filter(Bot.id != bot.id)
                    .filter(Bot.status.in_(["valid", "submitted"]))
                    .order_by(Bot.updated_at.desc())
                    .limit(5)
                    .all()
                )

                # Keep the current bot in seat 0 for a predictable demo, but shuffle opponents.
                seed = (bot.id * 1_000_003) % 2_147_483_647
                rng_seats = random.Random(int(seed) ^ 0x5F37_59DF)
                rng_seats.shuffle(other_bots)
                table_bots = [bot] + other_bots
                mcfg = MatchConfig(hands=50, seats=len(table_bots))
                match = Match(seed=int(seed), hands=int(mcfg.hands), seats=int(mcfg.seats), status="running")
                db.session.add(match)
                db.session.commit()

                demo_logs: list[dict] = []
                logs_by_seat: dict[int, list[str]] = {i: [] for i in range(len(table_bots))}
                errors_by_seat: dict[int, list[str]] = {i: [] for i in range(len(table_bots))}

                def _append_block(buf: list[str], block: str, *, max_chars: int = 20_000) -> None:
                    if not block:
                        return
                    buf.append(block)
                    joined = "\n".join(buf)
                    if len(joined) > max_chars:
                        # Keep the tail to preserve latest context.
                        tail = joined[-max_chars:]
                        buf.clear()
                        buf.append(tail)

                def _decide(code_str: str, gs: dict):
                    # Use fast in-process execution for demos (code is already validated).
                    res: BotRunResult = run_bot_action_fast(code_str, gs)
                    seat = int(gs.get("actor_seat") or 0)

                    if res.ok and res.action is not None:
                        if res.logs:
                            header = f"--- {gs.get('hand_id')} {gs.get('street')} seat={seat} ---\n"
                            _append_block(logs_by_seat[seat], header + res.logs.rstrip())

                            # Also surface primary bot logs inline on the demo panel for quick debugging.
                            if seat == 0:
                                demo_logs.append(
                                    {
                                        "hand_id": gs.get("hand_id"),
                                        "street": gs.get("street"),
                                        "logs": res.logs,
                                    }
                                )
                        return res.action

                    if res.error:
                        header = f"--- {gs.get('hand_id')} {gs.get('street')} seat={seat} ERROR ---\n"
                        _append_block(errors_by_seat[seat], header + res.error.rstrip(), max_chars=30_000)

                    # fallback action on bot failure
                    legal = {a["type"]: a for a in gs.get("legal_actions", [])}
                    if "check" in legal:
                        return {"type": "check"}
                    if "call" in legal:
                        return {"type": "call"}
                    return {"type": "fold"}

                def _make_state_fast(**kwargs):
                    # Use fewer equity samples for demo matches (20 vs 100)
                    # This gives ~10% error vs ~5% but is 5x faster
                    return make_bot_visible_state(**kwargs, equity_samples=20)

                try:
                    result = run_match(
                        bot_codes=[b.code for b in table_bots],
                        seed=seed,
                        match_config=mcfg,
                        bot_decide=_decide,
                        make_state_for_actor=_make_state_fast,
                    )
                except Exception as e:  # noqa: BLE001
                    match.status = "error"
                    match.error = str(e)
                    db.session.add(match)
                    db.session.commit()
                    demo = {"ok": False, "error": str(e), "result": {"match_id": match.id}}
                    msg = "Demo match failed."
                    db.session.add(bot)
                    db.session.commit()
                    return render_template("bot_detail.html", bot=bot, msg=msg, demo=demo)

                match.status = "finished"
                match.hands = int(result.hands)
                match.seats = int(result.seats)
                db.session.add(match)
                db.session.commit()

                # Persist per-hand replay data (board + action history + winners).
                for hand_index, hr in enumerate(result.hand_results):
                    db.session.add(
                        MatchHand(
                            match_id=match.id,
                            hand_index=int(hand_index),
                            hand_seed=int(hr.seed),
                            dealer_seat=int(hr.dealer_seat),
                            board_json=json.dumps(hr.board),
                            actions_json=json.dumps(hr.actions),
                            winners_json=json.dumps(hr.winners),
                            delta_stacks_json=json.dumps(hr.delta_stacks),
                            side_pots_json=json.dumps(hr.side_pots),
                        )
                    )
                db.session.commit()

                for seat, b in enumerate(table_bots):
                    db.session.add(
                        MatchResult(
                            match_id=match.id,
                            bot_id=b.id,
                            seat=int(seat),
                            hands_played=int(result.hands),
                            chips_won=int(result.chips_won[seat]),
                        )
                    )
                db.session.commit()

                # Persist per-bot logs/errors for match replay/debugging.
                for seat, b in enumerate(table_bots):
                    logs_text = "\n".join(logs_by_seat.get(seat, [])).strip()
                    err_text = "\n".join(errors_by_seat.get(seat, [])).strip()
                    if logs_text or err_text:
                        db.session.add(
                            MatchBotLog(
                                match_id=match.id,
                                bot_id=b.id,
                                seat=int(seat),
                                logs=logs_text or None,
                                errors=err_text or None,
                            )
                        )
                db.session.commit()

                # Update Elo ratings for this table based on chips_won.
                rating_rows: list[Rating] = []
                for b in table_bots:
                    r = db.session.get(Rating, b.id)
                    if r is None:
                        r = Rating(bot_id=b.id, rating=1500.0, matches_played=0)
                        db.session.add(r)
                    rating_rows.append(r)
                db.session.flush()

                old = [float(r.rating) for r in rating_rows]
                scores = [float(x) for x in result.chips_won]
                new = update_elo_pairwise(old, scores, cfg=EloConfig())
                for i, r in enumerate(rating_rows):
                    r.rating = clamp_rating(new[i])
                    r.matches_played = int(r.matches_played) + 1
                    db.session.add(r)
                db.session.commit()

                demo = {
                    "ok": True,
                    "table": [{"bot_id": b.id, "bot": b.name, "user": b.user.name} for b in table_bots],
                    "logs": demo_logs[-20:],
                    "result": {
                        "seed": result.seed,
                        "final_stacks": result.final_stacks,
                        "chips_won": result.chips_won,
                        "hands": result.hands,
                        "match_id": match.id,
                        "ratings": [float(r.rating) for r in rating_rows],
                    },
                }
                msg = "Demo match ran."
            else:
                msg = "Fix validation errors before running demo."

        db.session.add(bot)
        db.session.commit()

    return render_template("bot_detail.html", bot=bot, msg=msg, demo=demo)
