from __future__ import annotations

from ufc_fight.settings import get_settings

_settings = get_settings()

ENV = _settings.env
BASE_DATA = _settings.base_data
BASE_BATTLES = _settings.base_battles
SCOREBOARD_PATH = _settings.scoreboard_path
STATS_PATH = _settings.stats_path
CUSTOM_PATH = _settings.custom_path
LAST_RUN_PATH = _settings.last_run_path
FOLLOWER_CACHE_PATH = _settings.follower_cache_path
BATTLES_DIR = _settings.base_battles
PAYMENT_MODE = _settings.payment_mode
STRIPE_SECRET_KEY = _settings.stripe_secret_key
