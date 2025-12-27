# Hold ’Em Together — Implementation Plan (MVP → v1)

## Goal
A web-based Texas Hold’em programming game where players submit a Python bot function:

- Input: a **bot-visible game state** (JSON-serializable)
- Output: one legal action: `fold`, `check`, `call`, or `raise`

Submitted bots compete in the background against other bots. The leaderboard ranks bots by performance.

## Confirmed Requirements (as of 2025-12-19)
- **Poker variant**: Texas Hold’em
- **Table format**: **multi-player** table (more than 2 bots)
- **Betting**: **no-limit**
- **Information**: bots see their **hole cards + board + bet history + stacks**; bots **do not** see opponents’ hole cards
- **Web**: Flask backend; **web UI includes a basic development environment** so players can program from the browser
- **Hand strength helper**: game state includes an evaluation of the bot’s hand strength so users don’t need deep poker knowledge

## MVP Assumptions (explicit; can be adjusted)
These keep the first version shippable.

### Core gameplay
- **Seats**: configurable table size (start with 6)
- **Stacks/blinds**: fixed initial stack and blinds (e.g., 100 BB)
- **Dealer rotation**: rotates each hand
- **Hand lifecycle**: preflop → flop → turn → river → showdown (or earlier fold)

### No-limit betting (MVP rules)
- **Actions**: `fold`, `check`, `call`, `raise(amount)`
- **Raise semantics**: `amount` is total bet size for this street (or a delta); pick one and document consistently.
- **Legal raise**: at least min-raise (previous raise size) and at most player’s remaining stack (all-in)
- **All-in & side pots**: supported (required for multi-player)

### Determinism & reproducibility
- Every hand and match uses a **seeded RNG**, recorded with match results.

## Bot Interface

### Required function
Bots submit Python code that defines:

```python
def decide_action(game_state: dict) -> dict:
    # return one of:
    # {"type": "fold"}
    # {"type": "check"}
    # {"type": "call"}
    # {"type": "raise", "amount": 123}
    ...
```

### Bot-visible `game_state` (high-level)
The state is JSON and contains:
- `hand_id`, `street`, `dealer_seat`, `actor_seat`
- `hole_cards` (actor only)
- `board_cards`
- `stacks` (per seat)
- `contributed_this_street`, `contributed_total`
- `pot` and `side_pots`
- `action_history` (sequence of actions with seat + amounts)
- `legal_actions` (server-computed list, including raise bounds)

### Hand strength fields (server-computed)
To reduce required poker expertise, include:
- `hand_strength.category`: e.g., `high_card`, `pair`, `two_pair`, …
- `hand_strength.rank`: a comparable rank value for the best 5-card hand out of 7
- `hand_strength.equity_estimate`: optional Monte Carlo equity estimate vs random opponent ranges (seeded, fixed samples)

Notes:
- Equity is computed **server-side**; bots can read it but don’t compute it.
- Keep equity sampling small for MVP (e.g., 200–500) and cache per (hole, board, players, dead cards, seed).

## Architecture

### Components
1. **Flask web app**
   - auth-lite (username) or simple sessions
   - bot editor + submission
   - leaderboard + match history
2. **Poker engine**
   - table state machine + betting logic + side pots
   - deterministic dealing (seed)
   - showdown resolution with evaluator
3. **Hand evaluator + equity**
   - fast 7-card evaluator (category + rank)
   - optional Monte Carlo equity helper
4. **Sandbox runner**
   - execute bots in a separate OS process with timeouts
   - restricted environment (no network/files) as best-effort
5. **Background worker**
   - runs matches continuously (round robin / scheduled)
   - persists results and updates ratings

### Persistence (SQLite for MVP)
- `users`: id, name
- `bots`: id, user_id, name, code, created_at, status, last_error
- `bot_versions`: id, bot_id, code_hash, code, created_at
- `matches`: id, seed, started_at, finished_at, config_json
- `match_results`: match_id, bot_id, placement, chips_won, hands_played
- `ratings`: bot_id, rating, rd/uncertainty (optional), updated_at

## Web UI (MVP)
- **/ (Home)**: leaderboard + “Create/Select Bot”
- **/bots/new**: create bot
- **/bots/<id>**: in-browser editor (textarea first; CodeMirror later), validate, submit
- **/matches**: recent matches (summary)
- **/matches/<id>**: match details (seed, bots, placements, per-hand logs (optional))

## Background Competition Format
- Run repeated “tables” consisting of N hands with fixed seed sequence.
- Rotate seating assignments to reduce positional bias.
- Score bots by chips won per hand / tournament placements.
- Update leaderboard with a rating system:
  - MVP: Elo on head-to-head derived from placements
  - v1: TrueSkill-like or Bayesian rating with uncertainty

## Safety / Sandbox (MVP constraints)
- Run each bot decision in a subprocess with:
  - hard time limit (e.g., 50–200ms per decision)
  - memory cap (best-effort)
  - no outbound network (best-effort)
- On bot error/timeout: fallback to safe action (prefer `check` if legal else `fold`).

## Milestones

### Milestone A — Runnable skeleton
- Flask app starts
- Create bot, edit code in browser, submit
- A “demo match” runs against baseline bots

### Milestone B — Real no-limit engine
- Multi-player betting with side pots and all-ins
- Deterministic simulation with recorded seeds
- Hand evaluator integrated

### Milestone C — Tournament worker
- Background queue runs matches continuously
- Persist results, compute ratings, show leaderboard

### Milestone D — Hand strength helper
- Category + rank always
- Optional equity estimate with caching

## Status (as of 2025-12-20)

### MVP done
- Flask app + server-rendered UI: leaderboard, bot editor, match list/detail
- Bot submission pipeline: validate, submit, versioning
- Real multi-player no-limit engine: blinds, betting rounds, all-ins + side pots, showdown
- Determinism: seeded RNG recorded with each match
- Hand strength helper: made-hand category/rank + seeded Monte Carlo equity estimate (cached)
- Background worker: continuously runs matches, persists results, updates Elo-like ratings
- Sandbox runner: subprocess + timeout + restricted builtins/import allowlist (best-effort)
- Observability: captures bot stdout/errors and persists per-match bot logs; match detail shows them
- Positional bias reduction (MVP): deterministic seat shuffling per match seed (demo shuffles opponents)

### Differences vs the original persistence sketch
The original table list below was a sketch; the current DB is intentionally simpler for MVP:
- `matches` currently stores: `created_at`, `seed`, `hands`, `seats`, `status`, `error` (no `started_at/finished_at/config_json` yet)
- `match_results` stores: `seat`, `chips_won`, `hands_played` (no explicit `placement` column; placement is derived by sorting chips)
- Ratings store: `rating`, `matches_played` (no uncertainty/`updated_at` yet)
- Added: `match_bot_logs` to store per-match per-seat bot stdout/errors

### Next v1 items (not MVP)
- Stronger sandboxing (container/OS-level isolation + resource limits)
- Persist per-hand state/actions for true replay UI (current match detail shows aggregated bot logs)
- Smarter scheduling (round-robin/avoid repeats, exploration/exploitation)
- Migrations (Alembic) for evolving DB schema safely

## Open Questions (to decide when implementing engine)
- Raise `amount` meaning: total-to vs incremental raise
- Exact min-raise rule implementation and edge cases with all-ins
- Table size default (6? 9?)
- Match scoring: chips won, placements, or both
- Any anti-collusion rules (future)
