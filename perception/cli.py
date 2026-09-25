"""
Perception Command Line Interface (CLI).
Provides entrypoints for running headless camera monitoring sessions,
submitting heartbeats, and generating daily safety reports from the terminal.
"""

import os
import sys
import time
import signal
import logging
import argparse
import json
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from perception.detectors.base import get_optimal_device
from perception.detectors.legacy_yolo_adapter import LegacyYOLOv5Adapter
from perception.storage.event_store import EventStore
from perception.services.event_publisher import OutboxStore, PerceptionEventPublisher
from perception.services.session_runner import CameraSessionRunner, CivilSafetyPerceptionService
from perception.geometry.danger_zone import load_danger_zones_from_json

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("perception.cli")


def cmd_run(args: argparse.Namespace) -> int:
    """Runs a headless camera monitoring session."""
    logger.info(f"Initializing camera session for {args.camera_id} from source: {args.source}")

    device = get_optimal_device(args.device)
    logger.info(f"Target inference device: {device}")

    # Initialize Detector
    weights_path = Path(args.weights)
    if not weights_path.is_file():
        # Try fallback to project weights
        alt_path = PROJECT_ROOT / "perception" / "weights" / "helmet_head_person_s.pt"
        if alt_path.is_file():
            weights_path = alt_path
        else:
            logger.error(f"Weights file not found: {args.weights}")
            return 1

    detector = LegacyYOLOv5Adapter(device=device)
    detector.load_model(str(weights_path), device=device)
    logger.info(f"Model loaded successfully from {weights_path}")

    # Initialize Outbox & Publisher
    outbox_store = OutboxStore(db_path=args.outbox_db)
    publisher = PerceptionEventPublisher(
        outbox_store=outbox_store,
        agent_base_url=args.agent_url,
        bearer_token=os.getenv("INTERNAL_PERCEPTION_TOKEN"),
    )
    logger.info(f"Outbox initialized at {args.outbox_db}, targeting Agent at {args.agent_url}")

    # Initialize EventStore
    event_store = EventStore(
        db_path=args.event_db,
        snapshot_dir=args.snapshot_dir,
    )

    # Load initial danger zones if provided
    danger_zones = None
    if args.zones_config and Path(args.zones_config).is_file():
        danger_zones = load_danger_zones_from_json(args.zones_config)
        logger.info(f"Loaded {len(danger_zones)} danger zones from {args.zones_config}")

    # Create Runner
    runner = CameraSessionRunner(
        camera_id=args.camera_id,
        source=args.source,
        detector=detector,
        publisher=publisher,
        event_store=event_store,
        danger_zones=danger_zones,
        heartbeat_interval=args.heartbeat_interval,
        config_poll_interval=args.config_poll_interval,
        model_name=args.model_name,
        model_version=args.model_version,
    )

    stop_requested = False

    def handle_signal(sig, frame):
        nonlocal stop_requested
        if not stop_requested:
            stop_requested = True
            logger.info(f"Signal {sig} received. Initiating graceful shutdown...")
            runner.stop()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    session_id = runner.start()
    logger.info(f"Perception session {session_id} active. Press Ctrl+C to terminate.")

    try:
        while runner.is_running() and not stop_requested:
            time.sleep(1.0)
            status = runner.get_status()
            logger.debug(
                f"[Monitor] Cam: {status['camera_id']} | FPS: {status['fps']:.1f} | "
                f"Workers: {status['active_workers_count']} | Helmet: {status['helmet_compliance_rate']:.1%} | "
                f"Active Violations: {status['active_violations_count']}"
            )
    except KeyboardInterrupt:
        handle_signal(signal.SIGINT, None)

    runner.stop()
    logger.info("Session runner shut down cleanly.")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Generates structured daily safety report from local SQLite event store."""
    event_store = EventStore(db_path=args.event_db)
    service = CivilSafetyPerceptionService(event_store=event_store)
    report = service.generate_daily_safety_report(args.date)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="perception",
        description="Smart Construction Civil Engineering Perception CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: run
    run_parser = subparsers.add_parser("run", help="Run headless camera perception stream monitor")
    run_parser.add_argument("--camera-id", required=True, help="Camera identifier (e.g. cam_crane_01)")
    run_parser.add_argument("--source", required=True, help="RTSP URL, video file path, or webcam index")
    run_parser.add_argument("--agent-url", default="http://127.0.0.1:8000", help="Agent API base URL")
    run_parser.add_argument(
        "--weights",
        default=str(PROJECT_ROOT / "perception" / "weights" / "helmet_head_person_s.pt"),
        help="Path to YOLO weights",
    )
    run_parser.add_argument("--device", default="auto", help="Inference device: auto, cpu, cuda")
    run_parser.add_argument("--zones-config", default=None, help="Path to danger zones JSON")
    run_parser.add_argument("--outbox-db", default="data/outbox.db", help="SQLite path for outbox events")
    run_parser.add_argument("--event-db", default="data/events.db", help="SQLite path for local events")
    run_parser.add_argument("--snapshot-dir", default="data/snapshots", help="Directory for snapshot media")
    run_parser.add_argument("--heartbeat-interval", type=float, default=5.0, help="Heartbeat interval in seconds")
    run_parser.add_argument("--config-poll-interval", type=float, default=30.0, help="Config polling interval in seconds")
    run_parser.add_argument("--model-name", default="helmet_head_person_s", help="Model name identifier")
    run_parser.add_argument("--model-version", default="legacy-yolov5", help="Model version identifier")

    # Subcommand: report
    report_parser = subparsers.add_parser("report", help="Generate daily safety report")
    report_parser.add_argument("--date", required=True, help="Date in YYYYMMDD or YYYY-MM-DD")
    report_parser.add_argument("--event-db", default="data/events.db", help="SQLite path for local events")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "run":
        return cmd_run(args)
    elif args.command == "report":
        return cmd_report(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
