from __future__ import annotations

import json
import sys
from types import MappingProxyType


def _main() -> int:
    raw = sys.stdin.read()
    payload = json.loads(raw)
    code = payload["code"]
    game_state = payload["game_state"]

    # Best-effort restrictions: no builtins like open, eval, exec, __import__.
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
    }

    globals_dict = {
        "__builtins__": MappingProxyType(safe_builtins),
    }
    locals_dict: dict = {}

    try:
        exec(code, globals_dict, locals_dict)  # noqa: S102
        decide_action = locals_dict.get("decide_action") or globals_dict.get("decide_action")
        if decide_action is None or not callable(decide_action):
            raise ValueError("Bot must define callable decide_action(game_state)")
        action = decide_action(game_state)
        if not isinstance(action, dict) or "type" not in action:
            raise ValueError("Action must be a dict with key 'type'")
        sys.stdout.write(json.dumps({"ok": True, "action": action}))
        return 0
    except Exception as e:  # noqa: BLE001
        sys.stdout.write(json.dumps({"ok": False, "error": str(e)}))
        return 0


if __name__ == "__main__":
    raise SystemExit(_main())
