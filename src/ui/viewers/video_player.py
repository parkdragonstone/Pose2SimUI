"""
Pose Estimation 영상 멀티캠 뷰어 — QMediaPlayer × QVideoWidget, 공유 컨트롤 동기화
# Design Ref: §6.1 — VideoPlayerWidget: 카메라별 QVideoWidget 그리드, 공유 슬라이더
"""
import math
from pathlib import Path

import cv2

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QSlider, QLabel, QComboBox, QSizePolicy,
    QCheckBox,
)
from PyQt6.QtCore import Qt, QUrl, QTimer
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget

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

_GRID_FIXED_H = 340  # Videos 그리드 고정 높이 — Trial 전환 시 불변
_CELL_SPACING = 4   # 그리드 셀 간격


def _get_video_size(path: Path) -> tuple[int, int]:
    """cv2로 영상 해상도(w, h) 반환. 회전 메타데이터 반영. 실패 시 (16, 9) 반환."""
    try:
        cap = cv2.VideoCapture(str(path))
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        rotation = int(cap.get(cv2.CAP_PROP_ORIENTATION_META))
        cap.release()
        if w <= 0 or h <= 0:
            return (16, 9)
        if rotation in (90, 270):
            w, h = h, w
        return (w, h)
    except Exception:
        return (16, 9)


class VideoPlayerWidget(QWidget):
    """
    모든 카메라 영상을 QGridLayout + QVideoWidget으로 동시 표시.
    플랫폼 네이티브 렌더링(macOS: AVFoundation) — CPU 프레임 변환 없음.
    # Design Ref: §6.1 — VideoPlayerWidget
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._players: list[QMediaPlayer]       = []
        self._audio_outputs: list[QAudioOutput] = []
        self._video_widgets: list[QVideoWidget] = []
        self._duration_ms  = 0
        self._loop         = False
        self._current_videos: list[Path] = []
        self._grid_portrait = False
        self._setup_ui()

    # ── 레이아웃 ────────────────────────────────────────────────

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        ctrl = QHBoxLayout()
        ctrl.setContentsMargins(4, 2, 4, 2)
        ctrl.setSpacing(6)

        self._play_btn = QPushButton("PLAY")
        self._play_btn.setFixedSize(62, 26)
        self._play_btn.setToolTip("재생/일시정지 (Space)")
        self._play_btn.clicked.connect(self._toggle_play_pause)
        ctrl.addWidget(self._play_btn)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 1000)
        self._slider.setStyleSheet(_SLIDER_SS)
        self._slider.sliderMoved.connect(self._seek_all_from_slider)
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
        self._speed_box.setMinimumContentsLength(5)
        self._speed_box.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._speed_box.currentIndexChanged.connect(self._set_speed)
        ctrl.addWidget(self._speed_box)

        loop_cb = QCheckBox("Loop")
        loop_cb.stateChanged.connect(lambda s: setattr(self, "_loop", bool(s)))
        ctrl.addWidget(loop_cb)

        outer.addLayout(ctrl)

        self._grid_widget = QWidget()
        self._grid_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._grid_widget.setFixedHeight(_GRID_FIXED_H)
        self._grid_layout = QGridLayout(self._grid_widget)
        self._grid_layout.setContentsMargins(4, 0, 4, 4)
        self._grid_layout.setSpacing(_CELL_SPACING)
        outer.addWidget(self._grid_widget)
        outer.addStretch(1)

        self._empty = EmptyState(
            "영상 없음\n"
            "videos/ 폴더에 영상 파일을 추가하세요"
        )
        outer.addWidget(self._empty)
        self._empty.hide()

        self._timer = QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._update_slider)

    # ── 공개 API ─────────────────────────────────────────────

    def load_trial(self, trial: Trial):
        """
        Trial 교체 시 호출.
        Pose 영상이 있으면 pose/ 우선, 없으면 videos/ 원본.
        # Design Ref: §2.1 — VideoPlayer 영상 선택 로직
        """
        self._clear()
        videos = trial.pose_videos() if trial.has_pose_video else trial.raw_videos()
        if not videos:
            self._empty.show()
            self._grid_widget.hide()
            return

        self._empty.hide()
        self._grid_widget.show()
        self._current_videos = list(videos)

        vw, vh = _get_video_size(videos[0])
        portrait            = vh > vw
        self._grid_portrait = portrait

        n = len(videos)
        if portrait:
            total_cols = 4
            for c in range(total_cols):
                self._grid_layout.setColumnStretch(c, 1)
            start = (total_cols - min(n, total_cols)) // 2
            for i, vpath in enumerate(videos[:total_cols]):
                cell, player = self._make_camera_cell(vpath, delay_ms=i * 400)
                self._grid_layout.addWidget(cell, 0, start + i)
                self._players.append(player)
            self._grid_layout.setRowStretch(0, 1)
        else:
            cols      = 2
            rows_used = math.ceil(n / cols)
            for c in range(cols):
                self._grid_layout.setColumnStretch(c, 1)
            for i, vpath in enumerate(videos):
                row, col = divmod(i, cols)
                cell, player = self._make_camera_cell(vpath, delay_ms=i * 400)
                self._grid_layout.addWidget(cell, row, col)
                self._players.append(player)
            for r in range(rows_used):
                self._grid_layout.setRowStretch(r, 1)

        if self._players:
            self._players[0].durationChanged.connect(self._on_duration_changed)
            self._players[0].positionChanged.connect(self._on_position_changed)

    # ── 셀 생성 ──────────────────────────────────────────────

    def _make_camera_cell(self, video_path: Path, delay_ms: int = 0):
        player = QMediaPlayer()
        audio  = QAudioOutput()
        audio.setVolume(0.0)
        player.setAudioOutput(audio)
        self._audio_outputs.append(audio)

        vw = QVideoWidget()
        vw.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        vw.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._video_widgets.append(vw)

        player.setVideoOutput(vw)
        player.setSource(QUrl.fromLocalFile(str(video_path)))

        def _show_first_frame(p=player):
            if p.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
                p.play()
                p.pause()

        def _on_status(status, p=player):
            if status == QMediaPlayer.MediaStatus.LoadedMedia:
                QTimer.singleShot(delay_ms, lambda p=p: _show_first_frame(p))
            elif status == QMediaPlayer.MediaStatus.EndOfMedia:
                self._on_media_status(status, p)

        player.mediaStatusChanged.connect(_on_status)

        cam_name = video_path.stem.replace("_pose", "").replace("_", " ")
        name_lbl = QLabel(cam_name)
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_lbl.setStyleSheet("color: #64748B; font-size: 10px; padding: 2px 0;")
        name_lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        cell = QWidget()
        cl = QVBoxLayout(cell)
        cl.setContentsMargins(2, 2, 2, 2)
        cl.setSpacing(2)
        cl.addWidget(name_lbl)
        cl.addWidget(vw, 1)
        return cell, player

    # ── 내부 헬퍼 ────────────────────────────────────────────

    def stop_all_players(self):
        """앱 종료 전 모든 QMediaPlayer를 안전하게 정지/해제."""
        self._timer.stop()
        for p in self._players:
            p.stop()
            p.setSource(QUrl())
        for a in self._audio_outputs:
            a.setVolume(0.0)

    def _clear(self):
        self.stop_all_players()
        self._players.clear()
        self._audio_outputs.clear()
        self._video_widgets.clear()
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        # 이전 trial의 column/row stretch 초기화
        for c in range(4):
            self._grid_layout.setColumnStretch(c, 0)
        for r in range(4):
            self._grid_layout.setRowStretch(r, 0)
        self._duration_ms    = 0
        self._slider.setValue(0)
        self._time_label.setText("0:00 / 0:00")
        self._current_videos = []

    # ── 컨트롤 핸들러 ────────────────────────────────────────

    def _toggle_play_pause(self):
        if not self._players:
            return
        if self._players[0].playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            for p in self._players:
                p.pause()
            self._play_btn.setText("PLAY")
            self._timer.stop()
        else:
            for p in self._players:
                p.play()
            self._play_btn.setText("PAUSE")
            self._timer.start()

    def _seek_all_from_slider(self, value: int):
        if self._duration_ms > 0:
            ms = int(value * self._duration_ms / 1000)
            for p in self._players:
                p.setPosition(ms)

    def _set_speed(self, idx: int):
        for p in self._players:
            p.setPlaybackRate([0.25, 0.5, 1.0, 1.5, 2.0][idx])

    def _on_duration_changed(self, duration: int):
        self._duration_ms = duration

    def _on_position_changed(self, pos: int):
        if self._duration_ms > 0:
            self._slider.setValue(int(pos * 1000 / self._duration_ms))
        self._time_label.setText(
            f"{self._fmt(pos)} / {self._fmt(self._duration_ms)}"
        )

    def _on_media_status(self, status, player: QMediaPlayer):
        if status == QMediaPlayer.MediaStatus.EndOfMedia and self._loop:
            player.setPosition(0)
            player.play()

    def _update_slider(self):
        if self._players:
            self._on_position_changed(self._players[0].position())

    @staticmethod
    def _is_portrait(video_path: Path) -> bool:
        w, h = _get_video_size(video_path)
        return h > w

    @staticmethod
    def _fmt(ms: int) -> str:
        s = ms // 1000
        return f"{s // 60}:{s % 60:02d}"
