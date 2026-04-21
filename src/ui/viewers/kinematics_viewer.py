"""
Kinematics 관절 각도 뷰어 — 토글 버튼 그리드 + 흰 배경 pyqtgraph 차트
# Design Ref: §6.3 — KinematicsViewerWidget
"""
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QSizePolicy, QComboBox,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QPainter, QColor, QIcon

try:
    import pyqtgraph as pg
    import numpy as np
    _PG_AVAILABLE = True
except Exception:
    _PG_AVAILABLE = False

from src.core.project import Trial
from src.core.mot_parser import MOTData, parse_mot
from src.ui.widgets.empty_state import EmptyState


# ── 전체 신호 목록 (표시 순서 고정) ──────────────────────────────────
_ALL_SIGNALS: list[tuple[str, str]] = [
    ("pelvis_tilt",          "Pelvis Tilt"),
    ("pelvis_list",          "Pelvis List"),
    ("pelvis_rotation",      "Pelvis Rot"),
    ("L5_S1_Flex_Ext",       "Trunk Tilt"),
    ("L5_S1_Lat_Bending",    "Trunk List"),
    ("L5_S1_axial_rotation", "Trunk Rot"),
    ("hip_flexion_r",        "Hip Flex R"),
    ("hip_flexion_l",        "Hip Flex L"),
    ("hip_adduction_r",      "Hip Abd R"),
    ("hip_adduction_l",      "Hip Abd L"),
    ("hip_rotation_r",       "Hip Rot R"),
    ("hip_rotation_l",       "Hip Rot L"),
    ("knee_angle_r",         "Knee Flex R"),
    ("knee_angle_l",         "Knee Flex L"),
    ("ankle_angle_r",        "Ankle Flex R"),
    ("ankle_angle_l",        "Ankle Flex L"),
    ("arm_flex_r",           "Arm Flex R"),
    ("arm_flex_l",           "Arm Flex L"),
    ("arm_add_r",            "Arm Abd R"),
    ("arm_add_l",            "Arm Abd L"),
    ("arm_rot_r",            "Arm Rot R"),
    ("arm_rot_l",            "Arm Rot L"),
    ("elbow_flex_r",         "Elbow Flex R"),
    ("elbow_flex_l",         "Elbow Flex L"),
    ("pro_sup_r",            "Pro Sup R"),
    ("pro_sup_l",            "Pro Sup L"),
    ("wrist_flex_r",         "Wrist Flex R"),
    ("wrist_flex_l",         "Wrist Flex L"),
]

_COLS = 7   # 버튼 행당 열 수

# 신호별 고유 색상 (28개 전부 다름)
_SIGNAL_COLORS: dict[str, str] = {
    "pelvis_tilt":          "#E53935",
    "pelvis_list":          "#8E24AA",
    "pelvis_rotation":      "#3949AB",
    "L5_S1_Flex_Ext":       "#039BE5",
    "L5_S1_Lat_Bending":    "#00897B",
    "L5_S1_axial_rotation": "#43A047",
    "hip_flexion_r":        "#F4511E",
    "hip_flexion_l":        "#FB8C00",
    "hip_adduction_r":      "#F9A825",
    "hip_adduction_l":      "#7CB342",
    "hip_rotation_r":       "#0097A7",
    "hip_rotation_l":       "#1E88E5",
    "knee_angle_r":         "#5E35B1",
    "knee_angle_l":         "#D81B60",
    "ankle_angle_r":        "#6D4C41",
    "ankle_angle_l":        "#546E7A",
    "arm_flex_r":           "#C0392B",
    "arm_flex_l":           "#2980B9",
    "arm_add_r":            "#27AE60",
    "arm_add_l":            "#E67E22",
    "arm_rot_r":            "#8E44AD",
    "arm_rot_l":            "#16A085",
    "elbow_flex_r":         "#2C3E50",
    "elbow_flex_l":         "#E91E63",
    "pro_sup_r":            "#00838F",
    "pro_sup_l":            "#558B2F",
    "wrist_flex_r":         "#6A1B9A",
    "wrist_flex_l":         "#BF360C",
}


def _dot_icon(color: str) -> QIcon:
    """지정 색상의 8px 원형 아이콘."""
    px = QPixmap(10, 10)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(1, 1, 8, 8)
    p.end()
    return QIcon(px)


_BTN_OFF_SS = (
    "QPushButton {"
    " background:white; color:#1E293B;"
    " border:1.5px solid #CBD5E1; border-radius:12px;"
    " padding:0px 8px 0px 4px; font-size:10px;"
    " max-height:20px;"
    "}"
    "QPushButton:hover { background:#F1F5F9; border-color:#94A3B8; }"
)


def _btn_on_ss(color: str) -> str:
    return (
        f"QPushButton {{"
        f" background:{color}; color:white;"
        f" border:1.5px solid {color}; border-radius:12px;"
        f" padding:0px 8px 0px 4px; font-size:10px;"
        f" max-height:20px;"
        f"}}"
    )

# ── 더블클릭 리셋 PlotWidget ─────────────────────────────────────────

class _PlotWidget(pg.PlotWidget):
    """더블클릭으로 자동 범위 복원."""
    def mouseDoubleClickEvent(self, ev):
        self.autoRange()
        ev.accept()


# ── KinematicsViewerWidget ───────────────────────────────────────────

class KinematicsViewerWidget(QWidget):
    """
    .mot 파일 관절 각도 — 토글 버튼 그리드 + 흰 배경 그래프
    # Design Ref: §6.3 — KinematicsViewerWidget
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mot: MOTData | None = None
        self._curves:  dict[str, pg.PlotDataItem] = {}   # key → curve
        self._btn_map: dict[str, QPushButton]     = {}   # key → button
        self._color_map: dict[str, str]           = {}   # key → hex color
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 4, 0, 0)
        root.setSpacing(6)

        if not _PG_AVAILABLE:
            root.addWidget(EmptyState(
                "pyqtgraph를 불러올 수 없습니다.\n"
                "pip install pyqtgraph 을 실행해주세요."
            ))
            return

        # ── 파일 선택 (복수 파일 시만 표시) ──────────────────────────
        file_row = QHBoxLayout()
        file_row.setContentsMargins(4, 0, 4, 0)
        self._file_lbl = QLabel("파일:")
        self._file_lbl.setStyleSheet("font-size:11px;")
        file_row.addWidget(self._file_lbl)
        self._file_combo = QComboBox()
        self._file_combo.setMinimumWidth(200)
        self._file_combo.currentIndexChanged.connect(self._on_file_selected)
        file_row.addWidget(self._file_combo, 1)
        self._file_row_w = QWidget()
        self._file_row_w.setLayout(file_row)
        root.addWidget(self._file_row_w)
        self._file_row_w.hide()

        # ── 버튼 그리드 (신호 토글) ───────────────────────────────────
        self._btn_grid = QGridLayout()
        self._btn_grid.setSpacing(4)
        self._btn_grid.setContentsMargins(4, 0, 4, 0)
        for c in range(_COLS):
            self._btn_grid.setColumnStretch(c, 1)
        self._btn_w = QWidget()
        self._btn_w.setLayout(self._btn_grid)
        root.addWidget(self._btn_w)

        # ── pyqtgraph 흰 배경 차트 ────────────────────────────────────
        self._plot = _PlotWidget()
        self._plot.setBackground("white")
        self._plot.showGrid(x=False, y=True, alpha=0.3)
        self._plot.setMinimumHeight(240)
        self._plot.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        # 축 색상: 검정
        for axis in ("left", "bottom"):
            ax = self._plot.getAxis(axis)
            ax.setPen(pg.mkPen("#333333"))
            ax.setTextPen(pg.mkPen("#333333"))
        self._plot.getAxis("left").setTickSpacing(major=45, minor=15)
        self._plot.setLabel("left",   "Angle (deg)", color="#333333", size="10pt")
        self._plot.setLabel("bottom", "Time (s)",    color="#333333", size="10pt")
        # x축 0 이하로 이동 불가
        self._plot.setLimits(xMin=0)
        self._plot.addLegend(offset=(10, 10))
        root.addWidget(self._plot, 1)

        # ── 빈 상태 ─────────────────────────────────────────────────
        self._empty = EmptyState(
            "Kinematics 파일 없음\n"
            "kinematics/ 폴더에 .mot 파일을 추가하세요"
        )
        root.addWidget(self._empty)
        self._empty.hide()

    # ── 공개 API ─────────────────────────────────────────────────

    def load_trial(self, trial: Trial):
        if not _PG_AVAILABLE:
            return
        self._reset()
        mot_files = trial.mot_files()
        if not mot_files:
            self._show_empty(True)
            return
        self._show_empty(False)

        self._file_combo.blockSignals(True)
        self._file_combo.clear()
        for f in mot_files:
            self._file_combo.addItem(f.name, userData=f)
        self._file_combo.blockSignals(False)
        self._file_row_w.setVisible(len(mot_files) > 1)

        self._load_mot(Path(self._file_combo.currentData()))

    # ── 내부 ─────────────────────────────────────────────────────

    def _load_mot(self, path: Path):
        try:
            self._mot = parse_mot(path)
        except Exception:
            self._show_empty(True)
            return
        self._show_empty(False)
        self._build_buttons()

    def _on_file_selected(self, idx: int):
        path = self._file_combo.itemData(idx)
        if path:
            self._reset_curves_and_buttons()
            self._load_mot(Path(path))

    def _build_buttons(self):
        """데이터에 존재하는 신호만 버튼으로 생성."""
        if self._mot is None:
            return
        # 기존 버튼 제거
        while self._btn_grid.count():
            item = self._btn_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._btn_map.clear()
        self._color_map.clear()

        pos = 0
        for key, name in _ALL_SIGNALS:
            if key not in self._mot.data:
                continue
            color = _SIGNAL_COLORS.get(key, "#64748B")
            self._color_map[key] = color

            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setChecked(False)
            btn.setIcon(_dot_icon(color))
            btn.setIconSize(QSize(9, 9))
            btn.setStyleSheet(_BTN_OFF_SS)
            btn.clicked.connect(lambda checked, k=key: self._on_toggle(k, checked))
            self._btn_map[key] = btn
            row, col = divmod(pos, _COLS)
            self._btn_grid.addWidget(btn, row, col)
            pos += 1

    def _on_toggle(self, key: str, checked: bool):
        btn = self._btn_map.get(key)
        if btn is None:
            return
        color = self._color_map.get(key, "#C53030")
        if checked:
            btn.setStyleSheet(_btn_on_ss(color))
            btn.setIcon(_dot_icon("#FFFFFF"))
        else:
            btn.setStyleSheet(_BTN_OFF_SS)
            btn.setIcon(_dot_icon(color))

        if checked:
            self._add_curve(key)
        else:
            self._remove_curve(key)

    def _add_curve(self, key: str):
        if self._mot is None or key in self._curves:
            return
        color = self._color_map.get(key, "#333333")
        # 표시명 찾기
        name = next((n for k, n in _ALL_SIGNALS if k == key), key)
        curve = self._plot.plot(
            self._mot.time,
            self._mot.data[key],
            pen=pg.mkPen(color, width=2),
            name=name,
        )
        self._curves[key] = curve
        self._plot.autoRange()

    def _remove_curve(self, key: str):
        curve = self._curves.pop(key, None)
        if curve is not None:
            self._plot.removeItem(curve)
        try:
            self._plot.getPlotItem().legend.removeItem(
                next((n for k, n in _ALL_SIGNALS if k == key), key)
            )
        except Exception:
            pass

    def _reset_curves_and_buttons(self):
        for curve in self._curves.values():
            self._plot.removeItem(curve)
        self._curves.clear()
        try:
            self._plot.getPlotItem().legend.clear()
        except Exception:
            pass
        for key, btn in self._btn_map.items():
            btn.setChecked(False)
            btn.setStyleSheet(_BTN_OFF_SS)
            btn.setIcon(_dot_icon(self._color_map.get(key, "#64748B")))

    def _reset(self):
        self._reset_curves_and_buttons()
        while self._btn_grid.count():
            item = self._btn_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._btn_map.clear()
        self._color_map.clear()
        self._mot = None
        self._file_combo.blockSignals(True)
        self._file_combo.clear()
        self._file_combo.blockSignals(False)

    def _show_empty(self, show: bool):
        self._plot.setVisible(not show)
        self._btn_w.setVisible(not show)
        self._empty.setVisible(show)
