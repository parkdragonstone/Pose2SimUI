"""
결과 뷰어 컨테이너 — 영상/3D/Kinematics 플랫 수직 스택 (collapse 없음)
# Design Ref: §2.1 — ResultViewerWidget: 플랫 레이아웃, Trial 선택 시 중앙 패널에 표시
"""
from PyQt5.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout,
    QLabel, QSizePolicy, QFrame,
)
from PyQt5.QtCore import Qt  # noqa: F401 — Qt flags used in _section_header

from src.core.project import Trial
from src.ui.viewers.video_player import VideoPlayerWidget
from src.ui.viewers.viewer_3d import Viewer3DWidget
from src.ui.viewers.kinematics_viewer import KinematicsViewerWidget
from src.ui.widgets.empty_state import EmptyState


# ── 좌우 패딩 래퍼 ──────────────────────────────────────────────────

def _padded(widget: QWidget, h: int = 12) -> QWidget:
    """뷰어 위젯을 좌우 h px 패딩 컨테이너로 감싼다. 헤더는 full-width 유지."""
    wrapper = QWidget()
    layout = QVBoxLayout(wrapper)
    layout.setContentsMargins(h, 0, h, 0)
    layout.setSpacing(0)
    layout.addWidget(widget)
    return wrapper


# ── 섹션 헤더 레이블 ─────────────────────────────────────────────────

def _section_header(title: str) -> QLabel:
    """비접이식 섹션 구분 헤더."""
    lbl = QLabel(title)
    lbl.setStyleSheet(
        "background-color: #F1F5F9;"
        "border-top: 1px solid #E2E8F0;"
        "border-bottom: 1px solid #E2E8F0;"
        "font-weight: 600; font-size: 12px; color: #1E293B;"
        "padding: 5px 12px;"
    )
    lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    return lbl


# ── ResultViewerWidget ────────────────────────────────────────────

class ResultViewerWidget(QScrollArea):
    """
    Trial 선택 시 중앙 패널에 표시되는 결과 뷰어.
    VideoPlayer → 3D Keypoints → Kinematics 순으로 플랫 배치.
    # Design Ref: §2.1 — ResultViewerWidget (플랫, collapse 없음)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # ── 뷰어 위젯 인스턴스 ────────────────────────────────────
        self.video_player = VideoPlayerWidget()
        self.viewer_3d    = Viewer3DWidget()
        self.kine_viewer  = KinematicsViewerWidget()
        # Design Ref: §6.3 — KinematicsViewerWidget (M10)

        # ── 플랫 레이아웃 ─────────────────────────────────────────
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 헤더는 full-width, 뷰어만 좌우 12px 패딩
        layout.addWidget(_section_header("Videos"))
        layout.addWidget(_padded(self.video_player))

        layout.addWidget(_section_header("3D Keypoints"))
        layout.addWidget(_padded(self.viewer_3d))

        layout.addWidget(_section_header("Kinematics"))
        layout.addWidget(_padded(self.kine_viewer))

        layout.addStretch()
        self.setWidget(inner)

    def wheelEvent(self, event):
        # 가로 스크롤(트랙패드 좌우 스와이프) 차단
        if abs(event.angleDelta().x()) > abs(event.angleDelta().y()):
            event.ignore()
            return
        super().wheelEvent(event)

    def load_trial(self, trial: Trial):
        """
        Trial 전환 시 세 뷰어 모두 갱신.
        # Design Ref: §2.1 — load_trial
        """
        self.video_player.load_trial(trial)
        self.viewer_3d.load_trial(trial)
        self.kine_viewer.load_trial(trial)
