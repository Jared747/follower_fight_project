from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ufc_fight.scoreboard import revert_last_run
from ufc_fight.settings import get_settings

__all__ = ["revert_last_run"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Undo the last run for the selected environment.")
    parser.add_argument(
        "--env",
        choices=["dev", "prod"],
        help="Override UFC_ENV for this revert (defaults to value in .env or dev).",
    )
    args = parser.parse_args()

    if args.env:
        os.environ["UFC_ENV"] = args.env
        get_settings.cache_clear()

    revert_last_run()
