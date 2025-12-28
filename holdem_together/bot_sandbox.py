from __future__ import annotations

import builtins
import io
import json
import multiprocessing as mp
import textwrap
import traceback
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any


@dataclass(frozen=True)
class BotRunResult:
    ok: bool
    action: dict[str, Any] | None
    error: str | None
    logs: str | None


_REQUIRED_FN = "decide_action"

_ALLOWED_IMPORTS = {"math", "statistics"}


def _limited_import(name: str, globals=None, locals=None, fromlist=(), level: int = 0):  # noqa: ANN001
    # Disallow relative imports and any module outside allowlist.
    if level != 0:
        raise ImportError("Relative imports are not allowed")
    root = name.split(".", 1)[0]
    if root not in _ALLOWED_IMPORTS:
        raise ImportError(f"Import not allowed: {root}")
    return builtins.__import__(name, globals, locals, fromlist, level)


def _sandbox_globals(stdout_capture: io.StringIO):
    def _print(*args, **kwargs):  # noqa: ANN001
        sep = kwargs.get("sep", " ")
        end = kwargs.get("end", "\n")
        stdout_capture.write(sep.join(str(a) for a in args) + end)

    safe_builtins = {
        "abs": abs,
        "min": min,
        "max": max,
        "sum": sum,
        "len": len,
        "range": range,
        "enumerate": enumerate,
        "sorted": sorted,
        "round": round,
        "int": int,
        "float": float,
        "bool": bool,
        "str": str,
        "dict": dict,
        "list": list,
        "tuple": tuple,
        "set": set,
        "print": _print,
        "__import__": _limited_import,
    }

    return {"__builtins__": MappingProxyType(safe_builtins)}


def validate_bot_code(code: str) -> tuple[bool, str | None]:
    try:
        compiled = compile(code, "<bot>", "exec")
    except SyntaxError as e:
        return False, f"SyntaxError: {e.msg} (line {e.lineno})"

    try:
        out = io.StringIO()
        g = _sandbox_globals(out)
        exec(compiled, g, g)
    except Exception:
        return False, "Runtime error during import/exec:\n" + traceback.format_exc()

    fn = g.get(_REQUIRED_FN)
    if fn is None or not callable(fn):
        return False, f"Missing required function `{_REQUIRED_FN}(game_state: dict) -> dict`."

    return True, None


def _worker(code: str, game_state_json: str, q: mp.Queue) -> None:
    try:
        compiled = compile(code, "<bot>", "exec")
        stdout_capture = io.StringIO()
        g = _sandbox_globals(stdout_capture)
        exec(compiled, g, g)

        fn = g.get(_REQUIRED_FN)
        if fn is None or not callable(fn):
            raise ValueError(f"Missing required function `{_REQUIRED_FN}`")

        game_state = json.loads(game_state_json)

        action = fn(game_state)
        if not isinstance(action, dict):
            raise TypeError("Bot must return a dict action")

        q.put({"ok": True, "action": action, "logs": stdout_capture.getvalue()})
    except Exception:
        q.put({"ok": False, "error": traceback.format_exc()})


def run_bot_action_fast(code: str, game_state: dict[str, Any]) -> BotRunResult:
    """Run bot code in-process for maximum speed.

    This is used for demo matches where we trust the code (already validated)
    and want to avoid subprocess overhead. Not suitable for untrusted code
    in production since there's no timeout enforcement or isolation.
    """
    try:
        compiled = compile(textwrap.dedent(code), "<bot>", "exec")
        stdout_capture = io.StringIO()
        g = _sandbox_globals(stdout_capture)
        exec(compiled, g, g)

        fn = g.get(_REQUIRED_FN)
        if fn is None or not callable(fn):
            raise ValueError(f"Missing required function `{_REQUIRED_FN}`")

        action = fn(game_state)
        if not isinstance(action, dict):
            raise TypeError("Bot must return a dict action")

        return BotRunResult(ok=True, action=action, error=None, logs=stdout_capture.getvalue())
    except Exception:
        return BotRunResult(ok=False, action=None, error=traceback.format_exc(), logs=None)


def run_bot_action(code: str, game_state: dict[str, Any], timeout_s: float = 1.0) -> BotRunResult:
    """Run bot in a subprocess with a timeout.

    Note: This is best-effort isolation for MVP; production hardening requires OS sandboxing.
    The default timeout of 1.0s accounts for subprocess startup overhead (~100-200ms with forkserver)
    plus a reasonable margin for bot decision logic.
    """

    q: mp.Queue = mp.Queue()
    p = mp.Process(target=_worker, args=(textwrap.dedent(code), json.dumps(game_state), q))
    p.start()
    p.join(timeout=timeout_s)

    if p.is_alive():
        p.terminate()
        p.join(timeout=0.1)
        return BotRunResult(ok=False, action=None, error=f"Timeout after {timeout_s:.2f}s", logs=None)

    if q.empty():
        return BotRunResult(ok=False, action=None, error="No result from bot process", logs=None)

    msg = q.get()
    if msg.get("ok"):
        return BotRunResult(ok=True, action=msg.get("action"), error=None, logs=msg.get("logs"))

    return BotRunResult(ok=False, action=None, error=msg.get("error") or "Unknown error", logs=None)
