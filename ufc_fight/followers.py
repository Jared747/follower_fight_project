from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import instaloader
from instaloader.exceptions import BadCredentialsException, ConnectionException, TwoFactorAuthRequiredException

from .settings import Settings, get_settings
from .storage import load_json, save_json

_LOADER: Optional[instaloader.Instaloader] = None


@dataclass
class Follower:
    username: str
    profile_pic: str


def _session_path(settings: Settings | None = None) -> Path:
    active = settings or get_settings()
    return Path(active.session_file)


def _refresh_login(loader: instaloader.Instaloader, username: str, password: Optional[str], session_path: Path) -> None:
    if not password:
        raise RuntimeError(
            f"Session file missing/invalid: {session_path}\n"
            "Set INSTAGRAM_PASSWORD (and INSTAGRAM_USERNAME if different) so the app can refresh the session "
            "automatically, or place a valid session file in the project root."
        )
    loader.login(username, password)
    loader.save_session_to_file(str(session_path))


def _get_loader(settings: Settings | None = None, force_refresh: bool = False) -> instaloader.Instaloader:
    """Load a single Instaloader instance, refreshing the session if needed."""
    settings = settings or get_settings()
    global _LOADER
    if _LOADER is not None and not force_refresh:
        return _LOADER

    loader = instaloader.Instaloader(
        sleep=True,
        max_connection_attempts=1,
        request_timeout=60,
    )

    session_path = _session_path(settings)
    username = settings.instagram_username
    password = settings.instagram_password

    if session_path.exists():
        try:
            loader.load_session_from_file(username, filename=str(session_path))
        except Exception:
            _refresh_login(loader, username, password, session_path)
    else:
        _refresh_login(loader, username, password, session_path)

    logged_in_as = loader.test_login()
    if logged_in_as != username:
        _refresh_login(loader, username, password, session_path)

    _LOADER = loader
    return loader


def _load_cached_followers(settings: Settings) -> List[Follower]:
    """Load cached followers from disk if avatars already exist."""
    usernames = set()
    cached = load_json(settings.follower_cache_path, [])
    if isinstance(cached, list):
        usernames.update(str(name).strip() for name in cached if str(name).strip())

    local_files = {path.stem for path in settings.profile_dir.glob("*.jpg")}
    usernames.update(local_files)

    followers: List[Follower] = []
    missing: List[str] = []
    for username in sorted(usernames):
        avatar_path = settings.profile_dir / f"{username}.jpg"
        if avatar_path.exists():
            followers.append(Follower(username=username, profile_pic=str(avatar_path)))
        else:
            missing.append(username)

    if followers and not missing:
        return followers

    if followers and missing:
        print(
            f"[cache] found {len(followers)} cached followers but {len(missing)} avatars are missing; refreshing...",
            flush=True,
        )
    return []


def get_followers(
    sleep_between: float = 0.25,
    max_followers: Optional[int] = None,
    settings: Settings | None = None,
    use_cache: bool = True,
    refresh: bool = False,
) -> List[Follower]:
    """Return followers using a persisted, reusable Instagram session."""
    settings = settings or get_settings()
    refresh = refresh or os.getenv("UFC_REFRESH_FOLLOWERS", "").lower() in {"1", "true", "yes", "y"}

    if use_cache and not refresh:
        cached = _load_cached_followers(settings)
        if cached:
            print(
                f"[cache] using {len(cached)} locally cached followers "
                "(set UFC_REFRESH_FOLLOWERS=1 to force a fresh fetch)",
                flush=True,
            )
            return cached

    loader = _get_loader(settings=settings)
    username = settings.instagram_username or DEFAULT_USERNAME

    try:
        profile = instaloader.Profile.from_username(loader.context, username)
        total = profile.followers or 0

        followers: List[Follower] = []
        backoff = 20

        for idx, it in enumerate(profile.get_followers(), start=1):
            while True:
                try:
                    uname = it.username
                    ppic = it.profile_pic_url
                    followers.append(Follower(username=uname, profile_pic=ppic))

                    if total:
                        print(f"[fetch {idx}/{total}] {uname}", flush=True)
                    else:
                        print(f"[fetch {idx}] {uname}", flush=True)

                    if max_followers and len(followers) >= max_followers:
                        return followers

                    if sleep_between > 0:
                        time.sleep(sleep_between)
                    backoff = 20
                    break

                except ConnectionException as exc:
                    msg = str(exc)
                    if "Please wait a few minutes before you try again" in msg:
                        print(f"[fetch paused] rate-limited; retrying in {backoff}s...", flush=True)
                        time.sleep(backoff)
                        backoff = min(backoff * 2, 600)
                        continue
                    raise

        return followers

    except (BadCredentialsException, TwoFactorAuthRequiredException) as exc:
        raise RuntimeError(f"Auth failed: {exc.__class__.__name__}: {exc}") from exc
    except ConnectionException as exc:
        msg = str(exc)
        if "Please wait a few minutes before you try again" in msg:
            raise RuntimeError(
                "Rate limited by Instagram. Reuse the session, confirm login in the app, enable 2FA, and retry later."
            ) from exc
        raise RuntimeError(f"Connection error: {exc.__class__.__name__}: {exc}") from exc
    except Exception as exc:  # pragma: no cover - defensive fallback
        global _LOADER
        _LOADER = None
        raise RuntimeError(f"Failed to fetch followers: {exc.__class__.__name__}: {exc}") from exc
    finally:
        try:
            cached_list = locals().get("followers", [])
            if cached_list:
                save_json(settings.follower_cache_path, sorted({f.username for f in cached_list}))
        except Exception:
            pass


def download_profile_pics(
    followers: List[Follower],
    outdir: Path | None = None,
    skip_existing: bool = True,
    timeout: float = 30.0,
) -> None:
    """Download follower profile pictures to the configured directory."""
    outdir = outdir or get_settings().profile_dir
    outdir.mkdir(exist_ok=True)
    total = len(followers)

    for idx, follower in enumerate(followers, start=1):
        if not follower.username or not follower.profile_pic:
            raise RuntimeError(f"Invalid follower record: {follower}")

        dest = outdir / f"{follower.username}.jpg"

        if skip_existing and dest.exists():
            print(f"[skip {idx}/{total}] {follower.username} (already exists)", flush=True)
            continue

        try:
            with urlopen(follower.profile_pic, timeout=timeout) as response, open(dest, "wb") as handle:
                handle.write(response.read())
        except (HTTPError, URLError, TimeoutError) as exc:
            raise RuntimeError(
                f"Download failed for {follower.username} from {follower.profile_pic}: {exc.__class__.__name__}: {exc}"
            ) from exc

        print(f"[save {idx}/{total}] {follower.username}", flush=True)


if __name__ == "__main__":
    try:
        followers = get_followers(use_cache=False, refresh=True)
        download_profile_pics(followers, get_settings().profile_dir, skip_existing=True)
    except Exception as exc:  # pragma: no cover - CLI helper
        print(f"ERROR: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
