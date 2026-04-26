"""
실행 로그 스트리밍 패널 (하단 고정)
# Design Ref: §2.1 — Log Panel: 항상 펼쳐진 상태, 접기 없음
# Plan NFR-05 — 최대 10,000 라인 유지 (메모리 관리)
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QPlainTextEdit,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QTextCursor, QFont


MAX_LOG_LINES = 10_000


class LogPanel(QWidget):
    """
    파이프라인 실행 로그를 스트리밍 표시하는 하단 패널.
    항상 펼쳐진 상태. 최대 라인 수 초과 시 앞부분 자동 삭제.
    # Design Ref: §2.1 — Log Panel (collapse 없음)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── 헤더 (제목 + 지우기 버튼) ────────────────────────────────
        header = QWidget()
        header.setFixedHeight(28)
        header.setStyleSheet("background-color: #f1f3f4; border-top: 1px solid #dadce0;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 0, 8, 0)
        header_layout.setSpacing(6)

        title_lbl = QLabel("Log")
        title_lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #444;")
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()

        clear_btn = QPushButton("지우기")
        clear_btn.setFlat(True)
        clear_btn.setFixedHeight(20)
        clear_btn.setStyleSheet("font-size: 10px; color: #666;")
        header_layout.addWidget(clear_btn)

        layout.addWidget(header)

        # ── 로그 텍스트 영역 ──────────────────────────────────────────
        self._log_edit = QPlainTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setMaximumBlockCount(MAX_LOG_LINES)
        font = QFont("Menlo", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self._log_edit.setFont(font)
        self._log_edit.setStyleSheet(
            "background-color: #1e1e1e; color: #d4d4d4; border: none;"
        )
        layout.addWidget(self._log_edit)

        clear_btn.clicked.connect(self._log_edit.clear)

    def append_log(self, line: str):
        """
        로그 한 줄 추가. 자동으로 최하단으로 스크롤.
        # Plan NFR-05 — setMaximumBlockCount으로 메모리 관리
        """
        self._log_edit.appendPlainText(line)
        cursor = self._log_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._log_edit.setTextCursor(cursor)
