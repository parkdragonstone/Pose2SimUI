"""
Config 파라미터 위젯 — 값 타입별 입력 위젯 팩토리
# Design Ref: §7.1 — WIDGET_MAP: bool→QCheckBox, int→QSpinBox, float→QDoubleSpinBox
#                     str→QLineEdit/QComboBox, list→DynamicListWidget
"""
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout,
    QCheckBox, QSpinBox, QDoubleSpinBox,
    QLineEdit, QComboBox, QListWidget,
    QPushButton, QListWidgetItem, QLabel,
    QSizePolicy,
)
from PyQt6.QtCore import pyqtSignal, Qt
import base64

# ── SpinBox 화살표 SVG (base64) ──────────────────────────────────────────
_UP_B64 = base64.b64encode(
    b'<svg xmlns="http://www.w3.org/2000/svg" width="12" height="9">'
    b'<path d="M6 1L11 8H1Z" fill="#1E3A5F"/></svg>'
).decode()
_DN_B64 = base64.b64encode(
    b'<svg xmlns="http://www.w3.org/2000/svg" width="12" height="9">'
    b'<path d="M1 1L11 1L6 8Z" fill="#1E3A5F"/></svg>'
).decode()

# ── SpinBox 공통 스타일 ──────────────────────────────────────────────────
_SPIN_SS = (
    "QSpinBox, QDoubleSpinBox {"
    "  color: #1E293B; background: #FFFFFF; font-size: 11px;"
    "  border: 1px solid #CBD5E1; border-radius: 4px;"
    "  padding: 3px 2px 3px 6px; min-height: 26px;"
    "}"
    "QSpinBox:focus, QDoubleSpinBox:focus { border-color: #2563EB; color: #1E293B; background: #FFFFFF; }"
    "QSpinBox::selection, QDoubleSpinBox::selection {"
    "  color: #FFFFFF; background: #2563EB;"
    "}"
    "QSpinBox::up-button, QDoubleSpinBox::up-button {"
    "  subcontrol-origin: border; subcontrol-position: top right;"
    "  width: 26px;"
    "  border-left: 1px solid #CBD5E1; border-bottom: 1px solid #CBD5E1;"
    "  border-top-right-radius: 3px; background: #F1F5F9;"
    "}"
    "QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover { background: #DBEAFE; }"
    "QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed { background: #BFDBFE; }"
    f"QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{"
    f"  image: url('data:image/svg+xml;base64,{_UP_B64}'); width: 10px; height: 8px;"
    f"}}"
    "QSpinBox::down-button, QDoubleSpinBox::down-button {"
    "  subcontrol-origin: border; subcontrol-position: bottom right;"
    "  width: 26px;"
    "  border-left: 1px solid #CBD5E1; border-top: 1px solid #CBD5E1;"
    "  border-bottom-right-radius: 3px; background: #F1F5F9;"
    "}"
    "QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover { background: #DBEAFE; }"
    "QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed { background: #BFDBFE; }"
    f"QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{"
    f"  image: url('data:image/svg+xml;base64,{_DN_B64}'); width: 10px; height: 8px;"
    f"}}"
)

# ── COMBO_PARAMS: 선택지가 있는 str 파라미터 ──────────────────────────────
# Design Ref: §7.1
COMBO_PARAMS: dict[str, list[str]] = {
    "pose_model":  [
        "Body_with_feet", "Whole_body_wrist", "Whole_body",
        "Body", "Feet", "Face",
    ],
    "mode":        ["lightweight", "balanced", "performance"],
    "type":        ["butterworth", "kalman", "butterworth_on_speed",
                    "gaussian", "LOESS", "median"],
    "save_video":  ["to_video", "to_images", "False"],
    "keypoints_to_consider": ["all", "right", "left", "ankles"],
    "interpolation": ["cubic", "slinear", "linear", "nearest", "None"],
    "person_association": ["best_results_person", "largest_person"],
    "sections_to_keep":   ["all", "largest", "first", "last"],
    "fill_large_gaps_with": ["last_value", "nan", "zeros"],
}


class BoolParamWidget(QWidget):
    """bool 값 → QCheckBox"""
    value_changed = pyqtSignal(bool)

    def __init__(self, key: str, value: bool, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._cb = QCheckBox()
        self._cb.setChecked(bool(value))
        self._cb.toggled.connect(self.value_changed)
        layout.addWidget(self._cb)

    def get_value(self) -> bool:
        return self._cb.isChecked()

    def set_value(self, v: bool):
        self._cb.setChecked(bool(v))


class IntParamWidget(QWidget):
    """int 값 → QSpinBox"""
    value_changed = pyqtSignal(int)

    def __init__(self, key: str, value: int, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._spin = QSpinBox()
        self._spin.setStyleSheet(_SPIN_SS)
        self._spin.setRange(-999999, 999999)
        self._spin.setValue(int(value))
        self._spin.setMinimumWidth(60)
        self._spin.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._spin.valueChanged.connect(self.value_changed)
        layout.addWidget(self._spin)

    def get_value(self) -> int:
        return self._spin.value()

    def set_value(self, v: int):
        self._spin.setValue(int(v))


class FloatParamWidget(QWidget):
    """float 값 → QDoubleSpinBox"""
    value_changed = pyqtSignal(float)

    def __init__(self, key: str, value: float, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._spin = QDoubleSpinBox()
        self._spin.setStyleSheet(_SPIN_SS)
        self._spin.setRange(-999999.0, 999999.0)
        self._spin.setDecimals(4)
        self._spin.setSingleStep(0.1)
        self._spin.setValue(float(value))
        self._spin.setMinimumWidth(60)
        self._spin.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._spin.valueChanged.connect(self.value_changed)
        layout.addWidget(self._spin)

    def get_value(self) -> float:
        return self._spin.value()

    def set_value(self, v: float):
        self._spin.setValue(float(v))


class ComboParamWidget(QWidget):
    """str 값 (선택지 있음) → QComboBox"""
    value_changed = pyqtSignal(str)

    def __init__(self, key: str, value: str, choices: list[str], parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._combo = QComboBox()
        self._combo.addItems(choices)
        if str(value) in choices:
            self._combo.setCurrentText(str(value))
        self._combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents
        )
        # 가장 긴 항목 길이를 최소 기준으로 확보 (팝업 잘림 방지)
        max_len = max((len(c) for c in choices), default=8)
        self._combo.setMinimumContentsLength(max_len)
        self._combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._combo.currentTextChanged.connect(self.value_changed)
        layout.addWidget(self._combo)

    def get_value(self) -> str:
        return self._combo.currentText()

    def set_value(self, v: str):
        idx = self._combo.findText(str(v))
        if idx >= 0:
            self._combo.setCurrentIndex(idx)


class StrParamWidget(QWidget):
    """str 값 → QLineEdit"""
    value_changed = pyqtSignal(str)

    def __init__(self, key: str, value: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._edit = QLineEdit(str(value))
        self._edit.setMinimumWidth(60)
        self._edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._edit.textChanged.connect(self.value_changed)
        layout.addWidget(self._edit)

    def get_value(self) -> str:
        return self._edit.text()

    def set_value(self, v: str):
        self._edit.setText(str(v))


class ListParamWidget(QWidget):
    """
    list 값 → 동적 리스트 위젯 (항목 추가/삭제)
    # Design Ref: §7.1 — list → DynamicListWidget
    """
    value_changed = pyqtSignal(list)

    def __init__(self, key: str, value: list, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._list = QListWidget()
        self._list.setMaximumHeight(80)
        for item in value:
            self._list.addItem(str(item))
        layout.addWidget(self._list)

        btn_row = QHBoxLayout()
        self._entry = QLineEdit()
        self._entry.setPlaceholderText("값 입력 후 추가")
        add_btn = QPushButton("+")
        add_btn.setFixedWidth(28)
        add_btn.clicked.connect(self._add_item)
        del_btn = QPushButton("−")
        del_btn.setFixedWidth(28)
        del_btn.clicked.connect(self._del_item)
        btn_row.addWidget(self._entry)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(del_btn)
        layout.addLayout(btn_row)

    def _add_item(self):
        text = self._entry.text().strip()
        if text:
            self._list.addItem(text)
            self._entry.clear()
            self.value_changed.emit(self.get_value())

    def _del_item(self):
        for item in self._list.selectedItems():
            self._list.takeItem(self._list.row(item))
        self.value_changed.emit(self.get_value())

    def get_value(self) -> list:
        return [self._list.item(i).text() for i in range(self._list.count())]

    def set_value(self, v: list):
        self._list.clear()
        for item in v:
            self._list.addItem(str(item))


def make_param_widget(key: str, value) -> QWidget:
    """
    값 타입과 키 이름을 보고 적절한 파라미터 위젯을 반환하는 팩토리.
    # Design Ref: §7.1 — WIDGET_MAP
    """
    if key in COMBO_PARAMS:
        choices = COMBO_PARAMS[key]
        return ComboParamWidget(key, str(value), choices)
    if isinstance(value, bool):
        return BoolParamWidget(key, value)
    if isinstance(value, int):
        return IntParamWidget(key, value)
    if isinstance(value, float):
        return FloatParamWidget(key, value)
    if isinstance(value, list):
        return ListParamWidget(key, value)
    # str 또는 그 외 (str로 변환)
    return StrParamWidget(key, str(value) if value is not None else "")
