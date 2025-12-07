"""
fight_simulation.py
====================

This module provides the core logic for simulating a daily fight between
an Instagram account's followers and maintaining a simple ranking of
results.  The simulation itself is deliberately simple: each time the
fight is run all fighters start with full health.  Random pairs of
fighters are selected to trade blows until only a single fighter
remains.  Points are awarded based upon finishing position and
accumulated in a persistent scoreboard file.

The intention is for this module to be used both from a command line
script and from a Streamlit webapp.  It has no external dependencies
outside of the Python standard library.

Key functions:

``run_fight(followers)``
    Given a list of followers (each represented as a dictionary
    containing at least a ``username`` key) this function runs a
    randomized fight.  Fighters are paired up at random and each
    exchange results in a random amount of health being lost.  When
    a fighter's health drops to zero or below they are removed from
    the fight.  The function returns a list of fighters ordered
    from winner (position 1) through last place.

``update_scoreboard(ranking, scoreboard_path)``
    Takes the ranking returned by ``run_fight`` and updates a
    persistent JSON scoreboard.  The scoring formula awards
    ``total_fighters - position + 1`` points to a fighter for the
    current fight, ensuring that even last place earns at least
    one point while the winner earns ``total_fighters`` points.
    A ``runs`` counter is also maintained for each user.

The scoreboard file is stored as a JSON dictionary mapping
usernames to dictionaries with ``points`` and ``runs`` keys.  If
the file does not exist it will be created automatically.

Note: because the simulation uses random numbers the outcome will
differ on each run.  If deterministic results are desired for
testing, set ``random.seed(some_value)`` before calling
``run_fight``.
"""

from __future__ import annotations

import json
import os
import random
from typing import Dict, List, Iterable, Optional


def run_fight(followers: Iterable[Dict[str, str]]) -> List[Dict[str, object]]:
    """Simulate a fight among an iterable of followers.

    Each follower is expected to be a mapping with at least a
    ``username`` key.  If a ``profile_pic`` or other metadata is
    included it will be copied into the resulting ranking.

    The simulation operates as follows:

    * Every fighter starts with 100 health points.
    * While more than one fighter remains, pick two distinct fighters
      at random.  Both fighters inflict random damage on one another.
      The damage inflicted ranges between 5 and 30 health points.
    * If a fighter's health drops to zero or below they are removed
      from the list of active fighters and appended to the ranking
      list with their finishing position assigned at the end.
    * Once only a single fighter remains, that fighter is the
      winner and is appended to the ranking.

    The returned ranking list is ordered such that the first element
    has ``order`` 1 (winner), the second element has order 2, and so on.

    :param followers: iterable of follower data mappings
    :return: list of fighter dicts with ``order``, ``username``,
             ``profile_pic``, and ``final_health`` keys
    """
    # Prepare internal list of fighters with health
    fighters: List[Dict[str, object]] = []
    for follower in followers:
        # ensure we copy necessary fields and start with full health
        fighters.append({
            "username": follower.get("username"),
            "profile_pic": follower.get("profile_pic"),
            "health": 100.0,
        })

    # We'll build the ranking by popping eliminated fighters
    ranking: List[Dict[str, object]] = []

    # Continue until only one fighter remains
    while len(fighters) > 1:
        # Pick two distinct fighters at random
        i, j = random.sample(range(len(fighters)), 2)
        fighter_a = fighters[i]
        fighter_b = fighters[j]

        # Random damage values for each fighter (5 to 30)
        damage_a = random.randint(5, 30)
        damage_b = random.randint(5, 30)

        fighter_a["health"] -= damage_b  # fighter_b hits fighter_a
        fighter_b["health"] -= damage_a  # fighter_a hits fighter_b

        # Remove and record any fighters whose health has fallen to 0 or below
        # We remove the higher index first to avoid invalidating indices
        for idx in sorted([i, j], reverse=True):
            if fighters[idx]["health"] <= 0:
                eliminated = fighters.pop(idx)
                ranking.append(eliminated)

    # Add the remaining fighter as the winner
    if fighters:
        ranking.append(fighters[0])

    # Reverse ranking so winner comes first
    ranking.reverse()

    # Annotate with finishing order and final health
    for position, fighter in enumerate(ranking, start=1):
        fighter["order"] = position
        # rename health to final_health for clarity
        fighter["final_health"] = fighter.pop("health", None)

    return ranking


def update_scoreboard(ranking: List[Dict[str, object]], scoreboard_path: str = "scoreboard.json") -> None:
    """Update the persistent scoreboard with results from the latest fight.

    Points are awarded based upon finishing position such that the
    winner receives ``n`` points (where ``n`` is the number of
    participants in the fight), the runner-up receives ``n - 1``
    points, down to the last place fighter who still receives 1
    point.  This scoring system ensures that larger fights award
    proportionally more points while still rewarding participation.

    If the scoreboard file does not yet exist it will be created.

    :param ranking: list of fighters returned by ``run_fight``
    :param scoreboard_path: filesystem path to the JSON scoreboard
    """
    total = len(ranking)

    # Load existing scoreboard if present
    if os.path.isfile(scoreboard_path):
        with open(scoreboard_path, "r", encoding="utf-8") as f:
            try:
                scoreboard = json.load(f)
            except json.JSONDecodeError:
                scoreboard = {}
    else:
        scoreboard = {}

    # Update points and runs for each fighter
    for fighter in ranking:
        username = str(fighter.get("username"))
        if not username:
            continue
        points_awarded = total - fighter["order"] + 1
        entry = scoreboard.get(username, {"points": 0, "runs": 0})
        entry["points"] = entry.get("points", 0) + points_awarded
        entry["runs"] = entry.get("runs", 0) + 1
        scoreboard[username] = entry

    # Write scoreboard back to disk
    with open(scoreboard_path, "w", encoding="utf-8") as f:
        json.dump(scoreboard, f, indent=2)
