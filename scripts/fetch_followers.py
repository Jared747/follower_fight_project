from __future__ import annotations

import sys
import argparse
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ufc_fight.followers import Follower, download_profile_pics, get_followers
from ufc_fight.settings import get_settings

__all__ = ["Follower", "download_profile_pics", "get_followers", "main"]


def _apply_env_override() -> None:
    """Allow `--env dev|prod` or trailing `dev|prod` (e.g., `-- dev`)."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--env", dest="env_override", choices=["dev", "prod"])
    args, extras = parser.parse_known_args()

    env_override = args.env_override
    if not env_override:
        for token in extras:
            if token in {"dev", "prod"}:
                env_override = token
                break

    if env_override:
        os.environ["UFC_ENV"] = env_override


def main() -> None:
    _apply_env_override()
    settings = get_settings()
    followers = get_followers(settings=settings, use_cache=False, refresh=True)
    download_profile_pics(followers, settings.profile_dir, skip_existing=True)
    print(f"Updated follower cache at: {settings.follower_cache_path}")


if __name__ == "__main__":  # pragma: no cover - CLI helper
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
