"""
Pose2SimUI — Main entry point
# Design Ref: §1.1 — Option C 실용적 모듈 아키텍처
"""
import os
import sys
from pathlib import Path
import shutil

# cv2의 qt 폴더 경로를 찾아서 자동 제거
try:
    import cv2
    cv2_qt_path = os.path.join(os.path.dirname(cv2.__file__), "qt")
    if os.path.exists(cv2_qt_path):
        shutil.rmtree(cv2_qt_path)
        print(f"제거 완료: {cv2_qt_path}")
        # cv2를 다시 로드해야 하므로 프로세스 재시작
        os.execv(sys.executable, [sys.executable] + sys.argv)
except Exception as e:
    print(f"cv2 qt 폴더 처리 중 오류: {e}")
    
# pyqtgraph가 PyQt5를 사용하도록 고정 (UI와 Pose2Sim 모두 PyQt5 사용).
os.environ.setdefault("PYQTGRAPH_QT_LIB", "PyQt5")
os.environ.setdefault("QT_API", "pyqt5")           # matplotlib backend_qtagg가 PyQt5를 선택하도록

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
    import multiprocessing
    multiprocessing.freeze_support()   # PyInstaller frozen app에서 spawn subprocess 필수
    main()
