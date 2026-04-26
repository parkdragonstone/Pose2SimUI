"""
Pose2SimUI — Main entry point
# Design Ref: §1.1 — Option C 실용적 모듈 아키텍처
"""
import os
import sys
from pathlib import Path

# pyqtgraph가 PyQt5를 사용하도록 고정 (UI와 Pose2Sim 모두 PyQt5 사용).
os.environ.setdefault("PYQTGRAPH_QT_LIB", "PyQt5")

# Qt multimedia / OpenCV FFmpeg 백엔드가 동영상 프로브 시 stderr에 상세 스트림 정보를 출력.
# QApplication 생성 전에 환경변수로 억제 (런타임에 변경 불가).
os.environ.setdefault("AV_LOG_LEVEL", "quiet")           # Qt multimedia FFmpeg: quiet
os.environ.setdefault("QT_LOGGING_RULES",                # Qt 멀티미디어 로그 억제
    "qt.multimedia.ffmpeg=false;qt.multimedia.*=false")
os.environ.setdefault("OPENCV_LOG_LEVEL", "SILENT")      # OpenCV 자체 로그 억제
os.environ.setdefault("OPENCV_FFMPEG_LOGLEVEL", "-8")    # OpenCV FFmpeg: AV_LOG_QUIET(-8)

# src 패키지 경로를 Python path에 추가 (PyInstaller 패키징 시에도 동작)
sys.path.insert(0, str(Path(__file__).parent))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from src.ui.main_window import MainWindow
from src.utils.theme import apply_theme


def main():
    # HiDPI 지원 (macOS / Windows) — PyQt5 방식
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)
    app.setApplicationName("Pose2SimUI")
    app.setOrganizationName("Pose2SimUI")

    # Visual Design System 적용
    # Design Ref: §12 — 투톤 레이아웃, Blue 포인트 컬러
    apply_theme(app)

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
