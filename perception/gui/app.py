# -*- coding: utf-8 -*-
"""
Modernized Safety Perception GUI Application
Refactored from Smart_Construction/visual_interface.py with:
- Cross-platform Path resolution (pathlib)
- Safe hardware metrics (GPU via GPUtil with automatic CPU/RAM fallback via psutil)
- BaseDetector decoupled model backend
- No single-weight hardcoded crashes
"""

import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional
import psutil

# Import PyTorch and torchvision before PyQt5 to avoid C++ runtime symbol conflicts
import torch
import torch.jit
import torchvision
torch.jit.script_method = lambda fn, _rcb=None: fn
torch.jit.script = lambda obj, optimize=True, _frames_up=0, _rcb=None: obj

# Explicitly ensure Qt5 platform and plugin paths resolve to PyQt5
import PyQt5
pyqt5_dir = os.path.dirname(PyQt5.__file__)
qt5_plugins = os.path.join(pyqt5_dir, "Qt5", "plugins")
if os.path.isdir(qt5_plugins):
    if "QT_PLUGIN_PATH" not in os.environ:
        os.environ["QT_PLUGIN_PATH"] = qt5_plugins
    platforms_dir = os.path.join(qt5_plugins, "platforms")
    if os.path.isdir(platforms_dir) and "QT_QPA_PLATFORM_PLUGIN_PATH" not in os.environ:
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = platforms_dir


from PyQt5.QtCore import QDateTime, Qt, QThread, QTimer, QUrl, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QBrush, QColor, QIcon, QImage, QPixmap
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer
from PyQt5.QtWidgets import QApplication, QFileDialog, QMainWindow
from PyQt5.QtChart import QChart, QDateTimeAxis, QSplineSeries, QValueAxis

# Local GUI UI definitions
GUI_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = GUI_DIR.parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from perception.gui.UI.main_window import Ui_MainWindow
from perception.detectors.legacy_yolo_adapter import LegacyYOLOv5Adapter
from perception.detectors.ultralytics_detector import UltralyticsDetector
from perception.geometry.danger_zone import (
    DangerZone,
    load_danger_zones_from_json,
    person_in_danger_zone,
)
from perception.storage.event_store import EventStore
from perception.tracking.byte_tracker import BYTETracker
from perception.schemas.detection import BoundingBox

CODE_VER = "V2.5 (Perception Subsystem)"


def get_hardware_info() -> Dict[str, float]:
    """
    Safely probes system hardware utilization:
    Returns GPU utilization if available; falls back to CPU & RAM usage gracefully.
    """
    info = {
        "is_gpu": False,
        "load": psutil.cpu_percent(),
        "memory_util": psutil.virtual_memory().percent,
        "desc": f"CPU: {psutil.cpu_percent():.1f}% | RAM: {psutil.virtual_memory().percent:.1f}%",
    }
    try:
        from GPUtil import GPUtil
        gpus = GPUtil.getGPUs()
        if gpus and len(gpus) > 0:
            gpu = gpus[0]
            info["is_gpu"] = True
            info["load"] = float(gpu.load * 100.0)
            info["memory_util"] = float(gpu.memoryUtil * 100.0)
            info["desc"] = f"GPU 0: {gpu.load * 100.0:.1f}% | VRAM: {gpu.memoryUtil * 100.0:.1f}%"
    except Exception:
        pass

    return info


class PerceptionWorkerThread(QThread):
    """
    Background worker thread for inference, tracking and safety monitoring without blocking GUI main loop.
    """
    progress_signal = pyqtSignal(int, float)  # (percent, fps)
    message_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)

    def __init__(self, detector, source_path: str, output_dir: str):
        super().__init__()
        self.detector = detector
        self.source_path = source_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.running = False

        # Event storage, outbox, and danger zones
        self.event_store = EventStore(
            db_path=self.output_dir / "safety_events.db",
            snapshot_dir=self.output_dir / "snapshots",
        )
        from perception.services.event_publisher import PerceptionEventPublisher
        self.event_publisher = PerceptionEventPublisher(
            db_path=self.output_dir / "outbox.db",
        )
        self.danger_zones: List[DangerZone] = []
        cfg_path = PROJECT_ROOT / "perception" / "configs" / "default_danger_zones.json"
        if cfg_path.is_file():
            self.danger_zones = load_danger_zones_from_json(cfg_path)

    def run(self):
        self.running = True
        import cv2
        import numpy as np
        from perception.schemas.contract_v1 import TimeAnchor
        from perception.tracking.safety_pipeline import SafetyPerceptionPipeline

        src = self.source_path
        p_src = Path(src)
        out_file = str(self.output_dir / f"result_{p_src.name}")

        is_image = p_src.suffix.lower() in [".jpg", ".jpeg", ".png", ".bmp"]
        pipeline = SafetyPerceptionPipeline(
            detector=self.detector,
            danger_zones=self.danger_zones,
            event_store=self.event_store,
            event_publisher=self.event_publisher,
            time_anchor=TimeAnchor(),
            camera_id=p_src.stem,
        )

        def render_frame(frame, pipeline_result):
            # Draw danger zone overlays
            for zone in self.danger_zones:
                if len(zone.polygon) >= 3:
                    pts = np.array(zone.polygon, dtype=np.int32).reshape((-1, 1, 2))
                    overlay = frame.copy()
                    cv2.fillPoly(overlay, [pts], (0, 0, 220))
                    cv2.addWeighted(overlay, 0.25, frame, 0.75, 0, frame)
                    cv2.polylines(frame, [pts], isClosed=True, color=(0, 0, 255), thickness=2)
                    cv2.putText(frame, zone.name, tuple(pts[0][0]), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)

            # Draw tracked persons with compliance status
            for track in pipeline_result.tracked_persons:
                b = track.bbox
                is_violation = track.is_in_danger_zone or not track.has_helmet
                color = (0, 0, 255) if is_violation else (0, 255, 0)
                bx1, by1 = int(b.x1), int(b.y1)
                bx2, by2 = int(b.x2), int(b.y2)
                cv2.rectangle(frame, (bx1, by1), (bx2, by2), color, 2)

                # Feet point
                fx, fy = int(track.feet_point[0]), int(track.feet_point[1])
                cv2.circle(frame, (fx, fy), 4, (0, 255, 255), -1)

                h_status = "HELMET" if track.has_helmet else "NO_HELMET"
                label = f"ID:{track.track_id} [{h_status}]"
                if track.is_in_danger_zone:
                    label += f" | Dwell:{track.dwell_time_seconds:.1f}s"
                cv2.putText(frame, label, (bx1, max(15, by1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 2)

            # Log any new violations
            for ev in pipeline_result.new_violations:
                self.message_signal.emit(
                    f"⚠️ [ALERT] {ev.violation_type} (Track {ev.track_id}) at {ev.zone_name or 'Site'}"
                )

        if is_image:
            img = cv2.imread(src)
            if img is not None:
                t0 = time.monotonic()
                res = pipeline.process_frame(img)
                t_cost = time.monotonic() - t0
                fps = 1.0 / max(0.001, t_cost)

                render_frame(img, res)
                cv2.imwrite(out_file, img)
                self.progress_signal.emit(100, fps)
                self.message_signal.emit(
                    f"Processed {p_src.name}: {len(res.raw_detections)} bboxes, {len(res.tracked_persons)} workers. Cost: {t_cost*1000:.1f}ms"
                )
                self.finished_signal.emit(out_file)
        else:
            cap = cv2.VideoCapture(src)
            if not cap.isOpened():
                self.message_signal.emit(f"Error: Unable to open video {src}")
                self.finished_signal.emit("")
                return

            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
            fps_src = cap.get(cv2.CAP_PROP_FPS) or 25
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(out_file, fourcc, fps_src, (w, h))

            frame_idx = 0
            while self.running and cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                frame_idx += 1
                t0 = time.monotonic()
                res = pipeline.process_frame(frame, timestamp=frame_idx / fps_src)
                t_cost = time.monotonic() - t0
                fps = 1.0 / max(0.001, t_cost)

                render_frame(frame, res)
                writer.write(frame)

                percent = int((frame_idx / total_frames) * 100)
                self.progress_signal.emit(percent, fps)
                if frame_idx % 10 == 0:
                    self.message_signal.emit(f"Frame {frame_idx}/{total_frames} (FPS: {fps:.1f})")

            cap.release()
            writer.release()
            self.progress_signal.emit(100, fps_src)
            self.message_signal.emit(f"Video processing finished. Saved to {out_file}")
            self.finished_signal.emit(out_file)



class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.setWindowTitle(f"Civil Engineering Agent - Safety Perception Studio {CODE_VER}")
        self.showMaximized()

        # Dynamically determine optimal compute device
        from perception.detectors.base import get_optimal_device
        device = get_optimal_device()

        # Load detector from PERCEPTION_MODEL_WEIGHTS or perception/weights/
        weights_dir = PROJECT_ROOT / "perception" / "weights"
        candidate_weights = []
        env_weight = os.environ.get("PERCEPTION_MODEL_WEIGHTS")
        if env_weight and Path(env_weight).is_file():
            candidate_weights.append(Path(env_weight))
        candidate_weights.extend([
            weights_dir / "helmet_head_person_m.pt",
            weights_dir / "helmet_head_person_s.pt",
            weights_dir / "yolov8n.pt",
        ])

        self.detector = None
        self.using_weight_name = "MockDetector (No weights)"
        for w in candidate_weights:
            if w.is_file():
                if "yolov8" in w.name.lower() or "yolo11" in w.name.lower():
                    self.detector = UltralyticsDetector(str(w), device=device)
                else:
                    self.detector = LegacyYOLOv5Adapter(str(w), device=device)
                self.using_weight_name = f"{w.name} [{device}]"
                break

        if self.detector is None:
            from perception.detectors.base import MockDetector
            self.detector = MockDetector()

        # Update weight label in UI if present
        if hasattr(self, "weight_file_label"):
            self.weight_file_label.setText(f"Using weight: {self.using_weight_name}")

        self.current_source = ""
        self.output_file = ""

        # Bind button events
        self.import_media_pushButton.clicked.connect(self.import_media)
        self.start_predict_pushButton.clicked.connect(self.start_prediction)
        self.open_predict_file_pushButton.clicked.connect(self.open_output_folder)
        self.play_pushButton.clicked.connect(self.play_media)
        self.pause_pushButton.clicked.connect(self.pause_media)

        # Setup players
        self.input_player = QMediaPlayer()
        self.input_player.setVideoOutput(self.input_video_widget)
        self.output_player = QMediaPlayer()
        self.output_player.setVideoOutput(self.output_video_widget)

        # Setup image labels for static media and real-time visualization
        if hasattr(self, "input_real_time_label"):
            self.input_real_time_label.setScaledContents(True)
            self.input_real_time_label.setAlignment(Qt.AlignCenter)
        if hasattr(self, "output_real_time_label"):
            self.output_real_time_label.setScaledContents(True)
            self.output_real_time_label.setAlignment(Qt.AlignCenter)

        # Chart initialization
        self.series = QSplineSeries()
        self.chart_init()

        # Hardware monitor timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_hardware_chart)
        self.timer.start(1000)

    def chart_init(self):
        self.chart = QChart()
        self.chart.addSeries(self.series)
        self.chart.setTitle("System Utilization (Hardware Load)")
        self.chart.legend().hide()

        self.axisX = QDateTimeAxis()
        self.axisX.setFormat("hh:mm:ss")
        self.axisX.setTitleText("Time")
        self.axisX.setTickCount(5)
        self.chart.addAxis(self.axisX, Qt.AlignBottom)
        self.series.attachAxis(self.axisX)

        self.axisY = QValueAxis()
        self.axisY.setRange(0, 100)
        self.axisY.setTitleText("Utilization (%)")
        self.chart.addAxis(self.axisY, Qt.AlignLeft)
        self.series.attachAxis(self.axisY)

        if hasattr(self, "gpu_info_chart"):
            self.gpu_info_chart.setChart(self.chart)
        elif hasattr(self, "chart_view"):
            self.chart_view.setChart(self.chart)

    def update_hardware_chart(self):
        info = get_hardware_info()
        val = info["load"]
        now = QDateTime.currentDateTime()

        self.series.append(now.toMSecsSinceEpoch(), val)
        if self.series.count() > 30:
            self.series.remove(0)

        t_min = QDateTime.fromMSecsSinceEpoch(int(self.series.at(0).x()))
        self.axisX.setRange(t_min, now)
        self.chart.setTitle(f"System Load: {info['desc']}")

    def import_media(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Select Media File",
            str(PROJECT_ROOT / "tests" / "fixtures"),
            "Media Files (*.mp4 *.avi *.jpg *.jpeg *.png *.bmp)",
        )
        if filepath:
            self.current_source = filepath
            ext = Path(filepath).suffix.lower()
            is_image = ext in [".jpg", ".jpeg", ".png", ".bmp"]

            if is_image:
                if hasattr(self, "input_media_tabWidget"):
                    self.input_media_tabWidget.setCurrentIndex(1)
                if hasattr(self, "input_real_time_label"):
                    self.input_real_time_label.setPixmap(QPixmap(filepath))
                self.play_pushButton.setEnabled(False)
                self.pause_pushButton.setEnabled(False)
            else:
                if hasattr(self, "input_media_tabWidget"):
                    self.input_media_tabWidget.setCurrentIndex(0)
                self.input_player.setMedia(QMediaContent(QUrl.fromLocalFile(filepath)))
                self.input_player.pause()
                self.play_pushButton.setEnabled(True)
                self.pause_pushButton.setEnabled(True)

            self.predict_info_plainTextEdit.appendPlainText(f"Imported: {filepath}")

    def start_prediction(self):
        if not self.current_source:
            self.predict_info_plainTextEdit.appendPlainText("Please import a media file first!")
            return

        out_dir = str(PROJECT_ROOT / "runs" / "gui_output")
        self.worker = PerceptionWorkerThread(self.detector, self.current_source, out_dir)
        self.worker.progress_signal.connect(self.on_progress)
        self.worker.message_signal.connect(self.on_message)
        self.worker.finished_signal.connect(self.on_finished)
        self.start_predict_pushButton.setEnabled(False)
        self.worker.start()

    def on_progress(self, percent: int, fps: float):
        self.predict_progressBar.setValue(percent)
        self.fps_label.setText(f"--> {fps:.1f} FPS")

    def on_message(self, msg: str):
        self.predict_info_plainTextEdit.appendPlainText(msg)

    def on_finished(self, out_file: str):
        self.start_predict_pushButton.setEnabled(True)
        if out_file and Path(out_file).is_file():
            self.output_file = out_file
            ext = Path(out_file).suffix.lower()
            is_image = ext in [".jpg", ".jpeg", ".png", ".bmp"]

            if is_image:
                if hasattr(self, "output_media_tabWidget"):
                    self.output_media_tabWidget.setCurrentIndex(1)
                if hasattr(self, "output_real_time_label"):
                    self.output_real_time_label.setPixmap(QPixmap(out_file))
            else:
                if hasattr(self, "output_media_tabWidget"):
                    self.output_media_tabWidget.setCurrentIndex(0)
                self.output_player.setMedia(QMediaContent(QUrl.fromLocalFile(out_file)))
                self.output_player.pause()

            self.predict_info_plainTextEdit.appendPlainText(f"Ready: {out_file}")

    def play_media(self):
        self.input_player.play()
        self.output_player.play()

    def pause_media(self):
        self.input_player.pause()
        self.output_player.pause()

    def open_output_folder(self):
        out_dir = PROJECT_ROOT / "runs" / "gui_output"
        out_dir.mkdir(parents=True, exist_ok=True)
        import subprocess
        if sys.platform == "win32":
            os.startfile(str(out_dir))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(out_dir)])
        else:
            subprocess.Popen(["xdg-open", str(out_dir)])


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
