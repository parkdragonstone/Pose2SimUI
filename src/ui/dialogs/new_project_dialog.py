"""
새 프로젝트 생성 다이얼로그
# Design Ref: §2.1 — 새 프로젝트 생성: 이름 + 저장 위치 선택
# Plan SC: SC-01 — 새 프로젝트 생성 및 Pose2Sim 표준 폴더 구조 자동 생성
"""
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QVBoxLayout, QMessageBox,
)
from PyQt6.QtCore import Qt

from src.utils.constants import POSE2SIM_DIR_STRUCTURE
from src.utils.file_utils import ensure_dir


class NewProjectDialog(QDialog):
    """
    프로젝트 이름과 저장 폴더를 입력받아 Pose2Sim 표준 구조를 생성하는 다이얼로그.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("새 프로젝트 생성")
        self.setMinimumWidth(450)
        self._project_path: Path | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(8)

        # 프로젝트 이름
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("예: MyMoCap_Session1")
        form.addRow("프로젝트 이름:", self._name_edit)

        # 저장 위치
        location_layout = QHBoxLayout()
        self._location_edit = QLineEdit()
        self._location_edit.setPlaceholderText("폴더를 선택하세요")
        self._location_edit.setReadOnly(True)
        browse_btn = QPushButton("찾아보기...")
        browse_btn.setFixedWidth(90)
        browse_btn.clicked.connect(self._browse_location)
        location_layout.addWidget(self._location_edit)
        location_layout.addWidget(browse_btn)
        form.addRow("저장 위치:", location_layout)

        layout.addLayout(form)

        # 미리보기 레이블
        self._preview_label = QLabel("")
        self._preview_label.setStyleSheet("color: gray; font-size: 11px;")
        self._preview_label.setWordWrap(True)
        layout.addWidget(self._preview_label)

        # 버튼
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # 이름 변경 시 미리보기 갱신
        self._name_edit.textChanged.connect(self._update_preview)
        self._location_edit.textChanged.connect(self._update_preview)

    def _browse_location(self):
        folder = QFileDialog.getExistingDirectory(
            self, "저장 위치 선택", str(Path.home())
        )
        if folder:
            self._location_edit.setText(folder)

    def _update_preview(self):
        name = self._name_edit.text().strip()
        location = self._location_edit.text().strip()
        if name and location:
            path = Path(location) / name
            self._preview_label.setText(
                f"생성 경로: {path}\n"
                f"  calibration/intrinsics/\n"
                f"  calibration/extrinsics/\n"
                f"  Trial_01/videos/"
            )
        else:
            self._preview_label.setText("")

    def _on_accept(self):
        name = self._name_edit.text().strip()
        location = self._location_edit.text().strip()

        if not name:
            QMessageBox.warning(self, "입력 오류", "프로젝트 이름을 입력하세요.")
            return
        if not location:
            QMessageBox.warning(self, "입력 오류", "저장 위치를 선택하세요.")
            return

        project_path = Path(location) / name
        if project_path.exists() and any(project_path.iterdir()):
            result = QMessageBox.question(
                self, "폴더 이미 존재",
                f"'{project_path}' 폴더가 이미 존재합니다.\n계속하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if result != QMessageBox.StandardButton.Yes:
                return

        self._project_path = project_path
        self.accept()

    def create_project_structure(self) -> Path | None:
        """
        승인 후 Pose2Sim 표준 폴더 구조를 실제로 생성하고 경로를 반환.
        # Plan SC: SC-01
        """
        if self._project_path is None:
            return None
        ensure_dir(self._project_path)
        for subdir in POSE2SIM_DIR_STRUCTURE:
            ensure_dir(self._project_path / subdir)
        return self._project_path

    @property
    def project_name(self) -> str:
        return self._name_edit.text().strip()

    @property
    def project_path(self) -> Path | None:
        return self._project_path
