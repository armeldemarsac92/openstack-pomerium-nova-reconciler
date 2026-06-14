from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from mustelinet_reconciler.config.settings import Settings


def load_settings(path: str | Path) -> Settings:
    with Path(path).open("r", encoding="utf-8") as handle:
        raw: dict[str, Any] = yaml.safe_load(handle) or {}
    return Settings.model_validate(raw)
