from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List

from .storage import load_json, save_json


def update_stats_with_battle(
    ranking: List[Dict[str, object]],
    damage_log: Dict[str, Dict[str, Dict[str, float]]],
    stats_path: Path,
) -> Dict[str, object]:
    """Update per-user stats based on ranking and damage log data."""
    stats = load_json(stats_path, {})
    now_ts = int(time.time())

    for fighter in ranking:
        username = str(fighter.get("username") or "").strip()
        if not username:
            continue
        entry = stats.get(
            username,
            {"matches": 0, "wins": 0, "total_damage_dealt": 0.0, "total_hits": 0, "damage_to": {}},
        )
        entry["matches"] = entry.get("matches", 0) + 1
        if fighter.get("order") == 1:
            entry["wins"] = entry.get("wins", 0) + 1
        entry["last_played"] = now_ts
        stats[username] = entry

    for attacker, targets in damage_log.items():
        entry = stats.get(attacker, {"matches": 0, "wins": 0, "total_damage_dealt": 0.0, "total_hits": 0, "damage_to": {}})
        for defender, info in targets.items():
            dmg = float(info.get("damage", 0.0))
            hits = int(info.get("hits", 0))
            entry["total_damage_dealt"] = entry.get("total_damage_dealt", 0.0) + dmg
            entry["total_hits"] = entry.get("total_hits", 0) + hits
            dmg_to = entry.get("damage_to", {})
            prev = dmg_to.get(defender, {"damage": 0.0, "hits": 0})
            prev["damage"] = prev.get("damage", 0.0) + dmg
            prev["hits"] = prev.get("hits", 0) + hits
            dmg_to[defender] = prev
            entry["damage_to"] = dmg_to
        stats[attacker] = entry

    for username, entry in stats.items():
        dmg_to = entry.get("damage_to", {})
        if dmg_to:
            rival = max(dmg_to.items(), key=lambda kv: kv[1].get("damage", 0.0))[0]
            entry["biggest_rival"] = rival
        else:
            entry["biggest_rival"] = ""
        stats[username] = entry

    save_json(stats_path, stats)
    return stats


def revert_stats_with_battle(
    ranking: List[Dict[str, object]],
    damage_log: Dict[str, Dict[str, Dict[str, float]]],
    stats_path: Path,
) -> Dict[str, object]:
    """Rollback the last battle's stats using the ranking and damage log."""
    stats = load_json(stats_path, {})

    for fighter in ranking:
        username = str(fighter.get("username") or "").strip()
        if not username or username not in stats:
            continue
        entry = stats.get(username, {})
        entry["matches"] = max(0, entry.get("matches", 0) - 1)
        if fighter.get("order") == 1:
            entry["wins"] = max(0, entry.get("wins", 0) - 1)
        stats[username] = entry

    for attacker, targets in damage_log.items():
        if attacker not in stats:
            continue
        entry = stats.get(attacker, {"matches": 0, "wins": 0, "total_damage_dealt": 0.0, "total_hits": 0, "damage_to": {}})
        for defender, info in targets.items():
            dmg = float(info.get("damage", 0.0))
            hits = int(info.get("hits", 0))
            entry["total_damage_dealt"] = max(0.0, entry.get("total_damage_dealt", 0.0) - dmg)
            entry["total_hits"] = max(0, entry.get("total_hits", 0) - hits)
            dmg_to = entry.get("damage_to", {})
            prev = dmg_to.get(defender, {"damage": 0.0, "hits": 0})
            prev["damage"] = max(0.0, prev.get("damage", 0.0) - dmg)
            prev["hits"] = max(0, prev.get("hits", 0) - hits)
            if prev["damage"] == 0.0 and prev["hits"] == 0:
                dmg_to.pop(defender, None)
            else:
                dmg_to[defender] = prev
            entry["damage_to"] = dmg_to
        stats[attacker] = entry

    for username, entry in list(stats.items()):
        dmg_to = entry.get("damage_to", {})
        if dmg_to:
            rival = max(dmg_to.items(), key=lambda kv: kv[1].get("damage", 0.0))[0]
            entry["biggest_rival"] = rival
        else:
            entry["biggest_rival"] = ""
        stats[username] = entry

    save_json(stats_path, stats)
    return stats
