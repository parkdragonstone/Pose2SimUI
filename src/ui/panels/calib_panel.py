"""
인라인 Calibration 패널 — Intrinsic + Extrinsic 탭, [Save as Calib.toml]
# Design Ref: §8.2 — CalibPanel 구조 (단일 폴더 선택 → 카메라 자동 탐색)
# Design Ref: §8.0 — 프로젝트 Calibration 폴더 구조
"""
import math
import re
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLabel, QTabWidget, QComboBox,
    QSpinBox, QDoubleSpinBox,
    QScrollArea, QGroupBox, QButtonGroup, QRadioButton,
    QFileDialog, QSizePolicy, QFrame, QTableWidget,
    QTableWidgetItem, QHeaderView, QPlainTextEdit,
    QDialog, QStackedWidget, QSlider,
    QGraphicsView, QGraphicsScene,
)
from PyQt6.QtCore import Qt, QUrl, pyqtSignal, QRectF
from PyQt6.QtGui import (
    QImage, QPixmap, QFont, QPainter, QPen, QBrush, QColor,
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget

from src.core.config_manager import ConfigManager
from src.ui.widgets.empty_state import EmptyState

_SLIDER_SS = """
QSlider::groove:horizontal { height:3px; background:#CBD5E1; border-radius:1px; }
QSlider::sub-page:horizontal { background:#2563EB; border-radius:1px; }
QSlider::handle:horizontal {
    background:#2563EB; border:2px solid #1D4ED8;
    width:14px; height:14px; border-radius:7px; margin:-6px 0;
}
"""


# ── 카메라 자동 탐색 헬퍼 ────────────────────────────────────────────

#: Intrinsic 허용 확장자
_VIDEO_EXTS: frozenset[str] = frozenset({".avi", ".mp4", ".mov"})

#: Extrinsic 허용 확장자 (영상 + 이미지)
_MEDIA_EXTS: frozenset[str] = frozenset({
    ".avi", ".mp4", ".mov",
    ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif",
})


def _discover_cameras(folder: Path, extensions: frozenset[str]) -> dict[str, list[Path]]:
    """
    폴더 내 파일에서 camXX 패턴을 추출해 카메라별로 그룹핑.
    반환: {"cam01": [path1, ...], "cam02": [path2, ...], ...}
    # Design Ref: §8.0 — discover_cameras
    """
    groups: dict[str, list[Path]] = {}
    for f in sorted(folder.iterdir()):
        if not f.is_file():
            continue
        if f.suffix.lower() not in extensions:
            continue
        m = re.search(r"cam(\d+)", f.name, re.IGNORECASE)
        if m:
            key = f"cam{m.group(1).zfill(2)}"
            groups.setdefault(key, []).append(f)
    return dict(sorted(groups.items()))


# ── 썸네일 헬퍼 ──────────────────────────────────────────────────────

_IMAGE_EXTS: frozenset[str] = frozenset({
    ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif",
})


def _load_thumbnail(path: Path, tw: int, th: int) -> QPixmap | None:
    """
    비디오 첫 프레임 또는 이미지 파일을 QPixmap 썸네일로 반환.
    실패 시 None.
    """
    ext = path.suffix.lower()
    try:
        if ext in _IMAGE_EXTS:
            px = QPixmap(str(path))
            if px.isNull():
                return None
            return px.scaled(
                tw, th,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        # 비디오: OpenCV 첫 프레임
        import cv2
        cap = cv2.VideoCapture(str(path))
        ret, frame = cap.read()
        cap.release()
        if not ret:
            return None
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h_src, w_src = frame_rgb.shape[:2]
        scale = min(tw / w_src, th / h_src)
        nw, nh = max(1, int(w_src * scale)), max(1, int(h_src * scale))
        thumb = cv2.resize(frame_rgb, (nw, nh), interpolation=cv2.INTER_AREA)
        img = QImage(
            thumb.data, thumb.shape[1], thumb.shape[0],
            thumb.strides[0], QImage.Format.Format_RGB888,
        )
        return QPixmap.fromImage(img)
    except Exception:
        return None


# ── 영상 격자 셀 ──────────────────────────────────────────────────────

class _VideoCell(QWidget):
    """
    카메라 한 대의 썸네일 카드.
    · 상단: 첫 프레임 썸네일 (어두운 배경 + 비율 유지) — 클릭 시 재생 요청
    · 하단: cam_id 레이블 + [×] 제거 버튼
    # Design Ref: §8.2 — _VideoCell
    """

    remove_requested = pyqtSignal(str)          # cam_id
    play_requested   = pyqtSignal(str, object)  # cam_id, Path

    _TW, _TH = 144, 90    # 썸네일 영역 크기
    _CW, _CH = 152, 124   # 카드 전체 크기

    def __init__(self, cam_id: str, path: Path, parent=None):
        super().__init__(parent)
        self._cam_id = cam_id
        self._path   = path
        self.setFixedSize(self._CW, self._CH)
        self._setup_ui(cam_id, path)

    def _setup_ui(self, cam_id: str, path: Path):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # 썸네일 레이블 (클릭 가능)
        self._thumb = QLabel()
        self._thumb.setFixedSize(self._TW, self._TH)
        self._thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb.setCursor(Qt.CursorShape.PointingHandCursor)
        self._thumb.setStyleSheet(
            "background-color: #1E2433;"
            "border: 1px solid #2D3748;"
            "border-radius: 3px;"
        )
        self._thumb.setToolTip(f"{cam_id} 재생")
        self._thumb.mousePressEvent = lambda _e: self.play_requested.emit(
            self._cam_id, self._path
        )

        pixmap = _load_thumbnail(path, self._TW, self._TH)
        if pixmap:
            # 재생 아이콘 오버레이를 위해 픽스맵 위에 반투명 ▶ 텍스트
            self._thumb.setPixmap(pixmap)
        else:
            self._thumb.setText("🎬")
            self._thumb.setStyleSheet(
                "background-color: #1E2433; border: 1px solid #2D3748;"
                "border-radius: 3px; color: #475569; font-size: 22px;"
            )
        layout.addWidget(self._thumb)

        # 하단 바: cam_id + 제거 버튼
        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(2)

        id_lbl = QLabel(cam_id)
        id_lbl.setStyleSheet(
            "font-size: 10px; font-weight: 600; color: #64748B;"
        )
        bottom.addWidget(id_lbl, 1)

        rm_btn = QPushButton("✕")
        rm_btn.setFixedSize(18, 18)
        rm_btn.setStyleSheet(
            "QPushButton {"
            "  border: none; background-color: transparent;"
            "  color: #94A3B8; font-size: 12px; font-weight: bold;"
            "  padding: 0; margin: 0;"
            "}"
            "QPushButton:hover { color: #EF4444; background-color: transparent; }"
        )
        rm_btn.setToolTip(f"{cam_id} 제거")
        rm_btn.clicked.connect(lambda: self.remove_requested.emit(self._cam_id))
        bottom.addWidget(rm_btn)

        layout.addLayout(bottom)


# ── 영상 격자 위젯 (Intrinsic 전용) ──────────────────────────────────

class _CamVideoGrid(QWidget):
    """
    폴더 선택 버튼 + 카메라별 첫 프레임을 격자로 표시.
    _CamTable과 동일한 공개 API: set_project_root(), get_cam_files()
    열 수는 카메라 수에 따라 자동 계산: n≤2→n열, n>2→ceil(n/2)열
    # Design Ref: §8.2 — _CamVideoGrid
    """

    play_requested = pyqtSignal(str, object)  # cam_id, Path (상위로 전파)

    @staticmethod
    def _calc_cols(n: int) -> int:
        """카메라 수 → 격자 열 수. 4개 이하 1행, 5개 이상 4열 고정."""
        if n <= 4:
            return max(1, n)
        return 4

    def __init__(self, label: str, extensions: frozenset[str],
                 hint_subdir: str = "", parent=None):
        super().__init__(parent)
        self._extensions = extensions
        self._hint_subdir = hint_subdir
        self._cam_files: dict[str, Path] = {}
        self._project_root: Path | None = None
        self._setup_ui(label)

    def _setup_ui(self, label: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # 폴더 선택 행
        top = QHBoxLayout()
        top.setSpacing(6)

        self._folder_lbl = QLabel("(미선택)")
        self._folder_lbl.setStyleSheet("color: #94A3B8; font-size: 11px;")
        self._folder_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        top.addWidget(self._folder_lbl)

        browse_btn = QPushButton(f"📂 {label} 선택")
        browse_btn.setFixedHeight(26)
        browse_btn.clicked.connect(self._browse)
        top.addWidget(browse_btn)

        layout.addLayout(top)

        # 격자 스크롤 영역 (높이는 _refresh_grid에서 동적 계산)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setMaximumHeight(400)
        self._scroll.setFixedHeight(0)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        self._grid_widget = QWidget()
        self._grid = QVBoxLayout(self._grid_widget)
        self._grid.setSpacing(8)
        self._grid.setContentsMargins(4, 4, 4, 4)
        self._grid.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        self._scroll.setWidget(self._grid_widget)
        layout.addWidget(self._scroll)

        # 빈 상태
        self._empty = EmptyState("cam* 영상 없음\n폴더를 선택하면 자동 탐색됩니다")
        self._empty.setFixedHeight(60)
        self._empty.hide()
        layout.addWidget(self._empty)

    # ── 공개 API (= _CamTable 동일 인터페이스) ──────────────────────

    def set_project_root(self, root: Path):
        self._project_root = root
        if self._hint_subdir:
            auto_dir = root / self._hint_subdir
            if auto_dir.is_dir():
                self._load_folder(auto_dir)

    def get_cam_files(self) -> dict[str, str]:
        return {k: str(v) for k, v in self._cam_files.items()}

    def clear(self):
        """탐색된 파일 목록 및 그리드를 초기화."""
        self._cam_files = {}
        self._folder_lbl.setText("폴더 없음")
        self._folder_lbl.setToolTip("")
        self._refresh_grid()

    # ── 내부 ─────────────────────────────────────────────────────────

    def _browse(self):
        start = (
            str(self._project_root / self._hint_subdir)
            if self._project_root and self._hint_subdir
            else str(Path.home())
        )
        folder = QFileDialog.getExistingDirectory(self, "폴더 선택", start)
        if not folder:
            return
        self._load_folder(Path(folder))

    def _load_folder(self, folder: Path):
        self._folder_lbl.setText(folder.name)
        self._folder_lbl.setToolTip(str(folder))
        groups = _discover_cameras(folder, self._extensions)
        self._cam_files = {k: v[0] for k, v in groups.items() if v}
        self._refresh_grid()

    def _refresh_grid(self):
        # 기존 행 위젯 모두 제거
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._cam_files:
            self._scroll.hide()
            self._empty.show()
            return

        self._empty.hide()
        self._scroll.show()

        # QVBoxLayout 안에 QHBoxLayout 행을 추가 (동적 열 수)
        items = list(self._cam_files.items())
        cols = self._calc_cols(len(items))
        n_rows = math.ceil(len(items) / cols)
        cell_h = _VideoCell._CH
        needed = n_rows * cell_h + (n_rows - 1) * 8 + 16   # spacing + padding
        self._scroll.setFixedHeight(min(needed, 400))
        for row_start in range(0, len(items), cols):
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)
            row_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
            for cam_id, path in items[row_start: row_start + cols]:
                cell = _VideoCell(cam_id, path)
                cell.remove_requested.connect(self._remove_cam)
                cell.play_requested.connect(self._on_play_requested)
                row_layout.addWidget(cell)
            row_layout.addStretch()
            self._grid.addWidget(row_widget)

    def _remove_cam(self, cam_id: str):
        self._cam_files.pop(cam_id, None)
        self._refresh_grid()

    def _on_play_requested(self, cam_id: str, path: object):
        self.play_requested.emit(cam_id, path)


# ── 카메라 테이블 위젯 ────────────────────────────────────────────────

class _CamTable(QWidget):
    """
    폴더 선택 버튼 + 자동 발견된 카메라 목록 테이블.
    각 행: cam_id | 파일명 | [제거] 버튼
    """

    def __init__(self, label: str, extensions: frozenset[str],
                 hint_subdir: str = "", parent=None):
        super().__init__(parent)
        self._extensions = extensions
        self._hint_subdir = hint_subdir   # e.g. "calibration/intrinsic"
        self._cam_files: dict[str, Path] = {}   # cam_id → 대표 파일
        self._project_root: Path | None = None
        self._setup_ui(label)

    def _setup_ui(self, label: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 폴더 선택 행
        top = QHBoxLayout()
        top.setSpacing(6)

        self._folder_lbl = QLabel("(미선택)")
        self._folder_lbl.setStyleSheet("color: #94A3B8; font-size: 11px;")
        self._folder_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        top.addWidget(self._folder_lbl)

        browse_btn = QPushButton(f"📂 {label} 선택")
        browse_btn.setFixedHeight(26)
        browse_btn.clicked.connect(self._browse)
        top.addWidget(browse_btn)

        layout.addLayout(top)

        # 카메라 테이블
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["카메라", "파일", ""])
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._table.verticalHeader().hide()
        self._table.setFixedHeight(120)
        layout.addWidget(self._table)

        # 빈 상태
        self._empty = EmptyState("cam* 파일 없음\n폴더를 선택하면 자동 탐색됩니다")
        self._empty.hide()
        layout.addWidget(self._empty)

    def set_project_root(self, root: Path):
        self._project_root = root
        if self._hint_subdir:
            auto_dir = root / self._hint_subdir
            if auto_dir.is_dir():
                self._load_folder(auto_dir)

    def _browse(self):
        # 기본 디렉터리: project_root/calibration/intrinsic (or extrinsic)
        start = str(self._project_root / self._hint_subdir) \
            if self._project_root and self._hint_subdir else str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "폴더 선택", start)
        if not folder:
            return
        self._load_folder(Path(folder))

    def _load_folder(self, folder: Path):
        self._folder_lbl.setText(folder.name)
        self._folder_lbl.setToolTip(str(folder))

        groups = _discover_cameras(folder, self._extensions)
        self._cam_files = {k: v[0] for k, v in groups.items() if v}
        self._refresh_table()

    def _refresh_table(self):
        self._table.setRowCount(0)
        if not self._cam_files:
            self._table.hide()
            self._empty.show()
            return
        self._empty.hide()
        self._table.show()
        for cam_id, path in self._cam_files.items():
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(cam_id))
            self._table.setItem(row, 1, QTableWidgetItem(path.name))
            item1 = self._table.item(row, 1)
            if item1:
                item1.setToolTip(str(path))

            del_btn = QPushButton("제거")
            del_btn.setFixedHeight(22)
            del_btn.clicked.connect(lambda _, c=cam_id: self._remove_cam(c))
            self._table.setCellWidget(row, 2, del_btn)

    def _remove_cam(self, cam_id: str):
        self._cam_files.pop(cam_id, None)
        self._refresh_table()

    def get_cam_files(self) -> dict[str, str]:
        """cam_id → 파일 절대경로(str) 딕셔너리 반환."""
        return {k: str(v) for k, v in self._cam_files.items()}


# ── Scene 포인트 피커 위젯 ──────────────────────────────────────────

class _ZoomableImageView(QGraphicsView):
    """
    카메라 프레임 표시 + 줌/팬/포인트 클릭 지원 뷰.
    - 좌클릭: 기준점 선택 (이미지 좌표 emit)
    - 마우스 휠: 커서 위치 기준 줌 인/아웃
    - 우클릭 드래그 또는 중간 버튼 드래그: 화면 이동(팬)
    - 더블클릭 또는 R키: 줌/팬 리셋
    - +/-키: 단계 줌
    # Design Ref: §8.2 — Scene 포인트 피커 줌/팬 지원
    """
    clicked = pyqtSignal(float, float)  # 이미지 좌표 (원본 크기 기준)

    _ZOOM_STEP = 1.18  # 휠 한 틱 / 키 한 번당 배율

    def __init__(self, parent=None):
        super().__init__(parent)
        self._gscene = QGraphicsScene(self)
        self.setScene(self._gscene)
        self._pixmap_item = None
        self._frame = None
        self._points: list = []
        self._points_3d: list = []
        self._fit_next = True   # 다음 _rebuild 때 fitInView 실행 여부

        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        # 줌 앵커: 커서 아래 좌표 기준
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("background: #0F172A; border: none; border-radius: 4px;")
        self.setMinimumSize(600, 400)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self._panning = False
        self._pan_start = None

    # ── 공개 API (ScenePointPickerDialog와 동일 인터페이스) ──────────

    def set_frame(self, frame, points: list, points_3d: list):
        """카메라가 바뀌면 줌 리셋, 같은 카메라 포인트 추가 시엔 줌 유지."""
        if frame is not self._frame:
            self._fit_next = True
        self._frame = frame
        self._points = list(points)
        self._points_3d = list(points_3d)
        self._rebuild()

    def reset_zoom(self):
        """이미지 전체가 보이도록 뷰 리셋."""
        if self._gscene.sceneRect().isValid():
            self.fitInView(self._gscene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    # ── 내부 렌더링 ──────────────────────────────────────────────────

    def _rebuild(self):
        self._gscene.clear()
        self._pixmap_item = None

        if self._frame is None:
            return

        h, w = self._frame.shape[:2]
        img = QImage(
            self._frame.data, w, h,
            self._frame.strides[0], QImage.Format.Format_RGB888,
        )
        self._pixmap_item = self._gscene.addPixmap(QPixmap.fromImage(img))
        self._gscene.setSceneRect(QRectF(0, 0, w, h))

        # 클릭 포인트 오버레이 (QGraphicsScene 아이템 — 원본 해상도 좌표)
        r = max(5.0, min(w / 300, 20.0))  # 고해상도 이미지에서도 작고 적당한 크기
        font = QFont("Arial", max(10, int(r)), QFont.Weight.Bold)
        for i, (px, py) in enumerate(self._points):
            pen = QPen(QColor(255, 255, 255))
            pen.setWidthF(r * 0.2)
            self._gscene.addEllipse(
                px - r, py - r, r * 2, r * 2,
                pen, QBrush(QColor(0, 220, 80)),
            )
            txt = self._gscene.addText(str(i + 1), font)
            txt.setDefaultTextColor(QColor(255, 240, 0))
            txt.setPos(px + r * 1.2, py - r * 1.8)

        if self._fit_next:
            self.fitInView(self._gscene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
            self._fit_next = False

    # ── 이벤트 핸들러 ──────────────────────────────────────────────

    def wheelEvent(self, event):
        """마우스 휠 → 커서 위치 기준 줌."""
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = self._ZOOM_STEP if delta > 0 else 1.0 / self._ZOOM_STEP
        self.scale(factor, factor)

    def mousePressEvent(self, event):
        btn = event.button()
        if btn == Qt.MouseButton.LeftButton:
            # 이미지 위 좌클릭 → 포인트 기록
            scene_pos = self.mapToScene(event.position().toPoint())
            if (self._pixmap_item is not None
                    and self._gscene.sceneRect().contains(scene_pos)):
                self.clicked.emit(float(scene_pos.x()), float(scene_pos.y()))
        elif btn in (Qt.MouseButton.RightButton, Qt.MouseButton.MiddleButton):
            # 우클릭/중간 버튼 드래그 → 팬
            self._panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning and self._pan_start is not None:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - int(delta.x())
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - int(delta.y())
            )
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() in (Qt.MouseButton.RightButton, Qt.MouseButton.MiddleButton):
            self._panning = False
            self.setCursor(Qt.CursorShape.CrossCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        """좌더블클릭 → 줌 리셋."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.reset_zoom()
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_R:
            self.reset_zoom()
        elif key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self.scale(self._ZOOM_STEP, self._ZOOM_STEP)
        elif key == Qt.Key.Key_Minus:
            self.scale(1.0 / self._ZOOM_STEP, 1.0 / self._ZOOM_STEP)
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._fit_next and self._gscene.sceneRect().isValid():
            self.fitInView(self._gscene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)


class ScenePointPickerDialog(QDialog):
    """
    Extrinsic Scene 캘리브레이션용 2D 포인트 클릭 다이얼로그.
    각 카메라 프레임에서 3D 기준점의 2D 이미지 좌표를 순서대로 클릭.
    # Design Ref: §8.2 — Scene 포인트 피커 다이얼로그
    """

    def __init__(self, cam_files: dict, points_3d: list, parent=None):
        super().__init__(parent)
        self._cam_files = cam_files           # {"cam01": "/path/..."}
        self._points_3d = points_3d           # [[x,y,z], ...]
        self._n_pts = len(points_3d)
        self._cam_names = list(cam_files.keys())
        self._cur_idx = 0
        self._clicked: dict[str, list] = {c: [] for c in self._cam_names}
        self._frames: dict[str, object] = {}

        self._load_frames()
        self._setup_ui()
        self._refresh()

    # ── 프레임 로드 ──────────────────────────────────────────────────

    def _load_frames(self):
        try:
            import cv2
        except ImportError:
            return
        for cam, fp_str in self._cam_files.items():
            if not fp_str:
                self._frames[cam] = None
                continue
            fp = Path(fp_str)
            ext = fp.suffix.lower()
            try:
                if ext in {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}:
                    img = cv2.imread(str(fp))
                    self._frames[cam] = cv2.cvtColor(img, cv2.COLOR_BGR2RGB) if img is not None else None
                else:
                    cap = cv2.VideoCapture(str(fp))
                    ret, frame = cap.read()
                    cap.release()
                    self._frames[cam] = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) if ret else None
            except Exception:
                self._frames[cam] = None

    # ── UI 구성 ───────────────────────────────────────────────────────

    def _setup_ui(self):
        self.setWindowTitle("Scene 기준점 선택 — 각 카메라에서 기준점을 순서대로 클릭하세요")
        self.setMinimumSize(1000, 680)
        self.setModal(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # 헤더
        self._header_lbl = QLabel()
        self._header_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._header_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #E2E8F0; padding: 4px;")
        root.addWidget(self._header_lbl)

        # 안내문
        self._instr_lbl = QLabel()
        self._instr_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._instr_lbl.setStyleSheet("font-size: 12px; color: #94A3B8; padding: 2px;")
        self._instr_lbl.setWordWrap(True)
        root.addWidget(self._instr_lbl)

        # 줌/팬 조작 힌트
        hint = QLabel(
            "휠: 줌  |  우클릭 드래그: 화면 이동  |  더블클릭 / R: 줌 리셋  |  좌클릭: 기준점 선택"
        )
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("font-size: 10px; color: #475569; padding: 1px;")
        root.addWidget(hint)

        # 이미지 + 포인트 목록 영역
        body = QHBoxLayout()
        body.setSpacing(8)

        self._img_lbl = _ZoomableImageView()
        self._img_lbl.clicked.connect(self._on_click)
        body.addWidget(self._img_lbl, 3)

        # 오른쪽: 포인트 목록
        right_panel = QWidget()
        right_panel.setFixedWidth(230)
        right_panel.setStyleSheet(
            "background: #1E293B; border-radius: 6px;"
        )
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.setSpacing(4)

        pts_title = QLabel("3D 기준점 목록")
        pts_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #CBD5E1;")
        right_layout.addWidget(pts_title)

        self._pts_list = QLabel()
        self._pts_list.setStyleSheet("font-size: 10px; color: #94A3B8; font-family: Menlo, Monaco;")
        self._pts_list.setWordWrap(True)
        self._pts_list.setAlignment(Qt.AlignmentFlag.AlignTop)
        right_layout.addWidget(self._pts_list, 1)

        body.addWidget(right_panel)
        root.addLayout(body, 1)

        # 버튼 행
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self._undo_btn = QPushButton("↩ 마지막 취소")
        self._undo_btn.setFixedHeight(30)
        self._undo_btn.clicked.connect(self._undo)
        btn_row.addWidget(self._undo_btn)

        self._clear_btn = QPushButton("✕ 전체 초기화")
        self._clear_btn.setFixedHeight(30)
        self._clear_btn.clicked.connect(self._clear_cam)
        btn_row.addWidget(self._clear_btn)

        reset_zoom_btn = QPushButton("⊙ 줌 리셋 (R)")
        reset_zoom_btn.setFixedHeight(30)
        reset_zoom_btn.setToolTip("이미지 전체가 보이도록 줌을 리셋합니다 (단축키: R)")
        reset_zoom_btn.clicked.connect(self._img_lbl.reset_zoom)
        btn_row.addWidget(reset_zoom_btn)

        btn_row.addSpacing(12)
        self._prev_btn = QPushButton("◀ 이전 카메라")
        self._prev_btn.setFixedHeight(30)
        self._prev_btn.clicked.connect(self._prev_cam)
        btn_row.addWidget(self._prev_btn)

        self._next_btn = QPushButton("다음 카메라 ▶")
        self._next_btn.setFixedHeight(30)
        self._next_btn.clicked.connect(self._next_cam)
        btn_row.addWidget(self._next_btn)

        btn_row.addStretch()

        cancel_btn = QPushButton("취소")
        cancel_btn.setFixedHeight(30)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self._ok_btn = QPushButton("✓ 완료 — 캘리브레이션 실행")
        self._ok_btn.setObjectName("run_all_btn")
        self._ok_btn.setFixedHeight(30)
        self._ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(self._ok_btn)

        root.addLayout(btn_row)

    # ── 상태 갱신 ─────────────────────────────────────────────────────

    def _refresh(self):
        cam = self._cam_names[self._cur_idx]
        n_total = len(self._cam_names)
        n_clicked = len(self._clicked[cam])

        self._header_lbl.setText(
            f"카메라 {self._cur_idx + 1} / {n_total}:  {cam}"
        )

        if n_clicked < self._n_pts:
            p3d = self._points_3d[n_clicked]
            self._instr_lbl.setText(
                f"기준점 {n_clicked + 1} / {self._n_pts} 위치를 이미지에서 클릭하세요  "
                f"[3D: {p3d[0]:.2f}, {p3d[1]:.2f}, {p3d[2]:.2f}]"
            )
        else:
            self._instr_lbl.setText(
                f"이 카메라 완료. {'다음 카메라로 이동하거나 ' if self._cur_idx < n_total - 1 else ''}"
                "완료 버튼을 누르세요."
            )

        self._img_lbl.set_frame(
            self._frames.get(cam),
            self._clicked[cam],
            self._points_3d,
        )

        # 포인트 목록 텍스트
        lines = []
        for i, p3d in enumerate(self._points_3d):
            if i < n_clicked:
                p2d = self._clicked[cam][i]
                lines.append(f"✓ {i+1}. ({p2d[0]:.0f},{p2d[1]:.0f})\n   [{p3d[0]},{p3d[1]},{p3d[2]}]")
            elif i == n_clicked:
                lines.append(f"▶ {i+1}. ← 다음 클릭\n   [{p3d[0]},{p3d[1]},{p3d[2]}]")
            else:
                lines.append(f"○ {i+1}. 미선택\n   [{p3d[0]},{p3d[1]},{p3d[2]}]")
        self._pts_list.setText("\n".join(lines))

        # 버튼 활성화
        self._undo_btn.setEnabled(n_clicked > 0)
        self._clear_btn.setEnabled(n_clicked > 0)
        self._prev_btn.setEnabled(self._cur_idx > 0)
        self._next_btn.setEnabled(self._cur_idx < n_total - 1)

        all_done = all(len(self._clicked[c]) == self._n_pts for c in self._cam_names)
        self._ok_btn.setEnabled(all_done)

    # ── 이벤트 핸들러 ─────────────────────────────────────────────────

    def _on_click(self, ix: float, iy: float):
        cam = self._cam_names[self._cur_idx]
        if len(self._clicked[cam]) < self._n_pts:
            self._clicked[cam].append((ix, iy))
            # 마지막 포인트 찍으면 자동으로 다음 카메라로 이동
            if (len(self._clicked[cam]) == self._n_pts
                    and self._cur_idx < len(self._cam_names) - 1):
                self._cur_idx += 1
            self._refresh()

    def _undo(self):
        cam = self._cam_names[self._cur_idx]
        if self._clicked[cam]:
            self._clicked[cam].pop()
            self._refresh()

    def _clear_cam(self):
        cam = self._cam_names[self._cur_idx]
        self._clicked[cam].clear()
        self._refresh()

    def _prev_cam(self):
        if self._cur_idx > 0:
            self._cur_idx -= 1
            self._refresh()

    def _next_cam(self):
        if self._cur_idx < len(self._cam_names) - 1:
            self._cur_idx += 1
            self._refresh()

    def get_image_coords(self) -> dict:
        """{"cam01": [[x,y], ...], ...}"""
        return {
            cam: [list(pt) for pt in pts]
            for cam, pts in self._clicked.items()
        }


# ── 결과 팝업 다이얼로그 ──────────────────────────────────────────────

class CalibResultDialog(QDialog):
    """
    캘리브레이션 결과를 화면 중앙 팝업으로 표시.
    # Design Ref: §8.2 — 결과 팝업 (인라인 하단 표시 대신)
    """

    def __init__(self, title: str, text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(480)
        self.setMinimumHeight(220)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(12)

        result_edit = QPlainTextEdit(text)
        result_edit.setReadOnly(True)
        font = QFont("Menlo", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        result_edit.setFont(font)
        result_edit.setStyleSheet(
            "background-color: #1E293B; color: #E2E8F0; border: none; border-radius: 4px;"
        )
        layout.addWidget(result_edit)

        close_btn = QPushButton("닫기")
        close_btn.setFixedWidth(80)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)


# ── 인라인 단일 비디오 플레이어 ──────────────────────────────────────

class _InlineVideoPlayer(QWidget):
    """
    썸네일 클릭 시 나타나는 인라인 비디오 플레이어.
    QMediaPlayer + QVideoWidget + Play/Pause/Stop/Slider 컨트롤.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._player = QMediaPlayer(self)
        self._audio  = QAudioOutput(self)
        self._player.setAudioOutput(self._audio)
        self._audio.setVolume(0.8)
        self._setup_ui()
        self._player.positionChanged.connect(self._on_position)
        self._player.durationChanged.connect(self._on_duration)
        self._player.playbackStateChanged.connect(self._on_state)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 헤더: 파일명 + 닫기 버튼
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        self._title_lbl = QLabel()
        self._title_lbl.setStyleSheet("font-size: 11px; color: #64748B;")
        header.addWidget(self._title_lbl, 1)
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet(
            "QPushButton {"
            "  border: none; background-color: transparent;"
            "  color: #94A3B8; font-size: 13px; font-weight: bold;"
            "  padding: 0; margin: 0;"
            "}"
            "QPushButton:hover { color: #EF4444; background-color: transparent; }"
        )
        close_btn.clicked.connect(self._close_player)
        header.addWidget(close_btn)
        layout.addLayout(header)

        # 비디오 위젯
        self._video_widget = QVideoWidget()
        self._video_widget.setMinimumHeight(180)
        self._video_widget.setStyleSheet("background-color: #0F172A;")
        self._player.setVideoOutput(self._video_widget)
        layout.addWidget(self._video_widget, 1)

        # 컨트롤 바
        ctrl = QHBoxLayout()
        ctrl.setContentsMargins(0, 0, 0, 0)
        ctrl.setSpacing(4)

        self._play_btn = QPushButton("PLAY")
        self._play_btn.setFixedSize(62, 26)
        self._play_btn.clicked.connect(self._toggle_play)
        ctrl.addWidget(self._play_btn)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 1000)
        self._slider.setStyleSheet(_SLIDER_SS)
        self._slider.sliderMoved.connect(self._seek)
        ctrl.addWidget(self._slider, 1)

        self._time_lbl = QLabel("0:00 / 0:00")
        self._time_lbl.setStyleSheet("font-size: 10px; color: #64748B; min-width: 72px;")
        ctrl.addWidget(self._time_lbl)

        layout.addLayout(ctrl)

    def load(self, cam_id: str, path: Path):
        self._title_lbl.setText(f"{cam_id}  —  {path.name}")
        self._player.setSource(QUrl.fromLocalFile(str(path)))
        self._player.play()

    def _toggle_play(self):
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def _stop(self):
        self._player.stop()

    def _seek(self, pos: int):
        dur = self._player.duration()
        if dur > 0:
            self._player.setPosition(int(dur * pos / 1000))

    def _on_position(self, pos_ms: int):
        dur = self._player.duration()
        if dur > 0:
            self._slider.blockSignals(True)
            self._slider.setValue(int(pos_ms * 1000 / dur))
            self._slider.blockSignals(False)
        self._time_lbl.setText(f"{self._fmt(pos_ms)} / {self._fmt(dur)}")

    def _on_duration(self, dur: int):
        self._time_lbl.setText(f"0:00 / {self._fmt(dur)}")

    def _on_state(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._play_btn.setText("PAUSE")
        else:
            self._play_btn.setText("PLAY")

    @staticmethod
    def _fmt(ms: int) -> str:
        s = ms // 1000
        return f"{s // 60}:{s % 60:02d}"

    def _close_player(self):
        self._player.stop()
        self.hide()


# ── Intrinsic 미디어 위젯 (중앙 배치) ───────────────────────────────

class _IntrinsicMediaWidget(QScrollArea):
    """
    Intrinsic 탭 중앙 영역 — 카메라 영상 격자 + 인라인 비디오 플레이어.
    썸네일 클릭 시 해당 영상을 하단 플레이어에서 재생.
    # Design Ref: §8.2 — Intrinsic 미디어 (중앙)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._cam_grid = _CamVideoGrid(
            label="intrinsic 폴더",
            extensions=_VIDEO_EXTS,
            hint_subdir="calibration/intrinsics",
        )
        self._cam_grid.play_requested.connect(self._on_play_requested)

        self._player = _InlineVideoPlayer()
        self._player.hide()

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._cam_grid)
        layout.addWidget(self._player)
        self.setWidget(inner)

    def _on_play_requested(self, cam_id: str, path: object):
        self._player.show()
        self._player.load(cam_id, path)
        self.ensureWidgetVisible(self._player)

    def set_project_root(self, root: Path):
        self._cam_grid.set_project_root(root)

    def get_cam_files(self) -> dict[str, str]:
        return self._cam_grid.get_cam_files()

    def clear_media(self):
        self._cam_grid.clear()
        self._player.hide()


# ── Extrinsic 미디어 위젯 (중앙 배치) ───────────────────────────────

class _ExtrinsicMediaWidget(QScrollArea):
    """
    Extrinsic 탭 중앙 영역 — 선택된 Method에 맞는 미디어 격자 표시.
    # Design Ref: §8.2 — Extrinsic 미디어 (중앙)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._current_method = 0

        self._checker_grid = _CamVideoGrid(
            label="extrinsic 폴더",
            extensions=_MEDIA_EXTS,
            hint_subdir="calibration/extrinsics",
        )
        self._scene_grid = _CamVideoGrid(
            label="extrinsic 폴더",
            extensions=_MEDIA_EXTS,
            hint_subdir="calibration/extrinsics",
        )
        self._kp_info = QLabel(
            "Keypoints 모드\n포즈 추정 결과를 자동으로 사용합니다.\n별도 미디어 입력이 필요 없습니다."
        )
        self._kp_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._kp_info.setStyleSheet("color: #64748B; font-size: 13px;")
        self._kp_info.hide()
        self._scene_grid.hide()

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._checker_grid)
        layout.addWidget(self._scene_grid)
        layout.addWidget(self._kp_info)
        self.setWidget(inner)

    def set_project_root(self, root: Path):
        self._checker_grid.set_project_root(root)
        self._scene_grid.set_project_root(root)

    def set_method(self, method_id: int):
        self._current_method = method_id
        self._checker_grid.setVisible(method_id == 0)
        self._scene_grid.setVisible(method_id == 1)
        self._kp_info.setVisible(method_id == 2)

    def get_cam_files(self) -> dict[str, str]:
        if self._current_method == 0:
            return self._checker_grid.get_cam_files()
        if self._current_method == 1:
            return self._scene_grid.get_cam_files()
        return {}

    def clear_media(self):
        self._checker_grid.clear()
        self._scene_grid.clear()


# ── 캘리브레이션 설정 패널 (우측 배치) ──────────────────────────────

class CalibSettingsPanel(QWidget):
    """
    Calibration 파라미터 설정 패널 — 우측 패널에 배치.
    Intrinsic/Extrinsic 탭이 CalibPanel 탭과 동기화됨.
    Run 결과는 CalibResultDialog 팝업으로 표시.
    # Design Ref: §8.2 — CalibSettingsPanel (우측)
    """

    run_requested = pyqtSignal(str, dict)   # ("intrinsic"|"extrinsic", params)
    method_changed = pyqtSignal(int)         # Extrinsic method 변경 시

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cam_files_getters: dict[str, object] = {}
        self._setup_ui()

    def register_cam_files_getter(self, step: str, fn):
        """CalibPanel이 cam_files getter 함수를 등록."""
        self._cam_files_getters[step] = fn

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 헤더
        header = QWidget()
        header.setFixedHeight(36)
        header.setStyleSheet(
            "background-color: #F8FAFC; border-bottom: 1px solid #E2E8F0;"
        )
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(12, 0, 12, 0)
        title = QLabel("Calibration 설정")
        title.setStyleSheet("font-weight: 600; font-size: 12px; color: #1E293B;")
        h_layout.addWidget(title)
        layout.addWidget(header)

        # 스크롤 영역
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        inner_layout.setSpacing(0)

        # 탭 (CalibPanel 탭과 동기화)
        self._tab_widget = QTabWidget()
        self._tab_widget.setStyleSheet("QTabWidget::pane { border: none; }")

        self._intr_settings = self._build_intrinsic_settings()
        self._extr_settings = self._build_extrinsic_settings()
        self._tab_widget.addTab(self._intr_settings, "Intrinsic")
        self._tab_widget.addTab(self._extr_settings, "Extrinsic")

        inner_layout.addWidget(self._tab_widget)
        scroll.setWidget(inner)
        layout.addWidget(scroll)

    def _build_intrinsic_settings(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(6)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        self._intr_board_type = QComboBox()
        self._intr_board_type.addItems(["Checkerboard", "CharucoBoard", "CirclesGrid"])
        self._intr_board_type.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents
        )
        self._intr_board_type.setMinimumContentsLength(14)
        form.addRow("Board Type:", self._intr_board_type)

        self._intr_cols = QSpinBox()
        self._intr_cols.setRange(2, 30)
        self._intr_cols.setValue(4)
        form.addRow("Columns:", self._intr_cols)

        self._intr_rows = QSpinBox()
        self._intr_rows.setRange(2, 30)
        self._intr_rows.setValue(5)
        form.addRow("Rows:", self._intr_rows)

        self._intr_square_size = QDoubleSpinBox()
        self._intr_square_size.setRange(0.1, 1000.0)
        self._intr_square_size.setValue(35.0)
        self._intr_square_size.setSuffix(" mm")
        self._intr_square_size.setDecimals(1)
        form.addRow("Square Size:", self._intr_square_size)

        layout.addLayout(form)

        run_btn = QPushButton("▶ Run Intrinsic")
        run_btn.setObjectName("run_all_btn")
        run_btn.setFixedHeight(32)
        run_btn.clicked.connect(self._run_intrinsic)
        layout.addWidget(run_btn)
        return widget

    def _build_extrinsic_settings(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Method 선택
        method_group = QGroupBox("Method")
        # 남는 세로 공간이 Method 그룹에 배분되며 아래 위젯이 밀리는 현상 방지
        method_group.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        method_layout = QHBoxLayout(method_group)
        method_layout.setSpacing(4)
        self._method_grp = QButtonGroup(self)
        for i, name in enumerate(["Checkerboard", "Scene", "Keypoints"]):
            rb = QRadioButton(name)
            self._method_grp.addButton(rb, i)
            method_layout.addWidget(rb)
        self._method_grp.button(0).setChecked(True)
        layout.addWidget(method_group)

        # 파라미터 영역: QStackedWidget으로 Checkerboard/Scene/Keypoints 중 1개만 참여
        self._params_stack = QStackedWidget()
        self._params_stack.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )

        # idx 0: Checkerboard 파라미터 위젯
        self._chk_widget = QWidget()
        chk_form = QFormLayout(self._chk_widget)
        chk_form.setContentsMargins(0, 0, 0, 0)
        chk_form.setSpacing(6)
        chk_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        chk_form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        self._chk_board_type = QComboBox()
        self._chk_board_type.addItems(["Checkerboard", "CharucoBoard", "CirclesGrid"])
        self._chk_board_type.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents
        )
        self._chk_board_type.setMinimumContentsLength(14)
        chk_form.addRow("Board Type:", self._chk_board_type)

        self._chk_cols = QSpinBox()
        self._chk_cols.setRange(2, 30)
        self._chk_cols.setValue(4)
        chk_form.addRow("Columns:", self._chk_cols)

        self._chk_rows = QSpinBox()
        self._chk_rows.setRange(2, 30)
        self._chk_rows.setValue(5)
        chk_form.addRow("Rows:", self._chk_rows)

        self._chk_square_size = QDoubleSpinBox()
        self._chk_square_size.setRange(0.1, 1000.0)
        self._chk_square_size.setValue(35.0)
        self._chk_square_size.setSuffix(" mm")
        self._chk_square_size.setDecimals(1)
        chk_form.addRow("Square Size:", self._chk_square_size)

        # idx 1: Scene 파라미터 위젯
        self._scene_widget = QWidget()
        scene_layout = QVBoxLayout(self._scene_widget)
        scene_layout.setContentsMargins(0, 0, 0, 0)
        scene_layout.setSpacing(4)
        scene_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        coords_hint = QLabel("3D 기준점 좌표 (각 줄: X Y Z)")
        coords_hint.setStyleSheet("color: #64748B; font-size: 11px;")
        scene_layout.addWidget(coords_hint)
        self._scene_coords = QPlainTextEdit()
        self._scene_coords.setPlaceholderText("0 0 0\n1 0 0\n0 1 0\n...")
        self._scene_coords.setFixedHeight(130)
        scene_layout.addWidget(self._scene_coords)

        # idx 2: Keypoints 안내 위젯
        self._kp_widget = QWidget()
        kp_layout = QVBoxLayout(self._kp_widget)
        kp_layout.setContentsMargins(0, 0, 0, 0)
        kp_label = QLabel("포즈 추정 결과를 자동으로 사용합니다.\n별도 입력이 필요 없습니다.")
        kp_label.setStyleSheet("color: #64748B; font-size: 11px;")
        kp_label.setWordWrap(True)
        kp_layout.addWidget(kp_label)

        self._params_stack.addWidget(self._chk_widget)   # index 0
        self._params_stack.addWidget(self._scene_widget)  # index 1
        self._params_stack.addWidget(self._kp_widget)     # index 2
        self._params_stack.setCurrentIndex(0)

        layout.addWidget(self._params_stack)

        self._method_grp.idClicked.connect(self._on_method_changed)

        run_btn = QPushButton("▶ Run Extrinsic")
        run_btn.setObjectName("run_all_btn")
        run_btn.setFixedHeight(32)
        run_btn.clicked.connect(self._run_extrinsic)
        layout.addWidget(run_btn)
        return widget

    def _on_method_changed(self, method_id: int):
        self._params_stack.setCurrentIndex(method_id)
        self.method_changed.emit(method_id)

    def _run_intrinsic(self):
        cam_files = (
            self._cam_files_getters["intrinsic"]()
            if "intrinsic" in self._cam_files_getters else {}
        )
        params = {
            "board_type":     self._intr_board_type.currentText(),
            "cols":           self._intr_cols.value(),
            "rows":           self._intr_rows.value(),
            "square_size_mm": self._intr_square_size.value(),
            "cam_files":      cam_files,
        }
        self.run_requested.emit("intrinsic", params)

    def _run_extrinsic(self):
        cam_files = (
            self._cam_files_getters["extrinsic"]()
            if "extrinsic" in self._cam_files_getters else {}
        )
        method_id = self._method_grp.checkedId()
        methods = ["checkerboard", "scene", "keypoints"]
        params: dict = {"method": methods[method_id]}
        if method_id == 0:
            params.update({
                "board_type":     self._chk_board_type.currentText(),
                "cols":           self._chk_cols.value(),
                "rows":           self._chk_rows.value(),
                "square_size_mm": self._chk_square_size.value(),
                "cam_files":      cam_files,
            })
        elif method_id == 1:
            params["cam_files"]    = cam_files
            params["scene_coords"] = self._scene_coords.toPlainText()

            # 3D 기준점 파싱
            points_3d: list = []
            for line in params["scene_coords"].strip().splitlines():
                parts = line.strip().split()
                if len(parts) == 3:
                    try:
                        points_3d.append([float(p) for p in parts])
                    except ValueError:
                        pass

            if not points_3d:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self, "입력 오류",
                    "3D 기준점 좌표를 입력하세요.\n형식: 각 줄에 X Y Z (예: 0 0 0)"
                )
                return
            if not cam_files:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "입력 오류", "Extrinsic 미디어 파일을 먼저 선택하세요.")
                return

            # Qt 포인트 피커 다이얼로그 → macOS 메인 스레드에서 실행
            dlg = ScenePointPickerDialog(cam_files, points_3d, self.window())
            if dlg.exec() != ScenePointPickerDialog.DialogCode.Accepted:
                return
            params["image_coords_2d"] = dlg.get_image_coords()

        self.run_requested.emit("extrinsic", params)

    def show_result(self, step: str, text: str):
        """결과를 화면 중앙 팝업으로 표시."""
        titles = {
            "intrinsic": "Intrinsic 캘리브레이션 결과",
            "extrinsic": "Extrinsic 캘리브레이션 결과",
        }
        dlg = CalibResultDialog(
            titles.get(step, "결과"), text, self.window()
        )
        dlg.exec()

    def set_active_tab(self, idx: int):
        """CalibPanel 탭 전환과 동기화."""
        self._tab_widget.setCurrentIndex(idx)

    def get_extrinsic_params_partial(self) -> dict:
        """cam_files 제외한 설정값 반환 (저장용)."""
        method_id = self._method_grp.checkedId()
        methods = ["checkerboard", "scene", "keypoints"]
        params: dict = {"method": methods[method_id]}
        if method_id == 0:
            params.update({
                "board_type":     self._chk_board_type.currentText(),
                "cols":           self._chk_cols.value(),
                "rows":           self._chk_rows.value(),
                "square_size_mm": self._chk_square_size.value(),
            })
        elif method_id == 1:
            params["scene_coords"] = self._scene_coords.toPlainText()
        return params

    def get_intrinsic_params_partial(self) -> dict:
        """cam_files 제외한 설정값 반환 (저장용)."""
        return {
            "board_type":     self._intr_board_type.currentText(),
            "cols":           self._intr_cols.value(),
            "rows":           self._intr_rows.value(),
            "square_size_mm": self._intr_square_size.value(),
        }


# ── CalibPanel ────────────────────────────────────────────────────────

class CalibPanel(QWidget):
    """
    중앙 Calibration 패널 — 미디어 그리드 표시.
    설정 파라미터는 CalibSettingsPanel(우측)에서 관리.

    Signals:
        calib_saved(Path): 저장 완료 시 발행.
        run_requested(str, dict): ("intrinsic"|"extrinsic", params) 실행 요청.
        tab_changed(int): 탭 전환 시 CalibSettingsPanel과 동기화.
    # Design Ref: §8.2 — CalibPanel (중앙 미디어) + CalibSettingsPanel (우측 설정)
    """

    calib_saved   = pyqtSignal(object)      # Path
    run_requested = pyqtSignal(str, dict)   # step, params
    tab_changed   = pyqtSignal(int)         # tab index

    def __init__(self, parent=None):
        super().__init__(parent)
        self._project_root: Path | None = None
        self._current_file: Path | None = None
        self._config_manager = ConfigManager()

        # 설정 패널 (우측에 배치될 위젯 — CalibPanel이 소유하지만 레이아웃에 추가 안 함)
        self._settings_panel = CalibSettingsPanel()

        self._setup_ui()

        # 설정 패널 ↔ 미디어 위젯 연결
        self._settings_panel.register_cam_files_getter(
            "intrinsic", self._intr_media.get_cam_files
        )
        self._settings_panel.register_cam_files_getter(
            "extrinsic", self._extr_media.get_cam_files
        )
        self._settings_panel.run_requested.connect(self.run_requested)
        self._settings_panel.method_changed.connect(self._extr_media.set_method)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── 헤더 ─────────────────────────────────────────────────────
        header_widget = QWidget()
        header_widget.setObjectName("calib_panel_header")
        header_widget.setFixedHeight(36)
        header_widget.setStyleSheet(
            "#calib_panel_header { background-color: #E2E8F0; }"
        )
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(16, 0, 16, 0)
        self._file_label = QLabel("New Calibration")
        self._file_label.setStyleSheet(
            "font-weight: 700; font-size: 14px; color: #0F172A; background-color: transparent;"
        )
        header_layout.addWidget(self._file_label)
        header_layout.addStretch()
        layout.addWidget(header_widget)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFixedHeight(1)
        divider.setStyleSheet("background-color: #E2E8F0; border: none;")
        layout.addWidget(divider)

        # ── 미디어 탭 (Intrinsic / Extrinsic) ────────────────────────
        self._tabs = QTabWidget()

        self._intr_media = _IntrinsicMediaWidget()
        self._extr_media = _ExtrinsicMediaWidget()

        self._tabs.addTab(self._intr_media, "Intrinsic")
        self._tabs.addTab(self._extr_media, "Extrinsic")
        self._tabs.currentChanged.connect(self._on_tab_changed)

        layout.addWidget(self._tabs, 1)


    def _on_tab_changed(self, idx: int):
        self._settings_panel.set_active_tab(idx)
        self.tab_changed.emit(idx)

    # ── 공개 API ─────────────────────────────────────────────────────

    def get_settings_panel(self) -> CalibSettingsPanel:
        """우측 패널에 배치할 설정 위젯 반환."""
        return self._settings_panel

    def set_project(self, project_root: Path):
        """프로젝트 루트만 저장. 미디어 자동 탐색은 +New 클릭 시에만."""
        self._project_root = project_root

    def clear_media(self):
        """캘리브레이션 페이지를 벗어날 때 미디어 그리드를 초기화."""
        self._intr_media.clear_media()
        self._extr_media.clear_media()

    def load_calib(self, path: Path | None):
        """path=None → 새 캘리브 모드 (+New). path → 기존 파일 이름 표시."""
        self._current_file = path
        if path is None:
            self._file_label.setText("New Calibration")
            # +New 버튼 클릭 시에만 미디어 폴더 자동 탐색
            if self._project_root is not None:
                self._intr_media.set_project_root(self._project_root)
                self._extr_media.set_project_root(self._project_root)
        else:
            self._file_label.setText(path.name)

    def show_intrinsic_result(self, text: str):
        """Intrinsic 결과를 팝업으로 표시."""
        self._settings_panel.show_result("intrinsic", text)

    def show_extrinsic_result(self, text: str):
        """Extrinsic 결과를 팝업으로 표시."""
        self._settings_panel.show_result("extrinsic", text)

    # ── 저장 핸들러 ───────────────────────────────────────────────────

