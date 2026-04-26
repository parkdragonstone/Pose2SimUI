"""
멀티캠 뷰어 — OpenCV 순차 읽기 기반 (랜덤 접근 최소화로 렉 방지)
재생 중: cap.read() 순차 읽기만 사용
슬라이더 이동 시에만: cap.set(POS_FRAMES) 호출
# Design Ref: §6.1 — VideoPlayerWidget
"""
import math
from pathlib import Path

import cv2

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QSlider, QLabel, QComboBox, QSizePolicy,
    QCheckBox,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QImage, QPixmap

from src.core.project import Trial
from src.ui.widgets.empty_state import EmptyState

_SLIDER_SS = """
QSlider::groove:horizontal { height:3px; background:#CBD5E1; border-radius:1px; }
QSlider::sub-page:horizontal { background:#2563EB; border-radius:1px; }
QSlider::handle:horizontal {
    background:#2563EB; border:2px solid #1D4ED8;
    width:14px; height:14px; border-radius:7px; margin:-6px 0;
}
"""

_GRID_FIXED_H = 340
_CELL_SPACING = 4
_SPEEDS = [0.25, 0.5, 1.0, 1.5, 2.0]


def _bgr_to_pixmap(frame_bgr, target_w: int, target_h: int,
                   smooth: bool = False) -> QPixmap:
    """BGR 프레임 → 위젯 크기로 스케일된 QPixmap. 복사 최소화."""
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    img = QImage(rgb.data, w, h, rgb.strides[0], QImage.Format_RGB888)
    px = QPixmap.fromImage(img)
    if target_w > 0 and target_h > 0:
        tf = Qt.SmoothTransformation if smooth else Qt.FastTransformation
        px = px.scaled(target_w, target_h, Qt.KeepAspectRatio, tf)
    return px


class _CvDisplay(QLabel):
    """
    단일 카메라 표시용 QLabel.
    cap.read() 결과(BGR frame)를 직접 받아 렌더링.
    내부에 cv2.VideoCapture를 보유 — 슬라이더 seek 용도.
    """

    def __init__(self, path: Path, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background-color: #0F172A;")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._cap = cv2.VideoCapture(str(path))
        self._tw = 0
        self._th = 0

    # ── 공개 API ──────────────────────────────────────────────

    def read_next(self):
        """순차 읽기 — cap.set() 없이 바로 다음 프레임. 빠름."""
        return self._cap.read()

    def seek_and_read(self, frame_no: int):
        """랜덤 접근 — 슬라이더 이동 시에만 호출."""
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, frame_no))
        return self._cap.read()

    def render(self, frame_bgr, smooth: bool = False):
        px = _bgr_to_pixmap(frame_bgr, self._tw, self._th, smooth)
        self.setPixmap(px)

    def release(self):
        self._cap.release()

    # ── 위젯 크기 캐시 ──────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._tw = self.width()
        self._th = self.height()
        # 리사이즈 시 현재 픽스맵을 새 크기로 재스케일
        if self.pixmap() and not self.pixmap().isNull():
            self.setPixmap(self.pixmap().scaled(
                self._tw, self._th, Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))


class VideoPlayerWidget(QWidget):
    """
    멀티캠 OpenCV 뷰어.
    재생: cap.read() 순차 읽기 → 렉 없음
    Seek: cap.set() → 슬라이더 조작 시에만
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._displays: list[_CvDisplay] = []
        self._total_frames  = 0
        self._fps           = 30.0
        self._current_frame = 0
        self._playing       = False
        self._loop          = False
        self._speed_idx     = 2
        self._slider_dragging = False
        self._setup_ui()

    # ── 레이아웃 ──────────────────────────────────────────────

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        ctrl = QHBoxLayout()
        ctrl.setContentsMargins(4, 2, 4, 2)
        ctrl.setSpacing(6)

        self._play_btn = QPushButton("PLAY")
        self._play_btn.setFixedSize(62, 26)
        self._play_btn.clicked.connect(self._toggle_play_pause)
        ctrl.addWidget(self._play_btn)

        self._slider = QSlider(Qt.Horizontal)
        self._slider.setRange(0, 1000)
        self._slider.setStyleSheet(_SLIDER_SS)
        self._slider.sliderPressed.connect(self._on_slider_press)
        self._slider.sliderReleased.connect(self._on_slider_release)
        self._slider.sliderMoved.connect(self._on_slider_moved)
        ctrl.addWidget(self._slider, 1)

        self._time_label = QLabel("0:00 / 0:00")
        self._time_label.setStyleSheet("font-size: 11px; color: #64748B; min-width: 80px;")
        ctrl.addWidget(self._time_label)

        speed_lbl = QLabel("속도:")
        speed_lbl.setStyleSheet("font-size: 11px; color: #64748B;")
        ctrl.addWidget(speed_lbl)

        self._speed_box = QComboBox()
        self._speed_box.addItems(["0.25x", "0.5x", "1.0x", "1.5x", "2.0x"])
        self._speed_box.setCurrentIndex(2)
        self._speed_box.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self._speed_box.currentIndexChanged.connect(self._on_speed_changed)
        ctrl.addWidget(self._speed_box)

        loop_cb = QCheckBox("Loop")
        loop_cb.stateChanged.connect(lambda s: setattr(self, "_loop", bool(s)))
        ctrl.addWidget(loop_cb)

        outer.addLayout(ctrl)

        self._grid_widget = QWidget()
        self._grid_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._grid_widget.setFixedHeight(_GRID_FIXED_H)
        self._grid_layout = QGridLayout(self._grid_widget)
        self._grid_layout.setContentsMargins(4, 0, 4, 4)
        self._grid_layout.setSpacing(_CELL_SPACING)
        outer.addWidget(self._grid_widget)
        outer.addStretch(1)

        self._empty = EmptyState("영상 없음\nvideos/ 폴더에 영상 파일을 추가하세요")
        outer.addWidget(self._empty)
        self._empty.hide()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    # ── 공개 API ──────────────────────────────────────────────

    def load_trial(self, trial: Trial):
        self._clear()
        videos = trial.pose_videos() if trial.has_pose_video else trial.raw_videos()
        if not videos:
            self._empty.show()
            self._grid_widget.hide()
            return

        self._empty.hide()
        self._grid_widget.show()

        cap0 = cv2.VideoCapture(str(videos[0]))
        w    = int(cap0.get(cv2.CAP_PROP_FRAME_WIDTH))
        h    = int(cap0.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self._fps           = cap0.get(cv2.CAP_PROP_FPS) or 30.0
        self._total_frames  = max(1, int(cap0.get(cv2.CAP_PROP_FRAME_COUNT)))
        cap0.release()

        portrait = h > w
        n_vids = len(videos)

        if portrait:
            cols  = min(n_vids, 4)
            start = (4 - cols) // 2
            for c in range(4):
                self._grid_layout.setColumnStretch(c, 1)
            for i, vp in enumerate(videos[:cols]):
                cell, d = self._make_cell(vp)
                self._grid_layout.addWidget(cell, 0, start + i)
                self._displays.append(d)
            self._grid_layout.setRowStretch(0, 1)
        else:
            cols = 2
            rows = math.ceil(n_vids / cols)
            for c in range(cols):
                self._grid_layout.setColumnStretch(c, 1)
            for i, vp in enumerate(videos):
                r, c = divmod(i, cols)
                cell, d = self._make_cell(vp)
                self._grid_layout.addWidget(cell, r, c)
                self._displays.append(d)
            for r in range(rows):
                self._grid_layout.setRowStretch(r, 1)

        self._current_frame = 0
        self._update_ui(0)
        # 레이아웃 완성 후 첫 프레임 렌더링 — 즉시 호출하면 _tw/_th 가 0이라 스케일 안 됨
        QTimer.singleShot(0, lambda: self._seek_all(0, smooth=True))

    def stop_all_players(self):
        self._timer.stop()
        self._playing = False
        for d in self._displays:
            d.release()

    # ── 셀 생성 ───────────────────────────────────────────────

    def _make_cell(self, path: Path):
        d = _CvDisplay(path)
        name_lbl = QLabel(path.stem.replace("_pose", "").replace("_", " "))
        name_lbl.setAlignment(Qt.AlignCenter)
        name_lbl.setStyleSheet("color: #64748B; font-size: 10px; padding: 2px 0;")
        name_lbl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        cell = QWidget()
        cl = QVBoxLayout(cell)
        cl.setContentsMargins(2, 2, 2, 2)
        cl.setSpacing(2)
        cl.addWidget(name_lbl)
        cl.addWidget(d, 1)
        return cell, d

    # ── 타이머 콜백 (핵심 최적화) ──────────────────────────────

    def _tick(self):
        """재생 tick — 모든 캡에서 cap.read() 순차 읽기."""
        if self._slider_dragging:
            return
        next_f = self._current_frame + 1
        if next_f >= self._total_frames:
            if self._loop:
                self._seek_all(0)
                next_f = 0
            else:
                self._timer.stop()
                self._playing = False
                self._play_btn.setText("PLAY")
                return

        frames = [d.read_next() for d in self._displays]
        for d, (ret, frame) in zip(self._displays, frames):
            if ret:
                d.render(frame, smooth=False)

        self._current_frame = next_f
        self._update_ui(next_f)

    # ── 내부 헬퍼 ─────────────────────────────────────────────

    def _seek_all(self, frame_no: int, smooth: bool = False):
        """모든 캡을 frame_no로 seek 후 첫 프레임 표시."""
        frame_no = max(0, min(frame_no, self._total_frames - 1))
        for d in self._displays:
            ret, frame = d.seek_and_read(frame_no)
            if ret:
                d.render(frame, smooth=smooth)
        self._current_frame = frame_no

    def _update_ui(self, frame_no: int):
        fps = self._fps or 30.0
        if not self._slider_dragging and self._total_frames > 1:
            self._slider.setValue(int(frame_no * 1000 / (self._total_frames - 1)))
        cur_s = frame_no / fps
        tot_s = self._total_frames / fps
        self._time_label.setText(f"{self._fmt(cur_s)} / {self._fmt(tot_s)}")

    def _clear(self):
        self.stop_all_players()
        self._displays.clear()
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for c in range(4):
            self._grid_layout.setColumnStretch(c, 0)
        for r in range(4):
            self._grid_layout.setRowStretch(r, 0)
        self._total_frames  = 0
        self._current_frame = 0
        self._playing = False
        self._play_btn.setText("PLAY")
        self._slider.setValue(0)
        self._time_label.setText("0:00 / 0:00")

    def _restart_timer(self):
        interval = max(1, int(1000 / (self._fps * _SPEEDS[self._speed_idx])))
        self._timer.start(interval)

    # ── 컨트롤 핸들러 ─────────────────────────────────────────

    def _toggle_play_pause(self):
        if not self._displays:
            return
        if self._playing:
            self._timer.stop()
            self._playing = False
            self._play_btn.setText("PLAY")
            # 정지 시 현재 프레임 부드럽게 재렌더
            self._seek_all(self._current_frame, smooth=True)
        else:
            self._playing = True
            self._play_btn.setText("PAUSE")
            self._restart_timer()

    def _on_slider_press(self):
        self._slider_dragging = True
        self._timer.stop()

    def _on_slider_moved(self, value: int):
        if self._total_frames > 1:
            frame_no = int(value * (self._total_frames - 1) / 1000)
            self._seek_all(frame_no, smooth=False)
            self._update_ui(frame_no)

    def _on_slider_release(self):
        self._slider_dragging = False
        # Smooth render at resting position
        self._seek_all(self._current_frame, smooth=True)
        if self._playing:
            self._restart_timer()

    def _on_speed_changed(self, idx: int):
        self._speed_idx = idx
        if self._playing:
            self._restart_timer()

    @staticmethod
    def _fmt(seconds: float) -> str:
        s = int(seconds)
        return f"{s // 60}:{s % 60:02d}"
