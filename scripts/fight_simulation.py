from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Iterable, List, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ufc_fight.simulation import run_and_record, run_fight
from ufc_fight.scoreboard import update_scoreboard

__all__ = ["run_fight", "run_and_record", "update_scoreboard"]
