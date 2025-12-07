from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

import instaloader
from instaloader.exceptions import (
    ConnectionException,
    BadCredentialsException,
    TwoFactorAuthRequiredException,
)


USERNAME = "ultimatefollowerschampionship"
SESSION_FILE = "ultimatefollowingchampionship-session"


@dataclass
class Follower:
    username: str
    profile_pic: str


def get_followers(sleep_between: float = 2.0) -> List[Follower]:
    L = instaloader.Instaloader(
        sleep=True,
        max_connection_attempts=1,
        request_timeout=60,
    )

    session_path = Path(__file__).with_name(SESSION_FILE)

    if not session_path.exists():
        raise RuntimeError(
            f"Session file not found: {session_path}\n"
            f"Make sure '{SESSION_FILE}' is in the same folder as fetch_followers.py."
        )

    # Correct usage: first param = username, second param = path to session file
    L.load_session_from_file(USERNAME, filename=str(session_path))

    try:
        profile = instaloader.Profile.from_username(L.context, USERNAME)
        total = profile.followers or 0

        followers: List[Follower] = []
        i = 0
        backoff = 20

        for it in profile.get_followers():
            while True:
                try:
                    uname = it.username
                    ppic = it.profile_pic_url
                    followers.append(Follower(username=uname, profile_pic=ppic))
                    i += 1

                    if total:
                        print(f"[fetch {i}/{total}] {uname}", flush=True)
                    else:
                        print(f"[fetch {i}] {uname}", flush=True)

                    time.sleep(sleep_between)
                    backoff = 20
                    break

                except ConnectionException as e:
                    msg = str(e)
                    if "Please wait a few minutes before you try again" in msg:
                        print(
                            f"[fetch paused] rate-limited; retrying in {backoff}s...",
                            flush=True,
                        )
                        time.sleep(backoff)
                        backoff = min(backoff * 2, 600)
                        continue
                    raise

        return followers

    except (BadCredentialsException, TwoFactorAuthRequiredException) as e:
        raise RuntimeError(f"Auth failed: {e.__class__.__name__}: {e}") from e
    except ConnectionException as e:
        msg = str(e)
        if "Please wait a few minutes before you try again" in msg:
            raise RuntimeError(
                "Rate limited by Instagram. Reuse the session, stable IP, confirm login in the app, "
                "enable 2FA, and retry later."
            ) from e
        raise RuntimeError(f"Connection error: {e.__class__.__name__}: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Failed to fetch followers: {e.__class__.__name__}: {e}") from e


def download_profile_pics(
    followers: List[Follower],
    outdir: Path,
    skip_existing: bool = True,
    timeout: float = 30.0,
) -> None:
    outdir.mkdir(exist_ok=True)
    total = len(followers)

    for i, f in enumerate(followers, start=1):
        if not f.username or not f.profile_pic:
            raise RuntimeError(f"Invalid follower record: {f}")

        dest = outdir / f"{f.username}.jpg"

        if skip_existing and dest.exists():
            print(f"[skip {i}/{total}] {f.username} (already exists)", flush=True)
            continue

        try:
            with urlopen(f.profile_pic, timeout=timeout) as r, open(dest, "wb") as out:
                out.write(r.read())
        except (HTTPError, URLError, TimeoutError) as e:
            raise RuntimeError(
                f"Download failed for {f.username} from {f.profile_pic}: "
                f"{e.__class__.__name__}: {e}"
            ) from e

        print(f"[save {i}/{total}] {f.username}", flush=True)


if __name__ == "__main__":
    try:
        followers = get_followers()
        download_profile_pics(followers, Path("follower_pp"), skip_existing=True)
    except Exception as e:
        print(f"ERROR: {e.__class__.__name__}: {e}", file=sys.stderr)
        sys.exit(1)
from typing import Dict