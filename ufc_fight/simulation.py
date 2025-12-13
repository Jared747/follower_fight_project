from __future__ import annotations

import random
from typing import Dict, Iterable, List, Mapping

from .scoreboard import update_scoreboard
from .settings import Settings, get_settings
from .storage import save_json

DEFAULT_HEALTH = 100.0
# Keep manual HP overrides tiny so results stay believable.
HEALTH_OVERRIDES: Dict[str, float] = {
}


def run_fight(followers: Iterable[Mapping[str, object]]) -> List[Dict[str, object]]:
    """Simulate an elimination fight among followers (non-visual)."""
    fighters: List[Dict[str, object]] = []
    for follower in followers:
        username = follower.get("username")
        base_health = HEALTH_OVERRIDES.get(str(username), DEFAULT_HEALTH)
        fighters.append(
            {
                "username": username,
                "profile_pic": follower.get("profile_pic"),
                "health": base_health,
            }
        )

    ranking: List[Dict[str, object]] = []

    while len(fighters) > 1:
        i, j = random.sample(range(len(fighters)), 2)
        fighter_a = fighters[i]
        fighter_b = fighters[j]

        damage_a = random.randint(5, 30)
        damage_b = random.randint(5, 30)

        fighter_a["health"] -= damage_b
        fighter_b["health"] -= damage_a

        for idx in sorted([i, j], reverse=True):
            if fighters[idx]["health"] <= 0:
                eliminated = fighters.pop(idx)
                ranking.append(eliminated)

    if fighters:
        ranking.append(fighters[0])

    ranking.reverse()

    for position, fighter in enumerate(ranking, start=1):
        fighter["order"] = position
        fighter["final_health"] = fighter.pop("health", None)

    return ranking


def run_and_record(
    followers: Iterable[Mapping[str, object]],
    settings: Settings | None = None,
) -> List[Dict[str, object]]:
    """Run the non-visual fight, update the scoreboard, and persist the run."""
    settings = settings or get_settings()
    ranking = run_fight(followers)
    update_scoreboard(ranking, settings.scoreboard_path)
    save_json(settings.last_run_path, ranking)
    return ranking
