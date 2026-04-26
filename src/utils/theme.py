"""
Visual Design System — QSS 스타일시트
# Design Ref: §12 — 투톤 레이아웃 (다크 사이드바 + 라이트 메인), Blue 포인트 컬러
# 참고: Behance Desktop UI Design App 스타일
"""
import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont, QPalette, QColor
from PyQt5.QtCore import Qt

# 플랫폼별 실제 존재하는 폰트 사용 (font alias 경고 방지)
_UI_FONT = "Helvetica Neue" if sys.platform == "darwin" else "Segoe UI"


# ── 디자인 토큰 ──────────────────────────────────────────────────────────
# Design Ref: §12.1 컬러 팔레트

COLOR = {
    # 포인트
    "primary":        "#2563EB",
    "primary_hover":  "#1D4ED8",
    "primary_active": "#1E40AF",
    "primary_light":  "#EFF6FF",

    # 사이드바 (다크)
    "sidebar_bg":     "#1E2433",
    "sidebar_text":   "#CBD5E1",
    "sidebar_muted":  "#94A3B8",
    "sidebar_hover":  "#2D3748",
    "sidebar_active": "#2563EB",
    "sidebar_border": "#2D3748",

    # 메인 영역 (라이트)
    "surface":        "#FFFFFF",
    "surface_subtle": "#F8FAFC",
    "surface_hover":  "#F1F5F9",

    # 테두리 & 텍스트
    "border":         "#E2E8F0",
    "border_focus":   "#2563EB",
    "text_primary":   "#1E293B",
    "text_secondary": "#64748B",
    "text_muted":     "#94A3B8",

    # 상태
    "success":        "#16A34A",
    "success_bg":     "#F0FDF4",
    "error":          "#DC2626",
    "error_bg":       "#FEF2F2",
    "warning":        "#D97706",
    "warning_bg":     "#FFFBEB",
    "running_bg":     "#EFF6FF",

    # 로그 패널
    "log_bg":         "#0F172A",
    "log_text":       "#94A3B8",
    "log_border":     "#1E293B",
}


QSS = f"""
/* ═══════════════════════════════════════════════════════════════
   Global Reset & Base
═══════════════════════════════════════════════════════════════ */
QWidget {{
    font-family: "{_UI_FONT}", Arial;
    font-size: 12px;
    color: {COLOR['text_primary']};
    background-color: {COLOR['surface']};
    outline: none;
}}

QMainWindow {{
    background-color: {COLOR['surface']};
}}

/* ═══════════════════════════════════════════════════════════════
   Sidebar — 다크 테마
═══════════════════════════════════════════════════════════════ */
#sidebar {{
    background-color: {COLOR['sidebar_bg']};
    border-right: 1px solid {COLOR['sidebar_border']};
}}

#sidebar QWidget {{
    background-color: {COLOR['sidebar_bg']};
    color: {COLOR['sidebar_text']};
}}

#sidebar QLabel {{
    color: {COLOR['sidebar_text']};
    background-color: transparent;
}}

#sidebar QPushButton {{
    background-color: transparent;
    color: {COLOR['sidebar_text']};
    border: none;
    border-radius: 4px;
    padding: 6px 10px;
    text-align: left;
    font-size: 12px;
}}

#sidebar QPushButton:hover {{
    background-color: {COLOR['sidebar_hover']};
}}

#sidebar QPushButton:pressed {{
    background-color: {COLOR['sidebar_active']};
    color: #FFFFFF;
}}

#sidebar QListWidget {{
    background-color: transparent;
    border: none;
    color: {COLOR['sidebar_text']};
    outline: none;
}}

#sidebar QListWidget::item {{
    padding: 6px 12px;
    border-radius: 4px;
    margin: 1px 4px;
}}

#sidebar QListWidget::item:hover {{
    background-color: {COLOR['sidebar_hover']};
}}

#sidebar QListWidget::item:selected {{
    background-color: {COLOR['sidebar_active']};
    color: #FFFFFF;
}}

#sidebar QFrame[frameShape="4"] {{
    background-color: {COLOR['sidebar_border']};
    border: none;
    max-height: 1px;
    margin: 4px 8px;
}}

/* ═══════════════════════════════════════════════════════════════
   Project Panel (사이드바 내)
═══════════════════════════════════════════════════════════════ */
#project_label {{
    color: #FFFFFF;
    font-weight: 700;
    font-size: 13px;
    padding: 4px 0;
}}

/* ═══════════════════════════════════════════════════════════════
   Buttons
═══════════════════════════════════════════════════════════════ */
QPushButton {{
    background-color: {COLOR['primary_light']};
    color: {COLOR['primary']};
    border: 1.5px solid #BFDBFE;
    border-radius: 6px;
    padding: 0 10px;
    height: 26px;
    font-size: 11px;
    font-weight: bold;
}}

QPushButton:hover {{
    background-color: #DBEAFE;
    border-color: {COLOR['primary']};
}}

QPushButton:pressed {{
    background-color: #BFDBFE;
}}

QPushButton:disabled {{
    color: {COLOR['text_muted']};
    border-color: {COLOR['border']};
    background-color: {COLOR['surface_subtle']};
}}

/* Primary 버튼 (Run All) — 직접 스타일 지정 */
QPushButton#run_all_btn {{
    background-color: {COLOR['primary']};
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    font-weight: 600;
    height: 32px;
}}

QPushButton#run_all_btn:hover {{
    background-color: {COLOR['primary_hover']};
}}

QPushButton#run_all_btn:disabled {{
    background-color: {COLOR['text_muted']};
}}

/* ═══════════════════════════════════════════════════════════════
   QTabWidget
═══════════════════════════════════════════════════════════════ */
QTabWidget::pane {{
    border: 1px solid {COLOR['border']};
    border-radius: 0 6px 6px 6px;
    background-color: {COLOR['surface']};
}}

QTabBar::tab {{
    background-color: transparent;
    color: {COLOR['text_secondary']};
    padding: 7px 16px;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: 12px;
    margin-right: 2px;
}}

QTabBar::tab:selected {{
    color: {COLOR['primary']};
    border-bottom: 2px solid {COLOR['primary']};
    font-weight: 600;
}}

QTabBar::tab:hover:!selected {{
    color: {COLOR['text_primary']};
    background-color: {COLOR['surface_hover']};
}}

/* ═══════════════════════════════════════════════════════════════
   StepCard
═══════════════════════════════════════════════════════════════ */
StepCard {{
    background-color: {COLOR['surface']};
    border: 1px solid {COLOR['border']};
    border-radius: 6px;
    margin: 2px 0;
}}

StepCard:hover {{
    border-color: {COLOR['text_muted']};
    background-color: {COLOR['surface_hover']};
}}

StepCard[status="running"] {{
    background-color: {COLOR['running_bg']};
    border-color: {COLOR['primary']};
}}

StepCard[status="success"] {{
    background-color: {COLOR['success_bg']};
    border-color: {COLOR['success']};
}}

StepCard[status="failed"] {{
    background-color: {COLOR['error_bg']};
    border-color: {COLOR['error']};
}}

/* ═══════════════════════════════════════════════════════════════
   Input Widgets
═══════════════════════════════════════════════════════════════ */
QLineEdit, QSpinBox, QDoubleSpinBox {{
    background-color: {COLOR['surface']};
    color: {COLOR['text_primary']};
    border: 1px solid {COLOR['border']};
    border-radius: 4px;
    padding: 3px 8px;
    height: 26px;
    selection-background-color: {COLOR['primary_light']};
}}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {COLOR['border_focus']};
}}

QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
    background-color: {COLOR['surface_subtle']};
    color: {COLOR['text_muted']};
}}

QComboBox {{
    background-color: {COLOR['surface']};
    color: {COLOR['text_primary']};
    border: 1px solid {COLOR['border']};
    border-radius: 4px;
    padding: 3px 8px;
    height: 26px;
}}

QComboBox:focus {{
    border-color: {COLOR['border_focus']};
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

QComboBox QAbstractItemView {{
    background-color: {COLOR['surface']};
    border: 1px solid {COLOR['border']};
    border-radius: 4px;
    selection-background-color: {COLOR['primary_light']};
    color: {COLOR['text_primary']};
    outline: none;
}}

QCheckBox {{
    spacing: 6px;
    color: {COLOR['text_primary']};
}}

QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1.5px solid {COLOR['border']};
    border-radius: 3px;
    background-color: {COLOR['surface']};
}}

QCheckBox::indicator:checked {{
    background-color: {COLOR['primary']};
    border-color: {COLOR['primary']};
}}

/* ═══════════════════════════════════════════════════════════════
   QScrollArea & ScrollBar
═══════════════════════════════════════════════════════════════ */
QScrollArea {{
    background-color: transparent;
    border: none;
}}

QScrollBar:vertical {{
    background-color: transparent;
    width: 6px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background-color: {COLOR['border']};
    border-radius: 3px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {COLOR['text_muted']};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background-color: transparent;
    height: 6px;
    margin: 0;
}}

QScrollBar::handle:horizontal {{
    background-color: {COLOR['border']};
    border-radius: 3px;
    min-width: 30px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {COLOR['text_muted']};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ═══════════════════════════════════════════════════════════════
   QGroupBox
═══════════════════════════════════════════════════════════════ */
QGroupBox {{
    border: 1px solid {COLOR['border']};
    border-radius: 6px;
    margin-top: 14px;
    padding-top: 8px;
    font-weight: 600;
    font-size: 11px;
    color: {COLOR['text_secondary']};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    background-color: {COLOR['surface']};
}}

/* ═══════════════════════════════════════════════════════════════
   QSplitter
═══════════════════════════════════════════════════════════════ */
QSplitter::handle {{
    background-color: {COLOR['border']};
}}

QSplitter::handle:horizontal {{
    width: 1px;
}}

QSplitter::handle:vertical {{
    height: 1px;
}}

/* ═══════════════════════════════════════════════════════════════
   QProgressBar (StepCard 내)
═══════════════════════════════════════════════════════════════ */
QProgressBar {{
    background-color: {COLOR['border']};
    border: none;
    border-radius: 2px;
    height: 4px;
}}

QProgressBar::chunk {{
    background-color: {COLOR['primary']};
    border-radius: 2px;
}}

/* ═══════════════════════════════════════════════════════════════
   QMenuBar & QMenu
═══════════════════════════════════════════════════════════════ */
QMenuBar {{
    background-color: {COLOR['sidebar_bg']};
    color: {COLOR['sidebar_text']};
    border-bottom: 1px solid {COLOR['sidebar_border']};
    padding: 2px;
}}

QMenuBar::item {{
    padding: 4px 10px;
    border-radius: 4px;
    background-color: transparent;
}}

QMenuBar::item:selected {{
    background-color: {COLOR['sidebar_hover']};
    color: #FFFFFF;
}}

QMenu {{
    background-color: {COLOR['surface']};
    border: 1px solid {COLOR['border']};
    border-radius: 6px;
    padding: 4px;
}}

QMenu::item {{
    padding: 6px 16px;
    border-radius: 4px;
    color: {COLOR['text_primary']};
}}

QMenu::item:selected {{
    background-color: {COLOR['primary_light']};
    color: {COLOR['primary']};
}}

QMenu::separator {{
    height: 1px;
    background-color: {COLOR['border']};
    margin: 4px 8px;
}}

/* ═══════════════════════════════════════════════════════════════
   QStatusBar
═══════════════════════════════════════════════════════════════ */
QStatusBar {{
    background-color: {COLOR['sidebar_bg']};
    color: {COLOR['sidebar_muted']};
    font-size: 11px;
    border-top: 1px solid {COLOR['sidebar_border']};
    padding: 0 8px;
}}

/* ═══════════════════════════════════════════════════════════════
   Log Panel
═══════════════════════════════════════════════════════════════ */
#log_header {{
    background-color: {COLOR['surface_subtle']};
    border-top: 1px solid {COLOR['border']};
}}

/* ═══════════════════════════════════════════════════════════════
   QDialog
═══════════════════════════════════════════════════════════════ */
QDialog {{
    background-color: {COLOR['surface']};
}}

QDialogButtonBox QPushButton {{
    min-width: 72px;
}}

/* ═══════════════════════════════════════════════════════════════
   QToolTip
═══════════════════════════════════════════════════════════════ */
QToolTip {{
    background-color: {COLOR['text_primary']};
    color: #FFFFFF;
    border: none;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 11px;
}}

/* ═══════════════════════════════════════════════════════════════
   QListWidget (일반)
═══════════════════════════════════════════════════════════════ */
QListWidget {{
    background-color: {COLOR['surface']};
    border: 1px solid {COLOR['border']};
    border-radius: 4px;
    outline: none;
}}

QListWidget::item {{
    padding: 5px 8px;
    border-radius: 3px;
}}

QListWidget::item:hover {{
    background-color: {COLOR['surface_hover']};
}}

QListWidget::item:selected {{
    background-color: {COLOR['primary_light']};
    color: {COLOR['primary']};
}}

/* ═══════════════════════════════════════════════════════════════
   QFrame separators
═══════════════════════════════════════════════════════════════ */
QFrame[frameShape="4"],
QFrame[frameShape="5"] {{
    color: {COLOR['border']};
}}

/* ═══════════════════════════════════════════════════════════════
   Welcome Screen
═══════════════════════════════════════════════════════════════ */
#welcome_title {{
    font-size: 28px;
    font-weight: 700;
    color: {COLOR['text_primary']};
}}

#welcome_sub {{
    font-size: 14px;
    color: {COLOR['text_secondary']};
}}
"""


def apply_theme(app: QApplication) -> None:
    """
    앱 전체에 Visual Design System을 적용.
    # Design Ref: §12 — 투톤 레이아웃, Blue 포인트 컬러
    """
    # 기본 폰트 설정 (플랫폼별 실제 존재 폰트 사용)
    font = QFont()
    font.setFamily(_UI_FONT)
    font.setPointSize(12)
    app.setFont(font)

    # QSS 적용
    app.setStyleSheet(QSS)
