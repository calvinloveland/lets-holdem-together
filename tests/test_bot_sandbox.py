from holdem_together.bot_sandbox import run_bot_action, validate_bot_code
from holdem_together.game_state import make_bot_visible_state


def test_validate_requires_decide_action():
    ok, err = validate_bot_code("x = 1\n")
    assert not ok
    assert err and "decide_action" in err


def test_demo_bot_runs():
    code = """def decide_action(game_state: dict) -> dict:\n    return {\"type\": \"check\"}\n"""
    ok, err = validate_bot_code(code)
    assert ok and err is None

    gs = make_bot_visible_state(
        seed=1,
        street="preflop",
        dealer_seat=0,
        actor_seat=0,
        hole_cards=["As", "Kd"],
        board_cards=[],
        stacks=[1000, 1000, 1000],
        contributed_this_street=[10, 20, 0],
        contributed_total=[10, 20, 0],
        action_history=[
            {"street": "preflop", "seat": 0, "type": "post_sb", "amount": 10},
            {"street": "preflop", "seat": 1, "type": "post_bb", "amount": 20},
        ],
        legal_actions=[{"type": "check"}],
        active_seats=[0, 1, 2],
    )
    res = run_bot_action(code, gs, timeout_s=0.5)
    assert res.ok
    assert res.action == {"type": "check"}
