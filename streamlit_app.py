"""
streamlit_app.py
=================

A simple Streamlit application providing a graphical interface for
running the daily follower fight and viewing the leaderboard.  The
application exposes two main pieces of functionality:

* A "Run Today's Fight" button that, when pressed, retrieves the
  current follower list (via ``fetch_followers.get_followers``),
  performs a simulated fight (via ``fight_simulation.run_fight``),
  updates the persistent scoreboard, and displays the results of
  today's fight.
* A leaderboard view that displays the cumulative points and number
  of runs for each participant, sorted by total points.

Before running this application make sure to install the required
packages:

    pip install streamlit instaloader

If you wish to fetch real followers from Instagram you must also
set the ``INSTAGRAM_USERNAME`` and ``INSTAGRAM_PASSWORD`` environment
variables (or pass them directly via the ``get_followers`` function
in ``fetch_followers``).

To run locally, execute:

    streamlit run streamlit_app.py

"""

from __future__ import annotations

import json
import os
from typing import Dict, List

import streamlit as st

from fetch_followers import get_followers
from fight_simulation import run_fight, update_scoreboard


SCOREBOARD_PATH = "scoreboard.json"


def load_scoreboard(path: str = SCOREBOARD_PATH) -> Dict[str, Dict[str, int]]:
    """Load the scoreboard from disk or return an empty mapping."""
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}


def display_leaderboard(scoreboard: Dict[str, Dict[str, int]]) -> None:
    """Render the leaderboard as a table sorted by points descending."""
    if not scoreboard:
        st.info("No fights have been run yet. Run today's fight to populate the leaderboard.")
        return
    # Convert scoreboard dict to a sorted list of (username, data) tuples
    sorted_board = sorted(scoreboard.items(), key=lambda item: item[1].get("points", 0), reverse=True)
    st.write("### Leaderboard")
    # Build a simple table using Streamlit's built-in functionality
    table_data = {
        "Position": [idx + 1 for idx in range(len(sorted_board))],
        "Username": [user for user, _ in sorted_board],
        "Points": [data.get("points", 0) for _, data in sorted_board],
        "Runs": [data.get("runs", 0) for _, data in sorted_board],
    }
    st.table(table_data)


def main() -> None:
    st.set_page_config(page_title="Follower Fight Club", page_icon="🥊", layout="centered")
    st.title("Follower Fight Club")
    st.write(
        "Welcome to your personalised fight club! Each day you can run a fight "
        "between all of your Instagram followers. Fighters earn points based on "
        "their finishing position: the winner receives as many points as there "
        "are fighters, the runner-up one less, and so on down to the last "
        "place fighter who still earns a single point."
    )

    # Load current scoreboard
    scoreboard = load_scoreboard()

    # Button to run the daily fight
    if st.button("Run Today's Fight"):
        with st.spinner("Fetching followers and simulating fight…"):
            # Retrieve follower list
            followers = get_followers()
            if not followers:
                st.error(
                    "No followers were returned. Please check your Instagram credentials "
                    "and ensure that the 'instaloader' package is installed."
                )
            else:
                # Run the simulation
                ranking = run_fight(followers)
                # Update scoreboard file
                update_scoreboard(ranking, SCOREBOARD_PATH)
                # Reload scoreboard to reflect changes
                scoreboard = load_scoreboard()
                # Display results of today's fight
                st.success("Fight complete! Today's ranking is:")
                result_table = {
                    "Position": [f["order"] for f in ranking],
                    "Username": [f["username"] for f in ranking],
                    "Final Health": [round(f["final_health"], 2) if isinstance(f["final_health"], (int, float)) else "" for f in ranking],
                }
                st.table(result_table)

    # Always display leaderboard below
    display_leaderboard(scoreboard)


if __name__ == "__main__":
    main()
