Start fresh shell

```
C:\Python313\python.exe -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install moviepy numpy pillow python-dotenv instaloader
```

Instagram session (recommended): python 615_import_firefox_session.py -f ultimatefollowingchampionship-session
- Place your saved session in `sessions/` as `ultimatefollowingchampionship-session`, **or**
- Set `INSTAGRAM_USERNAME`, `INSTAGRAM_PASSWORD`, and optionally `INSTAGRAM_SESSION_FILE` to let the app refresh and cache the session automatically into `sessions/`.

Run the fight simulator and render a video:
```
python scripts/fight_battle.py
```
The mp4 will be written to `battles/<env>/` and the scoreboard to `data/<env>/scoreboard.json`.

Optional audio: place an mp3 named `fight_theme.mp3` under `assets/` to have the soundtrack play for the duration of the battle (ending 5s after the winner is shown).

Undo the last battle:
```
python scripts/revert_last_run.py
```
This subtracts the last fight's points/runs from the current env scoreboard (e.g., `data/dev/scoreboard.json`, `data/prod/scoreboard.json`) and deletes the most recent env battle video (e.g., `battles/dev/battle_*.mp4`).

Run the UFC web app (Streamlit):
```
streamlit run apps/web_app.py
# or override env without editing .env (both forms work):
# streamlit run apps/web_app.py -- dev
# streamlit run apps/web_app.py -- --env prod
```
You can log in by picking a follower handle, browse the leaderboard, view stats, customize your character, and buy power-ups. The app reads/writes env-scoped JSON files under `data/<env>/` (`scoreboard.json`, `stats.json`, `customizations.json`, `followers_cache.json`) and profile pictures under `follower_pp/`.

Environments:
- `.env` is auto-loaded; set `UFC_ENV=dev` (default) or `UFC_ENV=prod` to keep data and battle videos isolated (`data/<env>/`, `battles/<env>/`). Legacy top-level JSON files are treated as dev if present.
- Override per-run without editing `.env`: `python scripts/fight_battle.py --env prod` or `python scripts/revert_last_run.py --env prod`.
- Streamlit in prod: `$env:UFC_ENV='prod'; streamlit run apps/web_app.py` (or `streamlit run apps/web_app.py -- --env prod` / `-- prod`)

Deployment:
- AWS EC2 + Nginx + systemd guide: `deploy/aws-ec2.md`.
- Sync local code + prod data/profile images to EC2: `deploy/sync_to_ec2.ps1` (excludes `.env`, `.venv`, `battles/`, `sessions/`, `data/dev`, and other temp files).

## Project structure (refactored)
- `ufc_fight/` – core package (settings, storage, followers, simulation/video, scoreboard, stats).
- `apps/` – UI entrypoints (`web_app.py`, `streamlit_app.py`); run via `streamlit run apps/web_app.py` or `streamlit run apps/streamlit_app.py`.
- `scripts/` – CLI entrypoints (`fight_battle.py`, `revert_last_run.py`, `fetch_followers.py`, `fight_simulation.py`, `615_import_firefox_session.py`).
- `assets/` – media assets (e.g., `fight_theme.mp3`, `ufc_login_image.png`).
- `sessions/` – Instagram session files (default: `sessions/ultimatefollowingchampionship-session`).
- `data/<env>/` – runtime JSON data per environment (`scoreboard.json`, `stats.json`, `customizations.json`, `followers_cache.json`, `last_run_ranking.json`).
- Root now only carries essentials (`.env`, `README.md`, `config.py`).
