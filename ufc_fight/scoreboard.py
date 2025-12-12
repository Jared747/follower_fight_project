from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from .settings import Settings, get_settings
from .stats import revert_stats_with_battle
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
        order = int(fighter.get("order", 0)) or 0
        points_awarded = max(0, total - order + 1)
        if order == 1:
            points_awarded += 1  # winner bonus so first place is (total + 1) points
        entry = scoreboard.get(username, {"points": 0, "runs": 0})
        entry["points"] = entry.get("points", 0) + points_awarded
        entry["runs"] = entry.get("runs", 0) + 1
        scoreboard[username] = entry

    save_json(path, scoreboard)
    return scoreboard


def revert_last_run(settings: Settings | None = None) -> None:
    """Undo the last run: restore scoreboard/stats and delete the latest video."""
    settings = settings or get_settings()
    if not settings.last_run_path.exists():
        raise SystemExit("No last run data found. Run a battle first.")

    ranking: List[Dict[str, object]] = load_json(settings.last_run_path, [])
    if not ranking:
        raise SystemExit("Last run data is empty; nothing to revert.")

    # Prefer exact restore from backups when available.
    board_backup = load_json(settings.last_run_scoreboard_backup_path, None)
    stats_backup = load_json(settings.last_run_stats_backup_path, None)
    used_backup = False

    if board_backup is not None:
        save_json(settings.scoreboard_path, board_backup)
        used_backup = True
    if stats_backup is not None:
        save_json(settings.stats_path, stats_backup)
        used_backup = True

    if not used_backup:
        # Fallback: subtract the last run impact (scoreboard and stats) using ranking and damage log.
        total = len(ranking)
        scoreboard: Dict[str, Dict[str, int]] = load_json(settings.scoreboard_path, {})
        for fighter in ranking:
            username = str(fighter.get("username") or "").strip()
            if not username:
                continue
            order = int(fighter.get("order", 0) or 0)
            points_awarded = max(0, total - order + 1)
            if order == 1:
                points_awarded += 1

            entry = scoreboard.get(username, {"points": 0, "runs": 0})
            entry["points"] = max(0, entry.get("points", 0) - points_awarded)
            entry["runs"] = max(0, entry.get("runs", 0) - 1)

            if entry["points"] == 0 and entry["runs"] == 0:
                scoreboard.pop(username, None)
            else:
                scoreboard[username] = entry

        save_json(settings.scoreboard_path, scoreboard)

        damage_log = load_json(settings.last_run_damage_path, {})
        if damage_log:
            revert_stats_with_battle(ranking, damage_log, settings.stats_path)

    video_dir = settings.base_battles
    legacy_dir = Path("battles")
    candidates = sorted([path for path in video_dir.glob("battle_*.mp4")])
    if not candidates and legacy_dir.exists():
        candidates = sorted([path for path in legacy_dir.glob("battle_*.mp4")])
    if candidates:
        candidates[-1].unlink()

    settings.last_run_path.unlink(missing_ok=True)
    settings.last_run_damage_path.unlink(missing_ok=True)
    settings.last_run_scoreboard_backup_path.unlink(missing_ok=True)
    settings.last_run_stats_backup_path.unlink(missing_ok=True)

    print("Reverted last run: scoreboard/stats restored and latest battle video removed.")
