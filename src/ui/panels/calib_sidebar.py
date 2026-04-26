"""
Calibration 사이드바 섹션 — 사이드바 내 Calibration 파일 목록 + 새 캘리브 버튼
# Design Ref: §8.1 — CalibSidebar: 파일 목록, [+ New], calib_selected/new_calib_requested 시그널
"""
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem,
    QSizePolicy,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon

from src.ui.widgets.empty_state import EmptyState


class CalibSidebar(QWidget):
    """
    왼쪽 사이드바의 Calibration 영역.

    Signals:
        calib_selected(Path): 기존 .toml 파일 클릭 시 발행.
        new_calib_requested(): [+ New] 버튼 클릭 시 발행.
    """

    calib_selected      = pyqtSignal(object)   # Path
    new_calib_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._project_root: Path | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        # ── 헤더: "Calibration" + [+ New] ────────────────────────────
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Calibration")
        title.setObjectName("calib_section_title")
        title.setStyleSheet("font-size: 11px; font-weight: 600; color: #94A3B8; letter-spacing: 0.5px;")
        header.addWidget(title)

        header.addStretch()

        new_btn = QPushButton("+ New")
        new_btn.setObjectName("calib_new_btn")
        new_btn.setFixedHeight(22)
        new_btn.setStyleSheet(
            "QPushButton { font-size: 11px; padding: 0 8px; }"
        )
        new_btn.setToolTip("새 Calibration 생성")
        new_btn.clicked.connect(self.new_calib_requested)
        header.addWidget(new_btn)

        layout.addLayout(header)

        # ── 파일 목록 ─────────────────────────────────────────────────
        self._list = QListWidget()
        self._list.setObjectName("calib_list")
        self._list.setSpacing(1)
        self._list.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._list)

        # ── 빈 상태 ──────────────────────────────────────────────────
        self._empty = EmptyState("캘리브레이션 파일 없음\n[+ New]로 생성하세요")
        self._empty.hide()
        layout.addWidget(self._empty)

    # ── 공개 API ─────────────────────────────────────────────────────

    def set_project(self, project_root: Path):
        """프로젝트 루트 경로 설정 후 목록 갱신."""
        self._project_root = project_root
        self.refresh_list()

    def refresh_list(self, _saved_path: Path | None = None):
        """
        프로젝트 루트에서 Calib*.toml 파일을 재탐색해 목록 갱신.
        CalibPanel.calib_saved(Path) Signal에 바로 연결 가능.
        """
        self._list.clear()

        if self._project_root is None:
            self._show_empty(True)
            return

        calib_dir = self._project_root / "calibration"
        toml_files = sorted(calib_dir.glob("Calib*.toml")) if calib_dir.exists() else []
        if not toml_files:
            self._show_empty(True)
            return

        self._show_empty(False)
        for f in toml_files:
            item = QListWidgetItem(f"📄 {f.name}")
            item.setData(Qt.UserRole, f)
            item.setToolTip(str(f))
            self._list.addItem(item)

    # ── 내부 핸들러 ──────────────────────────────────────────────────

    def _on_item_clicked(self, item: QListWidgetItem):
        path: Path = item.data(Qt.UserRole)
        if path and path.exists():
            self.calib_selected.emit(path)

    def _show_empty(self, show: bool):
        self._list.setVisible(not show)
        self._empty.setVisible(show)
