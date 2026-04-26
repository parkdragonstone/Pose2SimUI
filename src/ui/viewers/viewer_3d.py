"""
3D Keypoint 뷰어 — matplotlib Axes3D + 스켈레톤 오버레이
# Design Ref: §6.2 — Viewer3DWidget: scatter, line3d, QTimer 애니메이션
# Note: macOS ARM64 (Apple Silicon) OpenGL 미지원으로 matplotlib 소프트웨어 렌더링 사용
"""
from pathlib import Path
import math

import numpy as np
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QSlider, QLabel, QComboBox,
    QSizePolicy,
)
from PyQt5.QtCore import Qt, QTimer

_MPL_AVAILABLE = False
_MPL_ERROR = ""
try:
    import matplotlib
    matplotlib.use("Qt5Agg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401  — registers 3d projection
    import mpl_toolkits.mplot3d.axes3d  # noqa: F401
    import mpl_toolkits.mplot3d.art3d   # noqa: F401
    _MPL_AVAILABLE = True
except Exception as _e:
    _MPL_ERROR = str(_e)

from src.core.project import Trial
from src.core.trc_parser import TRCData, parse_trc
from src.ui.widgets.empty_state import EmptyState


# ── 색상 ────────────────────────────────────────────────────────────
_C_RIGHT  = "#C0392B"
_C_LEFT   = "#4A86C8"
_C_CENTER = "#E8922A"
_C_EXTRA  = "#8B7355"
_BG       = "#0D0F14"

# ── 스켈레톤 연결 (마커 이름 기준) ──────────────────────────────────
_NAME_CONNECTIONS: list[tuple[str, str]] = [
    ("Hip", "RHip"), ("Hip", "LHip"), ("RHip", "LHip"),
    ("Hip", "Neck"),
    ("Neck", "Head"), ("Head", "Nose"),
    ("Neck", "RShoulder"), ("RShoulder", "RElbow"), ("RElbow", "RWrist"),
    ("Neck", "LShoulder"), ("LShoulder", "LElbow"), ("LElbow", "LWrist"),
    ("RShoulder", "LShoulder"),
    ("RHip", "RKnee"), ("RKnee", "RAnkle"),
    ("RAnkle", "RBigToe"), ("RBigToe", "RSmallToe"), ("RAnkle", "RHeel"),
    ("LHip", "LKnee"), ("LKnee", "LAnkle"),
    ("LAnkle", "LBigToe"), ("LBigToe", "LSmallToe"), ("LAnkle", "LHeel"),
]


def _side_color(name: str) -> str:
    if name.startswith("R"):
        return _C_RIGHT
    if name.startswith("L"):
        return _C_LEFT
    return _C_CENTER


def _build_connections(marker_names: list[str]) -> list[tuple[int, int]]:
    idx = {n: i for i, n in enumerate(marker_names)}
    return [(idx[a], idx[b]) for a, b in _NAME_CONNECTIONS
            if a in idx and b in idx]


# ── QSS ─────────────────────────────────────────────────────────────
_SLIDER_SS = """
QSlider::groove:horizontal { height:3px; background:#CBD5E1; border-radius:1px; }
QSlider::sub-page:horizontal { background:#2563EB; border-radius:1px; }
QSlider::handle:horizontal {
    background:#2563EB; border:2px solid #1D4ED8;
    width:14px; height:14px; border-radius:7px; margin:-6px 0;
}
"""
_PLAY_LABEL  = "PLAY"
_PAUSE_LABEL = "PAUSE"


# ── 커스텀 캔버스 (휠=줌, 우클릭=이동) ──────────────────────────────
class _Canvas3D(FigureCanvasQTAgg):
    """
    스크롤=줌(_view_half 스케일링), 우클릭드래그=이동(incremental + 방위각 분해).
    Qt 레벨에서 처리해 matplotlib 버전 차이 무시.

    좌표 매핑: data(x,y,z) → display(z,x,y)
      display_x = data_z (깊이)
      display_y = data_x (좌우)
      display_z = data_y (수직 UP)
    """

    def __init__(self, fig):
        super().__init__(fig)
        self._ax3d = None
        self._pan_last: tuple | None = None

    # ── 휠: 줌 (ax.dist 조정 — limits는 고정 유지) ─────────────
    def wheelEvent(self, event):
        if self._ax3d is not None:
            dy = event.angleDelta().y()
            if dy:
                factor = 0.88 if dy > 0 else 1.14   # 위=줌인
                ax = self._ax3d
                for get_lim, set_lim in [(ax.get_xlim, ax.set_xlim),
                                         (ax.get_ylim, ax.set_ylim),
                                         (ax.get_zlim, ax.set_zlim)]:
                    lo, hi = get_lim()
                    c = (lo + hi) / 2
                    h = (hi - lo) / 2 * factor
                    set_lim(c - h, c + h)
                self.draw_idle()
        event.accept()

    # ── 우클릭: 이동 시작 ────────────────────────────────────────
    def mousePressEvent(self, event):
        if self._ax3d and event.button() == Qt.RightButton:
            self._pan_last = (event.pos().x(), event.pos().y())
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.RightButton:
            self._pan_last = None
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    # ── 우클릭 드래그: _view_center 이동 후 재렌더 ──────────────
    def mouseMoveEvent(self, event):
        if (self._pan_last and self._ax3d and event.buttons() & Qt.RightButton):
            dx = (event.pos().x() - self._pan_last[0]) / max(self.width(), 1)
            dy = (event.pos().y() - self._pan_last[1]) / max(self.height(), 1)
            self._pan_last = (event.pos().x(), event.pos().y())

            ax = self._ax3d
            xl0, xl1 = ax.get_xlim()
            yl0, yl1 = ax.get_ylim()
            zl0, zl1 = ax.get_zlim()
            xr = xl1 - xl0
            yr = yl1 - yl0
            zr = zl1 - zl0
            a = math.radians(ax.azim)
            sc = 2.0
            shift_x = -dx * (-math.sin(a)) * sc * xr
            shift_y = -dx * math.cos(a)    * sc * yr
            shift_z = dy * sc * zr

            ax.set_xlim(xl0 + shift_x, xl1 + shift_x)
            ax.set_ylim(yl0 + shift_y, yl1 + shift_y)
            ax.set_zlim(zl0 + shift_z, zl1 + shift_z)
            self.draw_idle()
            event.accept()
        else:
            super().mouseMoveEvent(event)


# ── 메인 위젯 ────────────────────────────────────────────────────────
class Viewer3DWidget(QWidget):
    """
    3D Keypoint 뷰어.
    TRC 파일을 로드해 프레임 단위로 스켈레톤을 matplotlib 3D로 렌더링.
    # Design Ref: §6.2 — Viewer3DWidget
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._trc_data: TRCData | None = None
        self._frame_idx = 0
        self._playing = False
        self._xlim: tuple | None = None
        self._ylim: tuple | None = None
        self._zlim: tuple | None = None
        self._connections: list[tuple[int, int]] = []
        self._connected_set: frozenset = frozenset()
        self._marker_colors: list[str] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if not _MPL_AVAILABLE:
            layout.addWidget(EmptyState(
                f"3D 뷰어를 초기화할 수 없습니다.\n{_MPL_ERROR}"
            ))
            return

        # ── 데이터 선택 바 ─────────────────────────────────────────
        top_bar = QWidget()
        tl = QHBoxLayout(top_bar)
        tl.setContentsMargins(8, 6, 8, 4)
        tl.setSpacing(8)
        lbl = QLabel("데이터")
        lbl.setStyleSheet("color:#64748B; font-size:11px;")
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        tl.addWidget(lbl)
        self._file_combo = QComboBox()
        self._file_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._file_combo.currentIndexChanged.connect(self._on_file_selected)
        tl.addWidget(self._file_combo)
        layout.addWidget(top_bar)

        # ── 재생 컨트롤 바 ─────────────────────────────────────────
        ctrl_bar = QWidget()
        cl = QHBoxLayout(ctrl_bar)
        cl.setContentsMargins(8, 2, 8, 6)
        cl.setSpacing(10)
        self._play_btn = QPushButton(_PLAY_LABEL)
        self._play_btn.setFixedSize(62, 26)
        self._play_btn.clicked.connect(self._toggle_play)
        cl.addWidget(self._play_btn)
        self._frame_slider = QSlider(Qt.Horizontal)
        self._frame_slider.setRange(0, 0)
        self._frame_slider.setStyleSheet(_SLIDER_SS)
        self._frame_slider.sliderMoved.connect(self._seek)
        cl.addWidget(self._frame_slider, 1)
        self._frame_label = QLabel("0 / 0")
        self._frame_label.setStyleSheet("color:#64748B; font-size:11px; min-width:60px;")
        self._frame_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        cl.addWidget(self._frame_label)
        layout.addWidget(ctrl_bar)

        # ── matplotlib 3D 캔버스 ──────────────────────────────────
        self._fig = Figure(facecolor=_BG)
        self._canvas = _Canvas3D(self._fig)
        self._canvas.setMinimumHeight(320)
        self._ax = self._fig.add_subplot(111, projection="3d")
        self._canvas._ax3d = self._ax          # 커스텀 캔버스에 축 연결
        self._fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
        self._style_axes()
        layout.addWidget(self._canvas, 1)

        # ── 힌트 ──────────────────────────────────────────────────
        hint_bar = QWidget()
        hl = QHBoxLayout(hint_bar)
        hl.setContentsMargins(8, 2, 8, 4)
        hl.addStretch()
        hint = QLabel("좌클릭: 회전  |  우클릭 드래그: 이동  |  휠: 줌")
        hint.setStyleSheet("color:#475569; font-size:10px;")
        hl.addWidget(hint)
        layout.addWidget(hint_bar)

        # ── 빈 상태 ──────────────────────────────────────────────
        self._empty = EmptyState(
            "3D Keypoint 파일 없음\n"
            "pose-3d/ 폴더에 .trc 파일을 추가하세요"
        )
        layout.addWidget(self._empty)
        self._empty.hide()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._next_frame)

    # ── 축 스타일 ─────────────────────────────────────────────────

    def _style_axes(self):
        ax = self._ax
        ax.set_facecolor(_BG)
        ax.grid(False)
        for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
            axis.pane.fill = False
            axis.pane.set_edgecolor("none")
            axis.line.set_color("none")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_zticks([])
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.set_zlabel("")
        try:
            ax.set_box_aspect([1, 1, 1])   # 등비율 축
        except Exception:
            pass

    # ── 공개 API ─────────────────────────────────────────────────

    def load_trial(self, trial: Trial):
        if not _MPL_AVAILABLE:
            return
        self._stop()
        self._file_combo.blockSignals(True)
        self._file_combo.clear()
        trc_files = trial.trc_files()
        if not trc_files:
            self._show_empty(True)
            self._file_combo.blockSignals(False)
            return
        self._show_empty(False)
        for f in trc_files:
            self._file_combo.addItem(f.name, userData=f)
        preferred = trial.default_trc_path()
        if preferred:
            idx = self._file_combo.findText(preferred.name)
            if idx >= 0:
                self._file_combo.setCurrentIndex(idx)
        self._file_combo.blockSignals(False)
        self._load_trc(Path(self._file_combo.currentData()))

    def load_trc(self, trc_data: TRCData):
        if not _MPL_AVAILABLE:
            return
        self._stop()
        self._trc_data = trc_data
        self._frame_idx = 0
        n = trc_data.n_frames
        self._frame_slider.setRange(0, max(n - 1, 0))
        fps = trc_data.frame_rate or 30.0
        self._timer.setInterval(max(1, int(1000 / fps)))

        # 마커 이름 기반 연결·색상
        self._connections = _build_connections(trc_data.marker_names)
        self._connected_set = frozenset(i for p in self._connections for i in p)
        self._marker_colors = [_side_color(nm) for nm in trc_data.marker_names]

        # 전체 데이터 기준 등비율 큐브 바운딩 박스 계산
        self._compute_limits(trc_data)

        # 초기 뷰 설정 — Hip 중심 기준 limits 적용
        self._ax.azim = -60
        self._ax.elev = 15
        if self._xlim:
            self._ax.set_xlim(*self._xlim)
            self._ax.set_ylim(*self._ylim)
            self._ax.set_zlim(*self._zlim)

        if n > 0:
            self._render_frame(0)
        self._show_empty(n == 0)

    # ── 내부 메서드 ───────────────────────────────────────────────

    def _compute_limits(self, data: TRCData):
        """등비율 큐브 바운딩 박스. 중심 = Hip 평균 위치.

        좌표매칭: data(x,y,z) -> display(z,x,y)
        display_x = data_z (깊이)
        display_y = data_x (좌우)
        display_z = data_y (수직 UP)
        Hip을 중심으로 설정해 회전의 골반 기준이 되도록함.
        """
        all_pts = data.frames.reshape(-1, 3)
        valid = all_pts[~np.any(np.isnan(all_pts), axis=1)]
        if not len(valid):
            self._xlim = self._ylim = self._zlim = (-1.0, 1.0)
            return

        mn = valid.min(axis=0)
        mx = valid.max(axis=0)
        half = float((mx - mn).max() / 2.0) * 1.3

        hip_idx = next(
            (i for i, n in enumerate(data.marker_names) if n.lower() in ("hip", "pelvis", "hips")),
            None,
        )
        if hip_idx is not None:
            hip_pts = data.frames[:, hip_idx, :]
            hip_valid = hip_pts[~np.any(np.isnan(hip_pts), axis=1)]
            center = hip_valid.mean(axis=0) if len(hip_valid) else (mn + mx) / 2
        else:
            center = (mn + mx) / 2

        # data(x,y,z) → display(z,x,y)
        cx = float(center[2])
        cy = float(center[0])
        cz = float(center[1])
        self._xlim = (cx - half, cx + half)
        self._ylim = (cy - half, cy + half)
        self._zlim = (cz - half, cz + half)

    def _load_trc(self, path: Path):
        try:
            self.load_trc(parse_trc(path))
        except Exception as e:
            import traceback
            print(f"[Viewer3D] _load_trc failed: {e}\n{traceback.format_exc()}")
            self._show_empty(True)

    def _on_file_selected(self, idx: int):
        path = self._file_combo.itemData(idx)
        if path:
            self._load_trc(Path(path))

    def _render_frame(self, idx: int):
        if self._trc_data is None or self._trc_data.n_frames == 0:
            return
        pts = self._trc_data.frames[idx]   # (N_markers, 3)
        ax = self._ax
        
        azim = ax.azim
        elev = ax.elev
        saved_xlim = ax.get_xlim()
        saved_ylim = ax.get_ylim()
        saved_zlim = ax.get_zlim()
        ax.cla()
        self._style_axes()

        # 좌표 매핑: data(x,y,z) → display(z,x,y), 뷰 중심 기준 상대 좌표
        # ── 비연결 관절: 작은 탄색 점 ────────────────────────────
        extra = [i for i in range(len(pts)) if i not in self._connected_set]
        if extra:
            ep = pts[extra]
            ax.scatter(ep[:, 2], ep[:, 0], ep[:, 1],
                       c=_C_EXTRA, s=14, depthshade=True, alpha=0.65, zorder=3)

        # ── 뼈대 연결선 ──────────────────────────────────────────
        for a_idx, b_idx in self._connections:
            if a_idx < len(pts) and b_idx < len(pts):
                ca, cb = self._marker_colors[a_idx], self._marker_colors[b_idx]
                color = ca if ca == cb else "#7A6A5A"
                ax.plot([pts[a_idx, 2], pts[b_idx, 2]],
                        [pts[a_idx, 0], pts[b_idx, 0]],
                        [pts[a_idx, 1], pts[b_idx, 1]],
                        color=color, linewidth=2.0, alpha=0.92, zorder=4)

        # ── 연결 관절: 큰 컬러 점 ────────────────────────────────
        conn = [i for i in range(len(pts)) if i in self._connected_set]
        if conn:
            cp = pts[conn]
            ax.scatter(cp[:, 2], cp[:, 0], cp[:, 1],
                       c=[self._marker_colors[i] for i in conn],
                       s=38, depthshade=False, zorder=5)

        # ── 전역 좌표계 화살표 ────────────────────────────────────
        self._draw_coord_axes()

        # ── limits 고정 + 뷰 상태 복원 ──────────────────────────
        ax.set_xlim(saved_xlim)
        ax.set_ylim(saved_ylim)
        ax.set_zlim(saved_zlim)
        ax.azim = azim
        ax.elev = elev

        self._canvas.draw_idle()
        self._frame_slider.setValue(idx)
        self._frame_label.setText(f"{idx + 1} / {self._trc_data.n_frames}")

    def _draw_coord_axes(self):
        """전역 원점(0,0,0)에 X(빨강)/Y(초록·수직UP)/Z(파랑) 화살표.
        data(x,y,z) → display(z,x,y) 매핑 기준:
        data X 방향 → display Y 방향  → quiver(0,0,0,0,scale,0)
        data Y 방향 → display Z 방향(UP) → quiver(0,0
        quiver 인수 순서: (x0,display_y0,display_z0, dx,display_dy,display_dz
        """
        if self._xlim is None:
            return
        scale = (self._xlim[1] - self._xlim[0]) * 0.15
        kw = dict(arrow_length_ratio=0.25, linewidth=2.0, alpha=0.9)
        ax = self._ax
        ax.quiver(0, 0, 0, 0, scale, 0, color="#EF4444", **kw)
        ax.quiver(0, 0, 0, 0, 0, scale, color="#22C55E", **kw)
        ax.quiver(0, 0, 0, scale, 0, 0, color="#3B82F6", **kw)
        off = scale * 1.3
        ax.text(0,       0 + off, 0,       "X", color="#EF4444", fontsize=8, fontweight="bold")
        ax.text(0,       0,       0 + off, "Y", color="#22C55E", fontsize=8, fontweight="bold")
        ax.text(0 + off, 0,       0,       "Z", color="#3B82F6", fontsize=8, fontweight="bold")

    def _next_frame(self):
        if self._trc_data is None:
            return
        self._frame_idx = (self._frame_idx + 1) % self._trc_data.n_frames
        self._render_frame(self._frame_idx)

    def _toggle_play(self):
        if not self._trc_data or self._trc_data.n_frames == 0:
            return
        self._playing = not self._playing
        if self._playing:
            self._timer.start()
            self._play_btn.setText(_PAUSE_LABEL)
        else:
            self._timer.stop()
            self._play_btn.setText(_PLAY_LABEL)

    def _stop(self):
        self._playing = False
        self._timer.stop()
        if _MPL_AVAILABLE and hasattr(self, "_play_btn"):
            self._play_btn.setText(_PLAY_LABEL)
        self._frame_idx = 0

    def _seek(self, value: int):
        self._frame_idx = value
        self._render_frame(value)

    def _show_empty(self, show: bool):
        if hasattr(self, "_canvas"):
            self._canvas.setVisible(not show)
        if hasattr(self, "_empty"):
            self._empty.setVisible(show)
