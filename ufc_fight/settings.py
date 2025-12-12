from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root so UFC_ENV/PAYMENT_MODE/etc. are picked up for settings.
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    """Environment-scoped paths and runtime configuration."""

    env: str
    assets_dir: Path
    base_data: Path
    base_battles: Path
    scoreboard_path: Path
    stats_path: Path
    custom_path: Path
    last_run_path: Path
    last_run_damage_path: Path
    last_run_scoreboard_backup_path: Path
    last_run_stats_backup_path: Path
    follower_cache_path: Path
    profile_dir: Path
    sound_path: Path
    login_image_path: Path
    session_file: Path
    payment_mode: str
    stripe_secret_key: str
    instagram_username: str
    instagram_password: str | None


def _env_json_path(env: str, base_data: Path, name: str) -> Path:
    """Return the env-scoped JSON path, falling back to legacy dev files."""
    path = base_data / f"{name}.json"
    if env == "dev":
        legacy = Path(f"{name}.json")
        if legacy.exists() and not path.exists():
            return legacy
    return path


@lru_cache()
def get_settings() -> Settings:
    """Load settings once per process."""
    env = os.getenv("UFC_ENV", "dev").lower()

    assets_dir = Path("assets")
    assets_dir.mkdir(parents=True, exist_ok=True)

    base_data = Path("data") / env
    base_battles = Path("battles") / env
    base_data.mkdir(parents=True, exist_ok=True)
    base_battles.mkdir(parents=True, exist_ok=True)

    payment_mode = os.getenv("PAYMENT_MODE", "dev").lower()
    session_root = Path("sessions")
    session_root.mkdir(parents=True, exist_ok=True)
    session_file_name = os.getenv("INSTAGRAM_SESSION_FILE", "ultimatefollowingchampionship-session")

    return Settings(
        env=env,
        assets_dir=assets_dir,
        base_data=base_data,
        base_battles=base_battles,
        scoreboard_path=_env_json_path(env, base_data, "scoreboard"),
        stats_path=_env_json_path(env, base_data, "stats"),
        custom_path=_env_json_path(env, base_data, "customizations"),
        last_run_path=_env_json_path(env, base_data, "last_run_ranking"),
        last_run_damage_path=_env_json_path(env, base_data, "last_run_damage"),
        last_run_scoreboard_backup_path=_env_json_path(env, base_data, "last_run_scoreboard_backup"),
        last_run_stats_backup_path=_env_json_path(env, base_data, "last_run_stats_backup"),
        follower_cache_path=_env_json_path(env, base_data, "followers_cache"),
        profile_dir=Path("follower_pp"),
        sound_path=assets_dir / "fight_theme.mp3",
        login_image_path=assets_dir / "ufc_login_image.png",
        session_file=session_root / session_file_name,
        payment_mode=payment_mode,
        stripe_secret_key=os.getenv("STRIPE_SECRET_KEY", ""),
        instagram_username=os.getenv("INSTAGRAM_USERNAME", "ultimatefollowerschampionship"),
        instagram_password=os.getenv("INSTAGRAM_PASSWORD"),
    )
