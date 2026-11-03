"""Shared configuration defaults for the perception package."""
from __future__ import annotations

import os

DEFAULT_AGENT_URL = os.getenv("AGENT_URL", "http://127.0.0.1:8000").rstrip("/")
DEFAULT_OUTBOX_DB = os.getenv("PERCEPTION_OUTBOX_DB", "data/outbox.db")
DEFAULT_EVENT_DB = os.getenv("PERCEPTION_EVENT_DB", "data/events.db")
DEFAULT_SNAPSHOT_DIR = os.getenv("PERCEPTION_SNAPSHOT_DIR", "data/snapshots")
