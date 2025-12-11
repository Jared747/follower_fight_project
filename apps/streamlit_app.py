from __future__ import annotations

from typing import Dict

import streamlit as st

from ufc_fight.followers import get_followers
from ufc_fight.settings import get_settings
from ufc_fight.simulation import run_and_record
from ufc_fight.storage import load_json

settings = get_settings()


def load_scoreboard() -> Dict[str, Dict[str, int]]:
    """Load the scoreboard from disk or return an empty mapping."""
    return load_json(settings.scoreboard_path, {})


def display_leaderboard(scoreboard: Dict[str, Dict[str, int]]) -> None:
    """Render the leaderboard as a table sorted by points descending."""
    if not scoreboard:
        st.info("No fights have been run yet. Run today's fight to populate the leaderboard.")
        return
    sorted_board = sorted(scoreboard.items(), key=lambda item: item[1].get("points", 0), reverse=True)
    st.write("### Leaderboard")
    table_data = {
        "Position": [idx + 1 for idx in range(len(sorted_board))],
        "Username": [user for user, _ in sorted_board],
        "Points": [data.get("points", 0) for _, data in sorted_board],
        "Runs": [data.get("runs", 0) for _, data in sorted_board],
    }
    st.table(table_data)


def main() -> None:
    st.set_page_config(page_title="Follower Fight Club", page_icon="[Fight]", layout="centered")
    st.title("Follower Fight Club")
    st.write(
        "Welcome to your personalised fight club! Each day you can run a fight "
        "between all of your Instagram followers. Fighters earn points based on "
        "their finishing position: the winner receives as many points as there "
        "are fighters, the runner-up one less, and so on down to the last "
        "place fighter who still earns a single point."
    )

    scoreboard = load_scoreboard()

    if st.button("Run Today's Fight"):
        with st.spinner("Fetching followers and simulating fight..."):
            followers = get_followers(settings=settings)
            if not followers:
                st.error(
                    "No followers were returned. Please check your Instagram credentials "
                    "and ensure that the 'instaloader' package is installed."
                )
            else:
                ranking = run_and_record(followers, settings=settings)
                scoreboard = load_scoreboard()
                st.success("Fight complete! Today's ranking is:")
                result_table = {
                    "Position": [f["order"] for f in ranking],
                    "Username": [f["username"] for f in ranking],
                    "Final Health": [
                        round(f["final_health"], 2) if isinstance(f["final_health"], (int, float)) else "" for f in ranking
                    ],
                }
                st.table(result_table)

    display_leaderboard(scoreboard)


if __name__ == "__main__":
    main()
