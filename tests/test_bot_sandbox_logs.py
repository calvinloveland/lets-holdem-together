from __future__ import annotations

from holdem_together.bot_sandbox import run_bot_action
from holdem_together.game_state import make_bot_visible_state


def test_bot_print_logs_captured():
    code = """
import math

def decide_action(game_state):
    print('hello', 1)
    return {"type": "check", "x": math.sqrt(9)}
"""

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
        legal_actions=[{"type": "check"}],
        active_seats=[0, 1],
    )

    res = run_bot_action(code, gs, timeout_s=0.5)
    assert res.ok
    assert res.logs and "hello 1" in res.logs
