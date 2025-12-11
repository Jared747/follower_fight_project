from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from .settings import Settings, get_settings
from .storage import load_json, save_json


def update_scoreboard(
    ranking: List[Dict[str, object]],
    scoreboard_path: Path | None = None,
) -> Dict[str, Dict[str, int]]:
    """Update cumulative points and runs based on the latest ranking."""
    settings = get_settings()
    path = scoreboard_path or settings.scoreboard_path

    scoreboard: Dict[str, Dict[str, int]] = load_json(path, {})
    total = len(ranking)

    for fighter in ranking:
        username = str(fighter.get("username") or "").strip()
        if not username:
            continue
        points_awarded = total - int(fighter.get("order", 0)) + 1
        entry = scoreboard.get(username, {"points": 0, "runs": 0})
        entry["points"] = entry.get("points", 0) + points_awarded
        entry["runs"] = entry.get("runs", 0) + 1
        scoreboard[username] = entry

    save_json(path, scoreboard)
    return scoreboard


def revert_last_run(settings: Settings | None = None) -> None:
    """Undo the last run's scoreboard impact and delete the latest video."""
    settings = settings or get_settings()
    if not settings.last_run_path.exists():
        raise SystemExit("No last run data found. Run a battle first.")
    if not settings.scoreboard_path.exists():
        raise SystemExit("No scoreboard found to adjust.")

    ranking: List[Dict[str, object]] = load_json(settings.last_run_path, [])
    total = len(ranking)
    if total == 0:
        raise SystemExit("Last run data is empty; nothing to revert.")

    scoreboard: Dict[str, Dict[str, int]] = load_json(settings.scoreboard_path, {})

    for fighter in ranking:
        username = str(fighter.get("username") or "").strip()
        if not username:
            continue
        order = int(fighter.get("order", 0) or 0)
        points_awarded = total - order + 1

        entry = scoreboard.get(username, {"points": 0, "runs": 0})
        entry["points"] = max(0, entry.get("points", 0) - points_awarded)
        entry["runs"] = max(0, entry.get("runs", 0) - 1)

        if entry["points"] == 0 and entry["runs"] == 0:
            scoreboard.pop(username, None)
        else:
            scoreboard[username] = entry

    save_json(settings.scoreboard_path, scoreboard)

    video_dir = settings.base_battles
    legacy_dir = Path("battles")
    candidates = sorted([path for path in video_dir.glob("battle_*.mp4")])
    if not candidates and legacy_dir.exists():
        candidates = sorted([path for path in legacy_dir.glob("battle_*.mp4")])
    if candidates:
        candidates[-1].unlink()

    settings.last_run_path.unlink(missing_ok=True)

    print("Reverted last run: scoreboard adjusted and latest battle video removed.")
