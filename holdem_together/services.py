from __future__ import annotations

import hashlib

from .db import Bot, BotVersion, Rating, User, db


# --- Bad Bot Code Templates ---

BASELINE_BOT_CODE = """def decide_action(game_state: dict) -> dict:
    # Always check if possible, otherwise call, otherwise fold.
    legal = {a["type"]: a for a in game_state.get("legal_actions", [])}
    if "check" in legal:
        return {"type": "check"}
    if "call" in legal:
        return {"type": "call"}
    return {"type": "fold"}
"""

ALL_IN_MANIAC_CODE = """def decide_action(game_state: dict) -> dict:
    # YOLO! All-in every single hand, no matter what.
    legal = {a["type"]: a for a in game_state.get("legal_actions", [])}
    if "raise" in legal:
        # Shove everything!
        my_stack = game_state["stacks"][game_state["actor_seat"]]
        return {"type": "raise", "amount": my_stack}
    if "call" in legal:
        return {"type": "call"}
    return {"type": "fold"}
"""

SCAREDY_CAT_CODE = """def decide_action(game_state: dict) -> dict:
    # Too scared to put any money in. Check if free, otherwise fold.
    legal = {a["type"]: a for a in game_state.get("legal_actions", [])}
    if "check" in legal:
        return {"type": "check"}
    return {"type": "fold"}
"""

CALLING_STATION_CODE = """def decide_action(game_state: dict) -> dict:
    # Never fold, never raise. Just call everything like a true calling station.
    legal = {a["type"]: a for a in game_state.get("legal_actions", [])}
    if "call" in legal:
        return {"type": "call"}
    if "check" in legal:
        return {"type": "check"}
    return {"type": "fold"}
"""

MIN_RAISE_MONKEY_CODE = """def decide_action(game_state: dict) -> dict:
    # Raise the minimum amount every chance. Annoying but ineffective.
    legal = {a["type"]: a for a in game_state.get("legal_actions", [])}
    if "raise" in legal:
        raise_info = legal["raise"]
        return {"type": "raise", "amount": raise_info.get("min", 1)}
    if "call" in legal:
        return {"type": "call"}
    if "check" in legal:
        return {"type": "check"}
    return {"type": "fold"}
"""

RANDOM_RANDY_CODE = """def decide_action(game_state: dict) -> dict:
    # Completely random decisions based on pot size. Chaos incarnate.
    legal = game_state.get("legal_actions", [])
    if not legal:
        return {"type": "fold"}
    
    # Use pot as a pseudo-random seed (no imports allowed)
    pot = game_state.get("pot", 0)
    choice_idx = pot % len(legal)
    action = legal[choice_idx]
    
    if action["type"] == "raise":
        min_amt = action.get("min", 1)
        max_amt = action.get("max", min_amt)
        # Pick an amount based on pot value
        spread = max_amt - min_amt
        amt = min_amt + (pot % (spread + 1)) if spread > 0 else min_amt
        return {"type": "raise", "amount": amt}
    return {"type": action["type"]}
"""

SUPERSTITIOUS_SAM_CODE = """def decide_action(game_state: dict) -> dict:
    # Only plays hands with lucky cards (7s, Aces, or suited).
    # Folds everything else preflop, then plays scared.
    legal = {a["type"]: a for a in game_state.get("legal_actions", [])}
    hole = game_state.get("hole_cards", [])
    street = game_state.get("street", "preflop")
    
    if street == "preflop" and len(hole) == 2:
        card1, card2 = hole[0], hole[1]
        rank1, suit1 = card1[0], card1[1]
        rank2, suit2 = card2[0], card2[1]
        
        is_lucky = "7" in (rank1, rank2) or "A" in (rank1, rank2) or suit1 == suit2
        
        if not is_lucky:
            return {"type": "fold"}
    
    # Post-flop: just check/call, no aggression
    if "check" in legal:
        return {"type": "check"}
    if "call" in legal:
        return {"type": "call"}
    return {"type": "fold"}
"""

OVERCONFIDENT_OLLIE_CODE = """def decide_action(game_state: dict) -> dict:
    # Thinks any pair is the nuts. Goes all-in with any made hand.
    legal = {a["type"]: a for a in game_state.get("legal_actions", [])}
    hand_strength = game_state.get("hand_strength", {})
    category = hand_strength.get("category", "high_card")
    
    # If we have ANYTHING better than high card, GO ALL IN!
    if category != "high_card":
        if "raise" in legal:
            my_stack = game_state["stacks"][game_state["actor_seat"]]
            return {"type": "raise", "amount": my_stack}
        if "call" in legal:
            return {"type": "call"}
    
    # Otherwise be passive
    if "check" in legal:
        return {"type": "check"}
    if "call" in legal:
        return {"type": "call"}
    return {"type": "fold"}
"""

POT_COMMITTED_PETE_CODE = """def decide_action(game_state: dict) -> dict:
    # Falls for the sunk cost fallacy. Once money is in, can't let go.
    legal = {a["type"]: a for a in game_state.get("legal_actions", [])}
    contributed = game_state.get("contributed_total", [])
    actor = game_state.get("actor_seat", 0)
    my_investment = contributed[actor] if actor < len(contributed) else 0
    
    # If we've put in more than 50 chips, we're "pot committed" - never fold!
    if my_investment > 50:
        if "call" in legal:
            return {"type": "call"}
        if "check" in legal:
            return {"type": "check"}
        # Even call an all-in rather than "waste" what we put in
        if "raise" in legal:
            return {"type": "raise", "amount": legal["raise"].get("min", 1)}
    
    # Early in hand, just check/call
    if "check" in legal:
        return {"type": "check"}
    if "call" in legal:
        return {"type": "call"}
    return {"type": "fold"}
"""


# List of all bad bots to seed
BAD_BOTS = [
    ("baseline_check_call", BASELINE_BOT_CODE),
    ("all_in_maniac", ALL_IN_MANIAC_CODE),
    ("scaredy_cat", SCAREDY_CAT_CODE),
    ("calling_station", CALLING_STATION_CODE),
    ("min_raise_monkey", MIN_RAISE_MONKEY_CODE),
    ("random_randy", RANDOM_RANDY_CODE),
    ("superstitious_sam", SUPERSTITIOUS_SAM_CODE),
    ("overconfident_ollie", OVERCONFIDENT_OLLIE_CODE),
    ("pot_committed_pete", POT_COMMITTED_PETE_CODE),
]


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _create_bot(user_id: int, name: str, code: str) -> Bot:
    """Helper to create a bot with its version and rating."""
    bot = Bot(user_id=user_id, name=name, code=code, status="valid")
    db.session.add(bot)
    db.session.commit()

    version = BotVersion(bot_id=bot.id, code_hash=_hash_code(code), code=code)
    db.session.add(version)
    db.session.commit()

    if db.session.get(Rating, bot.id) is None:
        db.session.add(Rating(bot_id=bot.id, rating=1500.0, matches_played=0))
        db.session.commit()
    
    return bot


def ensure_seed_data() -> None:
    if User.query.count() == 0:
        user = User(name="baseline")
        db.session.add(user)
        db.session.commit()

    baseline_user = User.query.filter_by(name="baseline").first()
    assert baseline_user is not None

    if Bot.query.count() == 0:
        # Create all the bad bots
        for name, code in BAD_BOTS:
            _create_bot(baseline_user.id, name, code)


def ensure_ratings_exist() -> None:
    bots = Bot.query.all()
    for b in bots:
        if db.session.get(Rating, b.id) is None:
            db.session.add(Rating(bot_id=b.id, rating=1500.0, matches_played=0))
    db.session.commit()
