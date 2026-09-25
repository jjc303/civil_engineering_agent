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

# Safe PyTorch JIT patch
import torch.jit
torch.jit.script_method = lambda fn, _rcb=None: fn
torch.jit.script = lambda obj, optimize=True, _frames_up=0, _rcb=None: obj

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
    load_danger_zones_from_json,
    person_in_danger_zone,
)
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
    Background worker thread for inference and tracking without blocking GUI main loop.
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

    def run(self):
        self.running = True
        import cv2

        src = self.source_path
        p_src = Path(src)
        out_file = str(self.output_dir / f"result_{p_src.name}")

        is_image = p_src.suffix.lower() in [".jpg", ".jpeg", ".png", ".bmp"]
        tracker = BYTETracker()

        if is_image:
            img = cv2.imread(src)
            if img is not None:
                t0 = time.monotonic()
                res = self.detector.detect(img)
                t_cost = time.monotonic() - t0
                fps = 1.0 / max(0.001, t_cost)

                # Track
                person_boxes = [b for b in res.boxes if b.class_name == "person"]
                tracks = tracker.update(person_boxes)

                # Draw bboxes
                for box in res.boxes:
                    color = (0, 255, 0) if box.class_name == "helmet" else (0, 0, 255)
                    cv2.rectangle(img, (int(box.x1), int(box.y1)), (int(box.x2), int(box.y2)), color, 2)
                    cv2.putText(
                        img,
                        f"{box.class_name} {box.conf:.2f}",
                        (int(box.x1), max(15, int(box.y1) - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        color,
                        2,
                    )

                cv2.imwrite(out_file, img)
                self.progress_signal.emit(100, fps)
                self.message_signal.emit(
                    f"Processed {p_src.name}: {len(res.boxes)} detections, {len(tracks)} tracked persons. Cost: {t_cost*1000:.1f}ms"
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
                res = self.detector.detect(frame)
                t_cost = time.monotonic() - t0
                fps = 1.0 / max(0.001, t_cost)

                person_boxes = [b for b in res.boxes if b.class_name == "person"]
                tracks = tracker.update(person_boxes)

                for track in tracks:
                    b = track.bbox
                    cv2.rectangle(frame, (int(b.x1), int(b.y1)), (int(b.x2), int(b.y2)), (0, 255, 255), 2)
                    cv2.putText(
                        frame,
                        f"ID: {track.track_id}",
                        (int(b.x1), max(15, int(b.y1) - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 255, 255),
                        2,
                    )

                writer.write(frame)

                percent = int((frame_idx / total_frames) * 100)
                self.progress_signal.emit(percent, fps)
                if frame_idx % 10 == 0:
                    self.message_signal.emit(f"Frame {frame_idx}/{total_frames} processed (FPS: {fps:.1f})")

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

        # Load detector from perception/weights/
        weights_dir = PROJECT_ROOT / "perception" / "weights"
        m_weight = weights_dir / "helmet_head_person_m.pt"
        s_weight = weights_dir / "helmet_head_person_s.pt"

        if m_weight.is_file():
            self.detector = LegacyYOLOv5Adapter(str(m_weight), device="cpu")
            self.using_weight_name = m_weight.name
        elif s_weight.is_file():
            self.detector = LegacyYOLOv5Adapter(str(s_weight), device="cpu")
            self.using_weight_name = s_weight.name
        else:
            v8_weight = weights_dir / "yolov8n.pt"
            if v8_weight.is_file():
                self.detector = UltralyticsDetector(str(v8_weight), device="cpu")
                self.using_weight_name = v8_weight.name
            else:
                from perception.detectors.base import MockDetector
                self.detector = MockDetector()
                self.using_weight_name = "MockDetector (No weights)"

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
            "Media Files (*.mp4 *.avi *.jpg *.png)",
        )
        if filepath:
            self.current_source = filepath
            self.input_player.setMedia(QMediaContent(QUrl.fromLocalFile(filepath)))
            self.input_player.pause()
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
