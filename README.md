# Hold ’Em Together

Web-based Texas Hold’em programming game (Flask) where players write a bot function and compete on a leaderboard.

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
flask --app holdem_together.app run --debug
```

Open `http://127.0.0.1:5000/`.

The background tournament worker starts automatically with the Flask app.

## Configuration

Optional config via env vars:
- `HOLD_EM_SEATS` (default `6`) – players per match
- `HOLD_EM_HANDS` (default `50`) – hands per match
- `HOLD_EM_SLEEP_S` (default `2.0`) – seconds between matches
- `HOLD_EM_NO_WORKER=1` – disable the background worker

## Bot interface
Bots are Python and must define:

```python
def decide_action(game_state: dict) -> dict:
    return {"type": "check"}
```

Actions:
- `{ "type": "fold" }`
- `{ "type": "check" }`
- `{ "type": "call" }`
- `{ "type": "raise", "amount": 123 }` (MVP: `amount` is total-to for the current street)

## Plan
See `PLAN.md`.
