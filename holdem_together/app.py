from __future__ import annotations

import os
import random
import threading
import time

from flask import Flask

from .db import db
from .routes import bp


_worker_started = False
_worker_lock = threading.Lock()


def _run_background_worker(app: Flask) -> None:
    """Background thread that runs tournament matches."""
    from .background_runner import RunnerConfig, run_one_match

    seats = int(os.environ.get("HOLD_EM_SEATS", "6"))
    hands = int(os.environ.get("HOLD_EM_HANDS", "50"))
    sleep_s = float(os.environ.get("HOLD_EM_SLEEP_S", "2.0"))
    cfg = RunnerConfig(seats=seats, hands=hands, sleep_s=sleep_s)

    rng = random.Random()
    with app.app_context():
        while True:
            match_seed = rng.randint(1, 2_000_000_000)
            try:
                run_one_match(cfg=cfg, seed=match_seed)
            except Exception as e:
                app.logger.error(f"Background worker error: {e}")
            time.sleep(cfg.sleep_s)


def _start_background_worker(app: Flask) -> None:
    """Start the background worker thread if not already running."""
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        # Don't start worker during testing
        if app.config.get("TESTING"):
            return
        # Check env var to disable worker (useful for some deployments)
        if os.environ.get("HOLD_EM_NO_WORKER", "").lower() in ("1", "true", "yes"):
            return
        _worker_started = True
        thread = threading.Thread(target=_run_background_worker, args=(app,), daemon=True)
        thread.start()
        app.logger.info("Background tournament worker started")


def create_app(config_overrides: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="dev",
        SQLALCHEMY_DATABASE_URI="sqlite:///holdem_together.sqlite3",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )

    if config_overrides:
        app.config.update(config_overrides)

    db.init_app(app)
    app.register_blueprint(bp)

    with app.app_context():
        db.create_all()

        # Create a default user and baseline bot if empty.
        from .services import ensure_ratings_exist, ensure_seed_data

        ensure_seed_data()
        ensure_ratings_exist()

    # Start background worker thread
    _start_background_worker(app)

    return app


def main() -> None:
    """Entry point for the holdem_together command."""
    import argparse

    parser = argparse.ArgumentParser(description="Hold 'Em Together - Poker Bot Tournament")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--port", "-p", type=int, default=5000, help="Port to bind to (default: 5000)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    app = create_app()
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
