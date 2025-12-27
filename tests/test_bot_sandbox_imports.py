from __future__ import annotations

from holdem_together.bot_sandbox import run_bot_action, validate_bot_code
from holdem_together.game_state import make_bot_visible_state


def _gs():
    return make_bot_visible_state(
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
        legal_actions=[{"type": "check"}],
        active_seats=[0, 1],
    )


def test_import_math_allowed():
    code = """
import math

def decide_action(game_state):
    return {"type": "check", "x": math.sqrt(4)}
"""
    ok, err = validate_bot_code(code)
    assert ok, err
    res = run_bot_action(code, _gs(), timeout_s=0.5)
    assert res.ok


def test_import_os_blocked():
    code = """
import os

def decide_action(game_state):
    return {"type": "check"}
"""
    ok, err = validate_bot_code(code)
    assert not ok
    assert err and "Import not allowed" in err
