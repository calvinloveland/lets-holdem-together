from holdem_together.engine import TableConfig, simulate_hand
from holdem_together.game_state import make_bot_visible_state


def _always_check_or_call(code: str, game_state: dict) -> dict:
    legal = {a["type"]: a for a in game_state.get("legal_actions", [])}
    if "check" in legal:
        return {"type": "check"}
    if "call" in legal:
        return {"type": "call"}
    return {"type": "fold"}


def test_simulate_hand_deterministic():
    cfg = TableConfig(seats=4)
    codes = ["def decide_action(gs): return {'type':'check'}" for _ in range(cfg.seats)]

    stacks = [cfg.starting_stack for _ in range(cfg.seats)]
    r1 = simulate_hand(
        codes,
        seed=123,
        config=cfg,
        initial_stacks=stacks,
        bot_decide=_always_check_or_call,
        make_state_for_actor=make_bot_visible_state,
    )
    r2 = simulate_hand(
        codes,
        seed=123,
        config=cfg,
        initial_stacks=stacks,
        bot_decide=_always_check_or_call,
        make_state_for_actor=make_bot_visible_state,
    )

    assert r1.board == r2.board
    assert r1.actions == r2.actions
    assert r1.final_stacks == r2.final_stacks
