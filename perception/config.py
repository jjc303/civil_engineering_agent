"""Shared configuration defaults for the perception package."""
from __future__ import annotations

import os
from pathlib import Path

PERCEPTION_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PERCEPTION_ROOT.parent

DEFAULT_AGENT_URL = os.getenv("AGENT_URL", "http://127.0.0.1:8000").rstrip("/")
DEFAULT_OUTBOX_DB = os.getenv("PERCEPTION_OUTBOX_DB", "data/outbox.db")
DEFAULT_EVENT_DB = os.getenv("PERCEPTION_EVENT_DB", "data/events.db")
DEFAULT_SNAPSHOT_DIR = os.getenv("PERCEPTION_SNAPSHOT_DIR", "data/snapshots")
DEFAULT_DANGER_ZONES_PATH = Path(
    os.getenv(
        "PERCEPTION_DEFAULT_ZONES_PATH",
        str(PERCEPTION_ROOT / "configs" / "default_danger_zones.json"),
    )
)
DEFAULT_WEIGHTS_PATH = Path(
    os.getenv(
        "PERCEPTION_DEFAULT_WEIGHTS_PATH",
        str(PERCEPTION_ROOT / "weights" / "helmet_head_person_s.pt"),
    )
)
