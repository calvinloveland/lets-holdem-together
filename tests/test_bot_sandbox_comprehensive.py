"""Comprehensive tests for bot_sandbox module."""
from __future__ import annotations

import pytest

from holdem_together.bot_sandbox import (
    BotRunResult,
    run_bot_action,
    run_bot_action_fast,
    validate_bot_code,
    _ALLOWED_IMPORTS,
)
from holdem_together.game_state import make_bot_visible_state


def _make_basic_game_state():
    """Create a basic game state for testing."""
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
        action_history=[
            {"street": "preflop", "seat": 0, "type": "post_sb", "amount": 10},
            {"street": "preflop", "seat": 1, "type": "post_bb", "amount": 20},
        ],
        legal_actions=[{"type": "fold"}, {"type": "call", "amount": 10}, {"type": "raise", "min": 40, "max": 1000}],
        active_seats=[0, 1],
    )


class TestValidateBotCodeSyntax:
    """Tests for bot code syntax validation."""

    def test_valid_basic_bot(self):
        code = """
def decide_action(game_state: dict) -> dict:
    return {"type": "check"}
"""
        ok, err = validate_bot_code(code)
        assert ok
        assert err is None

    def test_syntax_error(self):
        code = """
def decide_action(game_state
    return {"type": "check"}
"""
        ok, err = validate_bot_code(code)
        assert not ok
        assert "SyntaxError" in err

    def test_indentation_error(self):
        code = """
def decide_action(game_state: dict) -> dict:
return {"type": "check"}
"""
        ok, err = validate_bot_code(code)
        assert not ok
        assert "Syntax" in err or "indent" in err.lower()


class TestValidateBotCodeFunction:
    """Tests for required function validation."""

    def test_missing_decide_action(self):
        code = """
def other_function(x):
    return x
"""
        ok, err = validate_bot_code(code)
        assert not ok
        assert "decide_action" in err

    def test_decide_action_not_callable(self):
        code = """
decide_action = 42
"""
        ok, err = validate_bot_code(code)
        assert not ok
        assert "decide_action" in err

    def test_decide_action_as_variable(self):
        code = """
decide_action = "not a function"
"""
        ok, err = validate_bot_code(code)
        assert not ok


class TestValidateBotCodeImports:
    """Tests for import restrictions."""

    def test_import_math_allowed(self):
        code = """
import math

def decide_action(game_state: dict) -> dict:
    return {"type": "check", "x": math.sqrt(4)}
"""
        ok, err = validate_bot_code(code)
        assert ok, err

    def test_import_statistics_allowed(self):
        code = """
import statistics

def decide_action(game_state: dict) -> dict:
    return {"type": "check"}
"""
        ok, err = validate_bot_code(code)
        assert ok, err

    def test_import_os_blocked(self):
        code = """
import os

def decide_action(game_state: dict) -> dict:
    return {"type": "check"}
"""
        ok, err = validate_bot_code(code)
        assert not ok
        assert "Import not allowed" in err

    def test_import_sys_blocked(self):
        code = """
import sys

def decide_action(game_state: dict) -> dict:
    return {"type": "check"}
"""
        ok, err = validate_bot_code(code)
        assert not ok
        assert "Import not allowed" in err

    def test_import_subprocess_blocked(self):
        code = """
import subprocess

def decide_action(game_state: dict) -> dict:
    return {"type": "check"}
"""
        ok, err = validate_bot_code(code)
        assert not ok

    def test_from_import_blocked(self):
        code = """
from os import path

def decide_action(game_state: dict) -> dict:
    return {"type": "check"}
"""
        ok, err = validate_bot_code(code)
        assert not ok


class TestValidateBotCodeRuntimeError:
    """Tests for runtime errors during validation."""

    def test_runtime_error_during_exec(self):
        code = """
x = 1 / 0  # ZeroDivisionError at import time

def decide_action(game_state: dict) -> dict:
    return {"type": "check"}
"""
        ok, err = validate_bot_code(code)
        assert not ok
        assert "Runtime error" in err or "ZeroDivision" in err


class TestRunBotActionFast:
    """Tests for fast in-process bot execution."""

    def test_basic_execution(self):
        code = """
def decide_action(game_state: dict) -> dict:
    return {"type": "check"}
"""
        gs = _make_basic_game_state()
        result = run_bot_action_fast(code, gs)
        assert result.ok
        assert result.action == {"type": "check"}

    def test_returns_fold(self):
        code = """
def decide_action(game_state: dict) -> dict:
    return {"type": "fold"}
"""
        gs = _make_basic_game_state()
        result = run_bot_action_fast(code, gs)
        assert result.ok
        assert result.action == {"type": "fold"}

    def test_returns_call(self):
        code = """
def decide_action(game_state: dict) -> dict:
    return {"type": "call"}
"""
        gs = _make_basic_game_state()
        result = run_bot_action_fast(code, gs)
        assert result.ok
        assert result.action == {"type": "call"}

    def test_returns_raise_with_amount(self):
        code = """
def decide_action(game_state: dict) -> dict:
    return {"type": "raise", "amount": 100}
"""
        gs = _make_basic_game_state()
        result = run_bot_action_fast(code, gs)
        assert result.ok
        assert result.action == {"type": "raise", "amount": 100}

    def test_reads_game_state(self):
        code = """
def decide_action(game_state: dict) -> dict:
    if game_state.get("street") == "preflop":
        return {"type": "call"}
    return {"type": "check"}
"""
        gs = _make_basic_game_state()
        result = run_bot_action_fast(code, gs)
        assert result.ok
        assert result.action == {"type": "call"}

    def test_uses_hole_cards(self):
        code = """
def decide_action(game_state: dict) -> dict:
    hole = game_state.get("hole_cards", [])
    if "As" in hole:
        return {"type": "raise", "amount": 100}
    return {"type": "fold"}
"""
        gs = _make_basic_game_state()
        result = run_bot_action_fast(code, gs)
        assert result.ok
        assert result.action == {"type": "raise", "amount": 100}

    def test_captures_print_output(self):
        code = """
def decide_action(game_state: dict) -> dict:
    print("Hello from bot!")
    return {"type": "check"}
"""
        gs = _make_basic_game_state()
        result = run_bot_action_fast(code, gs)
        assert result.ok
        assert "Hello from bot!" in result.logs

    def test_error_in_decide_action(self):
        code = """
def decide_action(game_state: dict) -> dict:
    x = 1 / 0  # ZeroDivisionError
    return {"type": "check"}
"""
        gs = _make_basic_game_state()
        result = run_bot_action_fast(code, gs)
        assert not result.ok
        assert "ZeroDivision" in result.error

    def test_returns_non_dict_fails(self):
        code = """
def decide_action(game_state: dict) -> dict:
    return "check"
"""
        gs = _make_basic_game_state()
        result = run_bot_action_fast(code, gs)
        assert not result.ok
        assert "dict" in result.error.lower()

    def test_uses_math_module(self):
        code = """
import math

def decide_action(game_state: dict) -> dict:
    x = math.sqrt(16)
    return {"type": "raise", "amount": int(x * 10)}
"""
        gs = _make_basic_game_state()
        result = run_bot_action_fast(code, gs)
        assert result.ok
        assert result.action == {"type": "raise", "amount": 40}


class TestRunBotAction:
    """Tests for subprocess bot execution."""

    def test_basic_execution(self):
        code = """
def decide_action(game_state: dict) -> dict:
    return {"type": "check"}
"""
        gs = _make_basic_game_state()
        result = run_bot_action(code, gs, timeout_s=2.0)
        assert result.ok
        assert result.action == {"type": "check"}

    def test_captures_print(self):
        code = """
def decide_action(game_state: dict) -> dict:
    print("subprocess print")
    return {"type": "call"}
"""
        gs = _make_basic_game_state()
        result = run_bot_action(code, gs, timeout_s=2.0)
        assert result.ok
        assert "subprocess print" in result.logs

    def test_runtime_error_reported(self):
        code = """
def decide_action(game_state: dict) -> dict:
    raise ValueError("intentional error")
"""
        gs = _make_basic_game_state()
        result = run_bot_action(code, gs, timeout_s=2.0)
        assert not result.ok
        assert "ValueError" in result.error or "intentional error" in result.error


class TestBotComplexLogic:
    """Tests for more complex bot logic."""

    def test_equity_based_decision(self):
        code = """
def decide_action(game_state: dict) -> dict:
    hs = game_state.get("hand_strength", {})
    equity = hs.get("equity_estimate", 0)
    if equity > 0.5:
        return {"type": "raise", "amount": 50}
    return {"type": "call"}
"""
        gs = _make_basic_game_state()
        result = run_bot_action_fast(code, gs)
        assert result.ok
        assert result.action["type"] in ("raise", "call")

    def test_pot_odds_calculation(self):
        code = """
def decide_action(game_state: dict) -> dict:
    pot = game_state.get("pot", 0)
    to_call = 10  # From legal actions
    if pot > 0:
        pot_odds = to_call / (pot + to_call)
        if pot_odds < 0.3:
            return {"type": "call"}
    return {"type": "fold"}
"""
        gs = _make_basic_game_state()
        result = run_bot_action_fast(code, gs)
        assert result.ok

    def test_street_based_logic(self):
        code = """
def decide_action(game_state: dict) -> dict:
    street = game_state.get("street", "")
    if street == "preflop":
        return {"type": "call"}
    elif street == "flop":
        return {"type": "check"}
    else:
        return {"type": "fold"}
"""
        gs = _make_basic_game_state()
        result = run_bot_action_fast(code, gs)
        assert result.ok
        assert result.action == {"type": "call"}

    def test_action_history_analysis(self):
        code = """
def decide_action(game_state: dict) -> dict:
    history = game_state.get("action_history", [])
    num_raises = sum(1 for a in history if a.get("type") == "raise")
    if num_raises > 2:
        return {"type": "fold"}
    return {"type": "call"}
"""
        gs = _make_basic_game_state()
        result = run_bot_action_fast(code, gs)
        assert result.ok


class TestBotBuiltins:
    """Tests for available built-in functions."""

    def test_uses_min_max(self):
        code = """
def decide_action(game_state: dict) -> dict:
    stacks = game_state.get("stacks", [])
    m = max(stacks) if stacks else 0
    return {"type": "raise", "amount": min(100, m)}
"""
        gs = _make_basic_game_state()
        result = run_bot_action_fast(code, gs)
        assert result.ok

    def test_uses_len_sum(self):
        code = """
def decide_action(game_state: dict) -> dict:
    stacks = game_state.get("stacks", [])
    total = sum(stacks)
    count = len(stacks)
    if count > 0 and total / count > 500:
        return {"type": "call"}
    return {"type": "fold"}
"""
        gs = _make_basic_game_state()
        result = run_bot_action_fast(code, gs)
        assert result.ok

    def test_uses_sorted(self):
        code = """
def decide_action(game_state: dict) -> dict:
    stacks = game_state.get("stacks", [])
    s = sorted(stacks, reverse=True)
    return {"type": "check"}
"""
        gs = _make_basic_game_state()
        result = run_bot_action_fast(code, gs)
        assert result.ok

    def test_uses_enumerate_range(self):
        code = """
def decide_action(game_state: dict) -> dict:
    stacks = game_state.get("stacks", [])
    for i, s in enumerate(stacks):
        pass
    for x in range(10):
        pass
    return {"type": "check"}
"""
        gs = _make_basic_game_state()
        result = run_bot_action_fast(code, gs)
        assert result.ok

    def test_uses_round_abs(self):
        code = """
def decide_action(game_state: dict) -> dict:
    x = round(3.7)
    y = abs(-5)
    return {"type": "raise", "amount": x + y}
"""
        gs = _make_basic_game_state()
        result = run_bot_action_fast(code, gs)
        assert result.ok
        assert result.action == {"type": "raise", "amount": 9}


class TestBotDataTypes:
    """Tests for data type construction."""

    def test_creates_dict(self):
        code = """
def decide_action(game_state: dict) -> dict:
    d = dict(type="check")
    return d
"""
        gs = _make_basic_game_state()
        result = run_bot_action_fast(code, gs)
        assert result.ok
        assert result.action == {"type": "check"}

    def test_creates_list_tuple_set(self):
        code = """
def decide_action(game_state: dict) -> dict:
    l = list([1, 2, 3])
    t = tuple((1, 2))
    s = set([1, 2, 3])
    return {"type": "check"}
"""
        gs = _make_basic_game_state()
        result = run_bot_action_fast(code, gs)
        assert result.ok

    def test_type_conversions(self):
        code = """
def decide_action(game_state: dict) -> dict:
    i = int("42")
    f = float("3.14")
    s = str(100)
    b = bool(1)
    return {"type": "raise", "amount": i}
"""
        gs = _make_basic_game_state()
        result = run_bot_action_fast(code, gs)
        assert result.ok
        assert result.action == {"type": "raise", "amount": 42}


class TestBotPrintFormats:
    """Tests for print function behavior."""

    def test_multiple_print_args(self):
        code = """
def decide_action(game_state: dict) -> dict:
    print("hello", "world", 123)
    return {"type": "check"}
"""
        gs = _make_basic_game_state()
        result = run_bot_action_fast(code, gs)
        assert result.ok
        assert "hello world 123" in result.logs

    def test_print_custom_sep(self):
        code = """
def decide_action(game_state: dict) -> dict:
    print("a", "b", "c", sep="-")
    return {"type": "check"}
"""
        gs = _make_basic_game_state()
        result = run_bot_action_fast(code, gs)
        assert result.ok
        assert "a-b-c" in result.logs

    def test_print_custom_end(self):
        code = """
def decide_action(game_state: dict) -> dict:
    print("line1", end="")
    print("line2")
    return {"type": "check"}
"""
        gs = _make_basic_game_state()
        result = run_bot_action_fast(code, gs)
        assert result.ok
        assert "line1line2" in result.logs
