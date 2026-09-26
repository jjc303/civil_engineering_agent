"""
Headless Perception Session Runner and CivilSafetyPerceptionService.
Provides asynchronous, headless multi-camera stream monitoring, background threads,
periodic heartbeat reporting to Agent, dynamic config hot-reloading, and daily report generation.
"""

import os
import sys
import time
import signal
import logging
import threading
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union, Tuple

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from perception.schemas.contract_v1 import (
    CameraStatusContractV1,
    CameraRunConfigContractV1,
    TimeAnchor,
)
from perception.schemas.detection import ViolationEvent, ViolationType, ViolationSeverity
from perception.geometry.danger_zone import DangerZone, load_danger_zones_from_json
from perception.detectors.base import BaseDetector, get_optimal_device
from perception.detectors.legacy_yolo_adapter import LegacyYOLOv5Adapter
from perception.tracking.safety_pipeline import SafetyPerceptionPipeline, PipelineFrameResult
from perception.storage.event_store import EventStore
from perception.services.event_publisher import PerceptionEventPublisher

logger = logging.getLogger("perception.session_runner")


class CameraSessionRunner:
    """
    Headless video perception session runner for a single camera stream.
    Runs decoding, tracking, violation detection, periodic heartbeat status reporting,
    and dynamic config polling in a dedicated background thread.
    """

    def __init__(
        self,
        camera_id: str,
        source: Union[str, int],
        detector: BaseDetector,
        publisher: Optional[PerceptionEventPublisher] = None,
        event_store: Optional[EventStore] = None,
        danger_zones: Optional[List[DangerZone]] = None,
        time_anchor: Optional[TimeAnchor] = None,
        monitor_session_id: Optional[str] = None,
        model_name: str = "helmet_head_person_m",
        model_version: str = "legacy-yolov5",
        heartbeat_interval: float = 5.0,
        config_poll_interval: float = 30.0,
        enter_debounce_frames: int = 3,
        exit_debounce_frames: int = 5,
        helmet_debounce_frames: int = 5,
        track_thresh: float = 0.5,
        loop_video: bool = True,
        fps_throttle: bool = False,
    ):
        self.camera_id = camera_id
        self.source = int(source) if isinstance(source, str) and source.isdigit() else source
        self.detector = detector
        self.publisher = publisher
        self.event_store = event_store
        self.initial_danger_zones = danger_zones or []
        self.time_anchor = time_anchor
        self.monitor_session_id = monitor_session_id or f"session_{camera_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        self.model_name = model_name
        self.model_version = model_version
        self.heartbeat_interval = heartbeat_interval
        self.config_poll_interval = config_poll_interval

        self.enter_debounce_frames = enter_debounce_frames
        self.exit_debounce_frames = exit_debounce_frames
        self.helmet_debounce_frames = helmet_debounce_frames
        self.track_thresh = track_thresh
        self.loop_video = loop_video
        self.fps_throttle = fps_throttle

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._is_running = False
        self._last_config_version = 0

        self.pipeline: Optional[SafetyPerceptionPipeline] = None
        self.last_status: Optional[CameraStatusContractV1] = None
        self.last_frame_result: Optional[PipelineFrameResult] = None
        self._preview_lock = threading.Lock()
        self._preview_jpeg: bytes | None = None

    def start(self) -> str:
        """Starts the video perception runner in a background thread."""
        if self.is_running():
            logger.warning(f"[SessionRunner] Camera {self.camera_id} is already running.")
            return self.monitor_session_id

        self._stop_event.clear()
        self._is_running = True

        if self.time_anchor is None:
            self.time_anchor = TimeAnchor(
                session_started_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                session_started_monotonic=time.monotonic(),
            )

        self._thread = threading.Thread(
            target=self._run_loop,
            name=f"CameraRunner-{self.camera_id}",
            daemon=True,
        )
        self._thread.start()
        logger.info(f"[SessionRunner] Started monitoring camera {self.camera_id} (session: {self.monitor_session_id})")
        return self.monitor_session_id

    def stop(self, timeout: float = 5.0) -> None:
        """Stops the monitoring session cleanly."""
        if not self._is_running and (self._thread is None or not self._thread.is_alive()):
            return

        logger.info(f"[SessionRunner] Stopping camera {self.camera_id}...")
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        self._is_running = False

        # Send offline heartbeat
        self._report_offline_status()

    def is_running(self) -> bool:
        """Checks if the runner thread is currently alive and active."""
        return self._is_running and (self._thread is not None and self._thread.is_alive())

    def get_status(self) -> Dict[str, Any]:
        """Returns real-time status dictionary."""
        active_viols = len(self.pipeline.active_violations) if self.pipeline else 0
        current_frame = self.pipeline.frame_counter if self.pipeline else 0

        return {
            "camera_id": self.camera_id,
            "monitor_session_id": self.monitor_session_id,
            "is_online": self.is_running(),
            "fps": self.last_status.fps if self.last_status else 0.0,
            "processed_frame_id": current_frame,
            "active_workers_count": self.last_status.active_workers_count if self.last_status else 0,
            "helmet_compliance_rate": self.last_status.helmet_compliance_rate if self.last_status else 1.0,
            "active_violations_count": active_viols,
        }

    def latest_preview_jpeg(self) -> bytes | None:
        """Return a thread-safe copy of the latest decoded frame for HTTP preview."""
        with self._preview_lock:
            return self._preview_jpeg

    def _fetch_or_fallback_zones(self) -> List[DangerZone]:
        """
        Attempts to fetch camera configuration from Agent.
        If config endpoint is unavailable (e.g. 404 or None), gracefully falls back
        to user-provided zones or default_danger_zones.json.
        """
        if self.publisher is not None:
            try:
                cfg = self.publisher.fetch_camera_config(self.camera_id)
                if cfg is not None:
                    self._last_config_version = cfg.config_version
                    self.enter_debounce_frames = cfg.enter_debounce_frames
                    self.exit_debounce_frames = cfg.exit_debounce_frames
                    self.helmet_debounce_frames = cfg.helmet_debounce_frames
                    zones = []
                    for z in cfg.zones:
                        if z.enabled:
                            zones.append(
                                DangerZone(
                                    name=z.zone_name,
                                    polygon=[(float(p[0]), float(p[1])) for p in z.polygon],
                                    alarm_dwell_threshold_seconds=z.alarm_dwell_threshold_seconds,
                                    zone_id=z.zone_id,
                                )
                            )
                    logger.info(f"[SessionRunner] Loaded {len(zones)} zones from Agent config v{cfg.config_version}")
                    return zones
            except Exception as exc:
                logger.warning(f"[SessionRunner] Failed to fetch config from Agent: {exc}")

        # Fallback to initial provided zones
        if self.initial_danger_zones:
            logger.info(f"[SessionRunner] Using {len(self.initial_danger_zones)} initial zones provided")
            return self.initial_danger_zones

        # Fallback to local default_danger_zones.json
        default_cfg_path = PROJECT_ROOT / "perception" / "configs" / "default_danger_zones.json"
        if default_cfg_path.is_file():
            loaded = load_danger_zones_from_json(default_cfg_path)
            logger.info(f"[SessionRunner] Agent config unavailable; gracefully fell back to {default_cfg_path} ({len(loaded)} zones)")
            return loaded

        logger.warning(f"[SessionRunner] No danger zones configured for camera {self.camera_id}")
        return []

    def _report_offline_status(self) -> None:
        """Sends final offline heartbeat to Agent."""
        if self.publisher is None:
            return
        try:
            offline_status = CameraStatusContractV1(
                camera_id=self.camera_id,
                monitor_session_id=self.monitor_session_id,
                is_online=False,
                fps=0.0,
                processed_frame_id=self.pipeline.frame_counter if self.pipeline else 0,
                active_workers_count=0,
                helmet_compliance_rate=self.last_status.helmet_compliance_rate if self.last_status else 1.0,
                model_name=self.model_name,
                model_version=self.model_version,
            )
            self.publisher.report_camera_status(offline_status)
            self.publisher.flush_outbox(max_batch=20)
        except Exception as exc:
            logger.warning(f"[SessionRunner] Failed to report offline status: {exc}")

    def _poll_config_updates(self) -> None:
        """Polls Agent for online config changes and hot-reloads if config_version changed."""
        if self.publisher is None or self.pipeline is None:
            return
        try:
            cfg = self.publisher.fetch_camera_config(self.camera_id)
            if cfg is not None and cfg.config_version > self._last_config_version:
                new_zones = [
                    DangerZone(
                        name=z.zone_name,
                        polygon=[(float(p[0]), float(p[1])) for p in z.polygon],
                        alarm_dwell_threshold_seconds=z.alarm_dwell_threshold_seconds,
                        zone_id=z.zone_id,
                    )
                    for z in cfg.zones
                    if z.enabled
                ]
                self.pipeline.update_config(
                    enter_debounce_frames=cfg.enter_debounce_frames,
                    exit_debounce_frames=cfg.exit_debounce_frames,
                    helmet_debounce_frames=cfg.helmet_debounce_frames,
                    danger_zones=new_zones,
                )
                self._last_config_version = cfg.config_version
                logger.info(
                    f"[SessionRunner] Hot-reloaded camera {self.camera_id} config to version {cfg.config_version}"
                )
        except Exception as exc:
            logger.debug(f"[SessionRunner] Config poll check failed: {exc}")

    def _run_loop(self) -> None:
        """Main execution thread loop."""
        danger_zones = self._fetch_or_fallback_zones()

        self.pipeline = SafetyPerceptionPipeline(
            detector=self.detector,
            danger_zones=danger_zones,
            event_store=self.event_store,
            event_publisher=self.publisher,
            time_anchor=self.time_anchor,
            monitor_session_id=self.monitor_session_id,
            camera_id=self.camera_id,
            model_name=self.model_name,
            model_version=self.model_version,
            enter_debounce_frames=self.enter_debounce_frames,
            exit_debounce_frames=self.exit_debounce_frames,
            helmet_debounce_frames=self.helmet_debounce_frames,
            track_thresh=self.track_thresh,
        )

        cap = cv2.VideoCapture(self.source)
        if not cap.isOpened():
            logger.error(f"[SessionRunner] Failed to open video source: {self.source}")
            self._report_offline_status()
            self._is_running = False
            return

        is_file_source = isinstance(self.source, str) and Path(self.source).is_file()
        video_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        if video_fps <= 0 or video_fps > 120:
            video_fps = 25.0

        loop_start_monotonic = time.monotonic()
        last_heartbeat_time = loop_start_monotonic
        last_config_poll_time = loop_start_monotonic
        frames_in_hb_window = 0

        # Initial online heartbeat
        self.last_status = CameraStatusContractV1(
            camera_id=self.camera_id,
            monitor_session_id=self.monitor_session_id,
            is_online=True,
            fps=round(video_fps, 2),
            processed_frame_id=0,
            active_workers_count=0,
            helmet_compliance_rate=1.0,
            model_name=self.model_name,
            model_version=self.model_version,
        )
        if self.publisher:
            self.publisher.report_camera_status(self.last_status)

        try:
            while not self._stop_event.is_set():
                frame_start_mono = time.monotonic()
                ret, frame = cap.read()
                if not ret:
                    if self.loop_video and is_file_source:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ret, frame = cap.read()
                    if not ret:
                        logger.info(f"[SessionRunner] Video stream ended or read returned False (cam: {self.camera_id})")
                        break

                # SafetyPerceptionPipeline timestamps are consumed by TimeAnchor,
                # whose reference is ``time.monotonic()`` at session startup.
                # A file video's frame position (0, 1/fps, ...) is *not* in that
                # clock domain. Passing it here made TimeAnchor subtract the
                # machine's large monotonic uptime and backdate file-source
                # violations. Use the same monotonic clock for every source.
                now_monotonic = time.monotonic()
                ts = now_monotonic

                # Process perception frame
                result = self.pipeline.process_frame(frame, timestamp=ts)
                self.last_frame_result = result
                ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                if ok:
                    with self._preview_lock:
                        self._preview_jpeg = encoded.tobytes()
                frames_in_hb_window += 1

                if self.fps_throttle:
                    frame_target_time = 1.0 / video_fps
                    elapsed_frame = time.monotonic() - frame_start_mono
                    if elapsed_frame < frame_target_time:
                        time.sleep(frame_target_time - elapsed_frame)

                # Calculate real-time compliance
                active_workers = len(result.tracked_persons)
                if active_workers > 0:
                    helmet_count = sum(1 for p in result.tracked_persons if p.has_helmet)
                    compliance_rate = round(helmet_count / active_workers, 4)
                else:
                    compliance_rate = 1.0

                # Periodic Heartbeat & Outbox Flush
                time_since_hb = now_monotonic - last_heartbeat_time
                if time_since_hb >= self.heartbeat_interval:
                    measured_fps = frames_in_hb_window / time_since_hb if time_since_hb > 0 else 0.0
                    frames_in_hb_window = 0
                    last_heartbeat_time = now_monotonic

                    self.last_status = CameraStatusContractV1(
                        camera_id=self.camera_id,
                        monitor_session_id=self.monitor_session_id,
                        is_online=True,
                        fps=round(measured_fps, 2),
                        processed_frame_id=self.pipeline.frame_counter,
                        active_workers_count=active_workers,
                        helmet_compliance_rate=compliance_rate,
                        model_name=self.model_name,
                        model_version=self.model_version,
                    )

                    if self.publisher is not None:
                        self.publisher.report_camera_status(self.last_status)
                        self.publisher.flush_outbox(max_batch=10)

                # Periodic Dynamic Config Polling
                if now_monotonic - last_config_poll_time >= self.config_poll_interval:
                    last_config_poll_time = now_monotonic
                    self._poll_config_updates()

        except Exception as exc:
            logger.exception(f"[SessionRunner] Unhandled exception in perception loop: {exc}")
        finally:
            cap.release()
            self._report_offline_status()
            self._is_running = False
            logger.info(f"[SessionRunner] Monitoring loop terminated for camera {self.camera_id}")


class CivilSafetyPerceptionService:
    """
    Civil Safety Perception Central Service matching the Mother Engineering Agent contract.
    Coordinates multi-camera background monitoring sessions, queries real-time status,
    and produces structured daily safety inspection reports for Agent LLM reasoning.
    """

    def __init__(
        self,
        detector: Optional[BaseDetector] = None,
        event_publisher: Optional[PerceptionEventPublisher] = None,
        event_store: Optional[EventStore] = None,
        weights_path: Optional[str] = None,
        device: str = "auto",
    ):
        self.device = get_optimal_device(device)
        self.event_publisher = event_publisher
        self.event_store = event_store or EventStore()
        self.runners: Dict[str, CameraSessionRunner] = {}
        self.weights_path = weights_path
        self._detector = detector

    @property
    def detector(self) -> BaseDetector:
        if self._detector is None:
            w_path = self.weights_path or str(PROJECT_ROOT / "perception" / "weights" / "helmet_head_person_s.pt")
            det = LegacyYOLOv5Adapter(device=self.device)
            if Path(w_path).is_file():
                det.load_model(w_path, device=self.device)
            self._detector = det
        return self._detector

    def start_monitoring(
        self,
        camera_id: str,
        stream_url: str,
        zones_config: Optional[List[dict]] = None,
        loop_video: bool = True,
        fps_throttle: bool = False,
    ) -> bool:
        """
        Starts a background continuous monitoring task for a specific camera.
        """
        if camera_id in self.runners and self.runners[camera_id].is_running():
            logger.warning(f"[PerceptionService] Camera {camera_id} is already being monitored.")
            return True

        danger_zones: Optional[List[DangerZone]] = None
        if zones_config:
            danger_zones = []
            for item in zones_config:
                if isinstance(item, dict) and "polygon" in item:
                    pts = [(float(pt[0]), float(pt[1])) for pt in item["polygon"]]
                    d = dict(item)
                    d["polygon"] = pts
                    danger_zones.append(DangerZone(**d))

        runner = CameraSessionRunner(
            camera_id=camera_id,
            source=stream_url,
            detector=self.detector,
            publisher=self.event_publisher,
            event_store=self.event_store,
            danger_zones=danger_zones,
            loop_video=loop_video,
            fps_throttle=fps_throttle,
        )

        runner.start()
        self.runners[camera_id] = runner
        return True

    def stop_monitoring(self, camera_id: str) -> bool:
        """
        Stops the continuous monitoring task for a specific camera.
        """
        if camera_id not in self.runners:
            return False

        runner = self.runners.pop(camera_id)
        runner.stop()
        return True

    def query_safety_status(self, camera_id: str) -> Dict[str, Any]:
        """
        Lightweight status query interface designed for periodic Agent polling.
        """
        runner = self.runners.get(camera_id)
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        if runner and runner.is_running():
            stat = runner.last_status
            active_violations = [
                {
                    "track_id": v.track_id,
                    "type": v.violation_type.value if hasattr(v.violation_type, "value") else str(v.violation_type),
                    "zone_name": v.zone_name or "N/A",
                    "dwell_time_seconds": round(v.duration_seconds, 2),
                    "severity": v.severity.value if hasattr(v.severity, "value") else str(v.severity),
                }
                for v in (runner.pipeline.active_violations if runner.pipeline else [])
            ]
            return {
                "camera_id": camera_id,
                "timestamp": now_iso,
                "is_online": True,
                "active_workers_count": stat.active_workers_count if stat else 0,
                "helmet_compliance_rate": stat.helmet_compliance_rate if stat else 1.0,
                "active_violations": active_violations,
            }
        else:
            return {
                "camera_id": camera_id,
                "timestamp": now_iso,
                "is_online": False,
                "active_workers_count": 0,
                "helmet_compliance_rate": 1.0,
                "active_violations": [],
            }

    def generate_daily_safety_report(self, date_str: str) -> Dict[str, Any]:
        """
        Aggregates SQLite violation events by date for LLM daily safety report generation.
        Accepts formats: 'YYYYMMDD' or 'YYYY-MM-DD'.
        """
        clean_date = date_str.replace("-", "")
        formatted_iso_date = f"{clean_date[:4]}-{clean_date[4:6]}-{clean_date[6:8]}" if len(clean_date) == 8 else date_str

        all_events = self.event_store.query_events(limit=5000)

        date_events: List[ViolationEvent] = []
        for ev in all_events:
            ev_date = ""
            if ev.created_at:
                ev_date = ev.created_at[:10]
            elif ev.snapshot_path and "snapshots/" in ev.snapshot_path:
                parts = ev.snapshot_path.split("/")
                if len(parts) >= 2 and len(parts[1]) == 8:
                    d = parts[1]
                    ev_date = f"{d[:4]}-{d[4:6]}-{d[6:8]}"

            if ev_date == formatted_iso_date or (ev.created_at and clean_date in ev.created_at):
                date_events.append(ev)

        by_type: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        by_camera: Dict[str, int] = {}
        resolved_count = 0
        active_count = 0

        for ev in date_events:
            v_type = ev.violation_type.value if hasattr(ev.violation_type, "value") else str(ev.violation_type)
            v_sev = ev.severity.value if hasattr(ev.severity, "value") else str(ev.severity)
            by_type[v_type] = by_type.get(v_type, 0) + 1
            by_severity[v_sev] = by_severity.get(v_sev, 0) + 1
            by_camera[ev.camera_id] = by_camera.get(ev.camera_id, 0) + 1

            if ev.status == "RESOLVED" or ev.end_time is not None:
                resolved_count += 1
            else:
                active_count += 1

        return {
            "date": formatted_iso_date,
            "total_violations": len(date_events),
            "by_type": by_type,
            "by_severity": by_severity,
            "by_camera": by_camera,
            "resolved_count": resolved_count,
            "active_count": active_count,
            "events": [
                {
                    "event_uuid": ev.event_uuid,
                    "camera_id": ev.camera_id,
                    "track_id": ev.track_id,
                    "violation_type": ev.violation_type.value if hasattr(ev.violation_type, "value") else str(ev.violation_type),
                    "severity": ev.severity.value if hasattr(ev.severity, "value") else str(ev.severity),
                    "status": ev.status,
                    "zone_name": ev.zone_name,
                    "start_time": ev.start_time,
                    "duration_seconds": ev.duration_seconds,
                    "snapshot_uri": ev.snapshot_path,
                }
                for ev in date_events
            ],
        }

    def stop_all(self) -> None:
        """Stops all active camera monitoring sessions."""
        for cam_id in list(self.runners.keys()):
            self.stop_monitoring(cam_id)
