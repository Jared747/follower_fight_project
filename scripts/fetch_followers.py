from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ufc_fight.followers import Follower, download_profile_pics, get_followers
from ufc_fight.settings import get_settings

__all__ = ["Follower", "download_profile_pics", "get_followers", "main"]


def main() -> None:
    settings = get_settings()
    followers = get_followers(settings=settings, use_cache=False, refresh=True)
    download_profile_pics(followers, settings.profile_dir, skip_existing=True)


if __name__ == "__main__":  # pragma: no cover - CLI helper
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
