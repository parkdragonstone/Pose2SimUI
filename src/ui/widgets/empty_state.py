"""
빈 상태 안내 위젯 — 목록이 비었을 때 표시
# Design Ref: §1.1 — empty_state.py
"""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt


class EmptyState(QWidget):
    """'결과 없음' 또는 안내 텍스트를 중앙에 표시하는 소형 위젯."""

    def __init__(self, message: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(8, 8, 8, 8)

        lbl = QLabel(message)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color: #94A3B8; font-size: 11px;")
        layout.addWidget(lbl)
