"""
Tests for Perception CLI entrypoint (perception.cli).
"""

import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from perception.cli import build_parser, cmd_report
from perception.storage.event_store import EventStore
from perception.schemas.detection import ViolationEvent, ViolationType, ViolationSeverity


def test_cli_parser_structure():
    """Verify CLI parser commands and flags."""
    parser = build_parser()

    # Test run subcommand
    run_args = parser.parse_args([
        "run",
        "--camera-id", "cam_test_01",
        "--source", "tests/fixtures/sample_walk.mp4",
        "--heartbeat-interval", "2.0",
    ])
    assert run_args.command == "run"
    assert run_args.camera_id == "cam_test_01"
    assert run_args.source == "tests/fixtures/sample_walk.mp4"
    assert run_args.heartbeat_interval == 2.0

    # Test report subcommand
    report_args = parser.parse_args([
        "report",
        "--date", "2026-09-25",
        "--event-db", "data/test_events.db",
    ])
    assert report_args.command == "report"
    assert report_args.date == "2026-09-25"
    assert report_args.event_db == "data/test_events.db"


def test_cli_report_generation(capsys):
    """Verify CLI report subcommand outputs valid JSON."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "events.db"
        store = EventStore(db_path=db_path)

        ev = ViolationEvent(
            event_uuid="ev-cli-01",
            track_id=10,
            camera_id="cam_gate_01",
            violation_type=ViolationType.NO_HELMET,
            severity=ViolationSeverity.WARNING,
            start_time=1.0,
            created_at="2026-09-25T14:00:00Z",
        )
        store.save_event(ev)

        parser = build_parser()
        args = parser.parse_args([
            "report",
            "--date", "2026-09-25",
            "--event-db", str(db_path),
        ])

        exit_code = cmd_report(args)
        assert exit_code == 0

        captured = capsys.readouterr()
        output_json = json.loads(captured.out)
        assert output_json["date"] == "2026-09-25"
        assert output_json["total_violations"] == 1
        assert output_json["by_camera"]["cam_gate_01"] == 1
