"""
프로젝트 관리 패널 — 사이드바 최상단
새 프로젝트 생성, 기존 프로젝트 열기, 최근 프로젝트 목록 표시.
# Design Ref: §2.1 — Project Panel (사이드바 상단)
# Plan SC: SC-01, SC-07
"""
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QMenu, QFileDialog,
    QSizePolicy, QAction,
)
from PyQt5.QtCore import Qt, pyqtSignal, QSettings

from src.core.project import Project
from src.core.config_manager import ConfigManager
from src.utils.constants import APP_NAME
from src.ui.dialogs.new_project_dialog import NewProjectDialog


MAX_RECENT = 10  # 최근 프로젝트 최대 보관 수


class ProjectPanel(QWidget):
    """
    왼쪽 사이드바 최상단에 위치하는 프로젝트 관리 위젯.

    Signals:
        project_opened(Project): 프로젝트가 열렸을 때 발행.
    """

    project_opened = pyqtSignal(object)   # Project 객체

    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings = QSettings(APP_NAME, APP_NAME)
        self._config_manager = ConfigManager()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 4)
        layout.setSpacing(4)

        # ── 헤더: 프로젝트명 + 메뉴 버튼 ─────────────────────────────
        header = QHBoxLayout()
        self._project_label = QLabel("프로젝트 없음")
        self._project_label.setObjectName("project_label")
        self._project_label.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Preferred
        )
        header.addWidget(self._project_label)

        menu_btn = QPushButton("⋮")
        menu_btn.setFixedSize(24, 24)
        menu_btn.setStyleSheet("border: none; font-size: 16px;")
        menu_btn.setToolTip("프로젝트 메뉴")
        menu_btn.clicked.connect(self._show_menu)
        header.addWidget(menu_btn)
        layout.addLayout(header)

        # ── 버튼 영역 ─────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        _btn_ss = "QPushButton { text-align: center; padding: 4px 8px; }"
        new_btn = QPushButton("+ 새 프로젝트")
        new_btn.setStyleSheet(_btn_ss)
        new_btn.clicked.connect(self._on_new_project)
        open_btn = QPushButton("열기")
        open_btn.setStyleSheet(_btn_ss)
        open_btn.clicked.connect(self._on_open_project)
        btn_row.addWidget(new_btn)
        btn_row.addWidget(open_btn)
        layout.addLayout(btn_row)

    def _show_menu(self):
        menu = QMenu(self)

        # 최근 프로젝트 서브메뉴
        recent_menu = menu.addMenu("최근 프로젝트")
        recent = self._load_recent()
        if recent:
            for path_str in recent:
                path = Path(path_str)
                action = QAction(path.name, self)
                action.setToolTip(path_str)
                action.triggered.connect(lambda checked, p=path: self._open_project(p))
                recent_menu.addAction(action)
            recent_menu.addSeparator()
            clear_action = QAction("목록 지우기", self)
            clear_action.triggered.connect(self._clear_recent)
            recent_menu.addAction(clear_action)
        else:
            no_recent = QAction("최근 프로젝트 없음", self)
            no_recent.setEnabled(False)
            recent_menu.addAction(no_recent)

        menu.exec(self.mapToGlobal(self.rect().topRight()))

    def _on_new_project(self):
        dlg = NewProjectDialog(self)
        if dlg.exec_() == NewProjectDialog.Accepted:
            project_path = dlg.create_project_structure()
            if project_path:
                # Config.toml 자동 생성
                self._config_manager.create_project_config(project_path)
                self._open_project(project_path)

    def _on_open_project(self):
        folder = QFileDialog.getExistingDirectory(
            self, "프로젝트 폴더 선택", str(Path.home())
        )
        if folder:
            self._open_project(Path(folder))

    def _open_project(self, path: Path):
        if not path.exists():
            return
        project = Project(name=path.name, root_path=path)
        self._project_label.setText(project.name)
        self._add_recent(str(path))
        self.project_opened.emit(project)

    # ── 최근 프로젝트 QSettings 관리 ──────────────────────────────────

    def _load_recent(self) -> list[str]:
        raw = self._settings.value("recent_projects", [])
        return raw if isinstance(raw, list) else []

    def _add_recent(self, path_str: str):
        recent = self._load_recent()
        if path_str in recent:
            recent.remove(path_str)
        recent.insert(0, path_str)
        self._settings.setValue("recent_projects", recent[:MAX_RECENT])

    def _clear_recent(self):
        self._settings.remove("recent_projects")
