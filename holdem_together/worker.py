from __future__ import annotations

import os

from .app import create_app
from .background_runner import RunnerConfig, run_forever


def main() -> None:
    seats = int(os.environ.get("HOLD_EM_SEATS", "6"))
    hands = int(os.environ.get("HOLD_EM_HANDS", "50"))
    sleep_s = float(os.environ.get("HOLD_EM_SLEEP_S", "2.0"))

    app = create_app()
    with app.app_context():
        run_forever(RunnerConfig(seats=seats, hands=hands, sleep_s=sleep_s))


if __name__ == "__main__":
    main()
