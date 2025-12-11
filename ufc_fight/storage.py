from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


def load_json(path: Path, default: Any):
    """Load JSON with a fallback value on missing/invalid content."""
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except json.JSONDecodeError:
            return copy.deepcopy(default)
    return copy.deepcopy(default)


def save_json(path: Path, data: Any) -> None:
    """Persist JSON to disk, ensuring the parent directory exists."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
