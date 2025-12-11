from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ufc_fight.video_battle import run_battle
from ufc_fight.settings import get_settings

__all__ = ["run_battle"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a follower battle video.")
    parser.add_argument(
        "--env",
        choices=["dev", "prod"],
        help="Override UFC_ENV for this run (defaults to value in .env or dev).",
    )
    args = parser.parse_args()

    if args.env:
        os.environ["UFC_ENV"] = args.env
        # Clear cached settings so the new environment takes effect.
        get_settings.cache_clear()

    run_battle()
