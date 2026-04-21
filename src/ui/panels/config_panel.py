"""
Config.toml 폼 에디터 패널
# Design Ref: §7.2 — QTabWidget: Project / Calibration / Pose / Sync /
#              Triangulation / Filtering / Augmentation / Kinematics
# Plan SC: SC-02 — Config.toml 모든 주요 파라미터 폼 UI 표시
"""
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QListWidget, QListWidgetItem,
    QLabel,
    QPushButton, QScrollArea,
    QSizePolicy, QFrame,
)
from PyQt6.QtCore import pyqtSignal, Qt

from src.core.config_manager import ConfigManager
from src.ui.widgets.param_widget import make_param_widget


# Config 섹션 → 탭 표시 순서
# Design Ref: §7.2
_TAB_ORDER = [
    ("project",          "Project"),
    ("pose",             "Pose"),
    ("synchronization",  "Sync"),
    ("triangulation",    "Triangulation"),
    ("filtering",        "Filtering"),
    ("markerAugmentation", "Augmentation"),
    ("kinematics",       "Kinematics"),
]

# 중첩 dict 섹션 (Filtering 하위 필터별 파라미터 등)은 펼쳐서 표시할 키
_EXPAND_SUBSECTIONS = {"butterworth", "gaussian", "LOESS", "median"}

# UI에서 숨길 파라미터 (값은 config에 유지, 저장 시 보존됨)
_HIDDEN_KEYS: dict[str, set] = {
    "project": {"frame_rate", "exclude_from_batch"},
    "pose": {"vid_img_extension", "device", "backend", "parallel_workers_pose", "save_video", "output_format", "tracking_mode",
             "display_detection"},
    "synchronization": {"approx_time_maxspeed", "keypoints_to_consider"},
    "filtering": {
        "type", "display_figures","save_filt_plots",
        "kalman", "one_euro", "gcv_spline", "gaussian",
        "loess", "median", "butterworth_on_speed",
    },
    "kinematics": {"parallel_workers_kinematics"}
}

# config에서 완전히 제거할 파라미터 (저장 시에도 포함되지 않음)
_DELETE_KEYS: dict[str, set] = {
    "markerAugmentation": {"participant_height", "participant_mass"},
}


class _SectionTab(QScrollArea):
    """
    하나의 Config 섹션(dict)을 표시하는 스크롤 탭.
    - bool: 체크박스 + 라벨 수평 배치
    - 그 외: 라벨(위) + 입력 위젯(아래) 수직 배치
    """
    param_changed = pyqtSignal(str, object)   # key, new_value

    def __init__(self, section_data: dict, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self._widgets: dict[str, QWidget] = {}

        inner = QWidget()
        inner.setMinimumWidth(200)
        inner.setStyleSheet(
            "QLabel, QSpinBox, QDoubleSpinBox, QLineEdit,"
            "QComboBox, QCheckBox, QGroupBox { font-size: 11px; }"
        )
        outer_layout = QVBoxLayout(inner)
        outer_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        outer_layout.setSpacing(2)
        outer_layout.setContentsMargins(12, 8, 12, 8)

        for key, value in section_data.items():
            if isinstance(value, dict):
                outer_layout.addWidget(self._build_group(key, value))
            else:
                self._add_field(outer_layout, key, value, key)

        outer_layout.addStretch()
        self.setWidget(inner)

    def _add_field(self, layout: QVBoxLayout, key: str, value, signal_key: str):
        """단일 파라미터 필드를 layout에 추가."""
        widget = make_param_widget(key, value)
        self._widgets[signal_key] = widget
        if hasattr(widget, "value_changed"):
            widget.value_changed.connect(
                lambda v, k=signal_key: self.param_changed.emit(k, v)
            )

        if isinstance(value, bool):
            # bool: 체크박스 왼쪽, 라벨 오른쪽 수평 배치
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 3, 0, 3)
            rl.setSpacing(6)
            lbl = QLabel(key.replace("_", " "))
            lbl.setToolTip(key)
            lbl.setStyleSheet("color: #64748B; font-size: 10px;")
            rl.addWidget(widget)
            rl.addWidget(lbl)
            rl.addStretch()
            layout.addWidget(row)
        else:
            # 비-bool: 라벨 위, 입력 위젯 아래 수직 배치
            container = QWidget()
            cl = QVBoxLayout(container)
            cl.setContentsMargins(0, 4, 0, 4)
            cl.setSpacing(3)
            lbl = QLabel(key.replace("_", " "))
            lbl.setToolTip(key)
            lbl.setStyleSheet("color: #64748B; font-size: 10px;")
            lbl.setWordWrap(True)
            cl.addWidget(lbl)
            cl.addWidget(widget)
            layout.addWidget(container)

    def _build_group(self, group_key: str, group_data: dict) -> QWidget:
        """중첩 dict를 그룹명+필드명 인라인 라벨로 표시 (박스 없음)."""
        container = QWidget()
        vl = QVBoxLayout(container)
        vl.setContentsMargins(0, 4, 0, 0)
        vl.setSpacing(0)

        items = [(k, v) for k, v in group_data.items() if not isinstance(v, dict)]
        for i, (key, value) in enumerate(items):
            full_key = f"{group_key}.{key}"
            widget = make_param_widget(key, value)
            self._widgets[full_key] = widget
            if hasattr(widget, "value_changed"):
                widget.value_changed.connect(
                    lambda v, k=full_key: self.param_changed.emit(k, v)
                )

            field_w = QWidget()
            fl = QVBoxLayout(field_w)
            fl.setContentsMargins(0, 6, 0, 4)
            fl.setSpacing(3)

            # 그룹명(굵음) + 필드명(연함) 인라인 헤더
            header = QWidget()
            hl = QHBoxLayout(header)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setSpacing(5)
            grp_lbl = QLabel(group_key)
            grp_lbl.setStyleSheet("color: #64748B; font-size: 10px;")
            fld_lbl = QLabel(key.replace("_", " "))
            fld_lbl.setStyleSheet("color: #64748B; font-size: 10px;")
            hl.addWidget(grp_lbl)
            hl.addWidget(fld_lbl)
            hl.addStretch()
            fl.addWidget(header)
            fl.addWidget(widget)
            vl.addWidget(field_w)

            if i < len(items) - 1:
                sep = QFrame()
                sep.setFrameShape(QFrame.Shape.HLine)
                sep.setStyleSheet("color: #E2E8F0; margin: 0px;")
                vl.addWidget(sep)

        return container

    def collect_values(self) -> dict:
        """현재 위젯 값을 플랫 dict로 수집. 중첩 키는 '.'로 구분."""
        result = {}
        for key, widget in self._widgets.items():
            if hasattr(widget, "get_value"):
                result[key] = widget.get_value()
        return result


class ConfigPanel(QWidget):
    """
    Config.toml 전체를 섹션별 탭으로 표시하는 편집 패널.
    변경 즉시 파일에 저장하는 실시간 저장 모드 지원.

    # Design Ref: §7.2 — Config 탭 구성
    # Plan SC: SC-02, SC-07
    """

    config_changed = pyqtSignal(dict)   # 변경된 전체 config dict

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config_path: Path | None = None
        self._config: dict = {}
        self._manager = ConfigManager()
        self._tabs: dict[str, _SectionTab] = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── 상단 툴바: 파일 경로 + 저장/초기화 ───────────────────────
        toolbar_widget = QWidget()
        toolbar_widget.setStyleSheet("background-color: #F8FAFC;")
        toolbar = QHBoxLayout(toolbar_widget)
        toolbar.setContentsMargins(8, 4, 8, 4)
        toolbar.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self._path_label = QLabel("설정 파일: (없음)")
        self._path_label.setStyleSheet("color: #64748B; font-size: 11px;")
        self._path_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        toolbar.addWidget(self._path_label)

        _btn_ss = "QPushButton { padding: 3px 4px; text-align: center; }"
        save_btn = QPushButton("저장")
        save_btn.setFixedSize(60, 26)
        save_btn.setStyleSheet(_btn_ss)
        save_btn.clicked.connect(self._save_config)
        reset_btn = QPushButton("기본값")
        reset_btn.setFixedSize(60, 26)
        reset_btn.setStyleSheet(_btn_ss)
        reset_btn.setToolTip("기본값으로 초기화")
        reset_btn.clicked.connect(self._reset_to_default)
        toolbar.addWidget(save_btn)
        toolbar.addWidget(reset_btn)
        layout.addWidget(toolbar_widget)

        # border-bottom을 별도 QFrame으로 분리 (부모 border가 자식을 클리핑하는 Qt 이슈 방지)
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFixedHeight(1)
        divider.setStyleSheet("background-color: #E2E8F0; border: none;")
        layout.addWidget(divider)

        # ── 본문: 좌측 섹션 리스트 + 우측 스택 ──────────────────────
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        # 좌측 섹션 리스트
        self._section_list = QListWidget()
        self._section_list.setFixedWidth(100)
        self._section_list.setFrameShape(QFrame.Shape.NoFrame)
        self._section_list.setStyleSheet(
            "QListWidget {"
            "  background-color: #F8FAFC;"
            "  border-right: 1px solid #E2E8F0;"
            "  font-size: 11px;"
            "  outline: none;"
            "}"
            "QListWidget::item {"
            "  padding: 7px 10px;"
            "  color: #475569;"
            "}"
            "QListWidget::item:selected {"
            "  background-color: #EFF6FF;"
            "  color: #2563EB;"
            "  font-weight: 600;"
            "}"
            "QListWidget::item:hover:!selected {"
            "  background-color: #F1F5F9;"
            "}"
        )
        self._section_list.currentRowChanged.connect(self._on_section_changed)
        body.addWidget(self._section_list)

        # 우측 콘텐츠 스택
        self._section_stack = QStackedWidget()
        body.addWidget(self._section_stack, 1)

        layout.addLayout(body, 1)

    def load_config(self, config_path: Path):
        """
        지정된 Config.toml을 로드하고 탭을 재구성.
        # Plan SC: SC-07 — 프로젝트 전환 시 설정 독립 유지
        """
        self._config_path = config_path
        self._config = self._manager.load_or_default(config_path)
        for section, keys in _DELETE_KEYS.items():
            if section in self._config:
                for k in keys:
                    self._config[section].pop(k, None)
        self._path_label.setText(f"설정: {config_path.name}")
        self._rebuild_sections()

    def _rebuild_sections(self):
        """config dict를 읽어 섹션 리스트 + 스택을 다시 빌드."""
        # 기존 내용 제거
        self._section_list.clear()
        self._tabs.clear()
        while self._section_stack.count():
            w = self._section_stack.widget(0)
            self._section_stack.removeWidget(w)
            w.deleteLater()

        for section_key, section_label in _TAB_ORDER:
            section_data = self._config.get(section_key, {})
            if not section_data:
                continue
            hidden = _HIDDEN_KEYS.get(section_key, set())
            if hidden:
                section_data = {k: v for k, v in section_data.items() if k not in hidden}
            tab = _SectionTab(section_data)
            tab.param_changed.connect(
                lambda key, v, sk=section_key: self._on_param_changed(sk, key, v)
            )
            self._tabs[section_key] = tab
            self._section_stack.addWidget(tab)
            self._section_list.addItem(QListWidgetItem(section_label))

        if self._section_list.count() > 0:
            self._section_list.setCurrentRow(0)

    def _on_section_changed(self, row: int):
        """섹션 리스트 선택 변경 → 스택 페이지 전환."""
        if row >= 0:
            self._section_stack.setCurrentIndex(row)

    def _on_param_changed(self, section_key: str, param_key: str, value):
        """
        개별 파라미터 변경 시 config dict 즉시 업데이트.
        중첩 키('.')가 있으면 하위 dict 탐색.
        """
        section = self._config.setdefault(section_key, {})
        if "." in param_key:
            parts = param_key.split(".", 1)
            subsection = section.setdefault(parts[0], {})
            subsection[parts[1]] = value
        else:
            section[param_key] = value
        self.config_changed.emit(self._config)

    def _save_config(self):
        """현재 설정을 Config.toml에 저장."""
        if self._config_path is None:
            return
        # 모든 탭의 최신 위젯 값을 수집해 config에 반영
        for section_key, tab in self._tabs.items():
            flat = tab.collect_values()
            section = self._config.setdefault(section_key, {})
            for key, value in flat.items():
                if "." in key:
                    parts = key.split(".", 1)
                    section.setdefault(parts[0], {})[parts[1]] = value
                else:
                    section[key] = value
        self._manager.save(self._config, self._config_path)
        self._path_label.setText(f"설정: {self._config_path.name}  ✓ 저장됨")

    def _reset_to_default(self):
        """기본값으로 초기화 후 탭 재빌드."""
        self._config = self._manager.get_default_config()
        for section, keys in _DELETE_KEYS.items():
            if section in self._config:
                for k in keys:
                    self._config[section].pop(k, None)
        if self._config_path:
            self._config["project"]["project_dir"] = str(
                self._config_path.parent
            )
        self._rebuild_sections()
        self.config_changed.emit(self._config)

    def get_config(self) -> dict:
        return self._config
