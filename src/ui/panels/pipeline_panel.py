"""
파이프라인 패널 — Trial 선택 시 중앙 영역에 표시
# Design Ref: §2.2 — [Pipeline|Config] 탭, Calib 드롭다운, Step Cards, Run All/Stop
# Design Ref: §3.2 — Signal 흐름: pipeline_panel → main_window → pipeline_runner
# Plan SC: SC-04 — 파이프라인 각 단계 개별 실행
"""
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QComboBox,
    QPushButton, QScrollArea, QFrame,
    QSizePolicy,
)
from PyQt5.QtCore import pyqtSignal, Qt

from src.core.project import Project, Trial
from src.core.pipeline_runner import PipelineRunner
from src.ui.widgets.step_card import StepCard, StepStatus
from src.ui.panels.config_panel import ConfigPanel


class PipelinePanel(QWidget):
    """
    Trial 선택 후 중앙 영역에 표시되는 파이프라인/설정 패널.

    [Pipeline] 탭: Calib 선택 드롭다운 + Step Cards + Run All / Stop
    [Config] 탭:   ConfigPanel (Config.toml 폼 에디터)

    Signals:
        step_run_requested(str, Path):  step_name, working_dir
        run_all_requested(Path):        working_dir
        cancel_requested():             취소 요청
    """

    step_run_requested = pyqtSignal(str, object)   # step_name, Path
    run_all_requested  = pyqtSignal(object, object) # Path, list[str] enabled steps
    cancel_requested   = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._trial: Trial | None = None
        self._project: Project | None = None
        self._runner: PipelineRunner | None = None
        self._step_cards: dict[str, StepCard] = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        tab_widget = QTabWidget()
        tab_widget.addTab(self._build_pipeline_tab(), "Pipeline")
        tab_widget.addTab(self._build_config_tab(),   "Config")
        layout.addWidget(tab_widget)
        self._tab_widget = tab_widget

    # ── Pipeline 탭 ────────────────────────────────────────────────────

    def _build_pipeline_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Calibration 파일 선택 드롭다운
        # Design Ref: §2.2 — Calibration: [Calib1.toml ▼] (캘리브 파일 선택)
        calib_row = QHBoxLayout()
        calib_label = QLabel("Calibration:")
        calib_label.setFixedWidth(90)
        self._calib_combo = QComboBox()
        self._calib_combo.setMinimumWidth(200)
        self._calib_combo.setPlaceholderText("캘리브 파일 없음")
        self._calib_combo.setToolTip("사이드바에서 Calibration을 먼저 실행하세요")
        calib_row.addWidget(calib_label)
        calib_row.addWidget(self._calib_combo)
        calib_row.addStretch()
        layout.addLayout(calib_row)

        # 구분선
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep)

        # Step Cards 스크롤 영역
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        cards_widget = QWidget()
        cards_layout = QVBoxLayout(cards_widget)
        cards_layout.setSpacing(4)
        cards_layout.setContentsMargins(0, 0, 0, 0)

        for step_name in PipelineRunner.STEP_ORDER:
            label = PipelineRunner.STEP_LABELS[step_name]
            card = StepCard(step_name, label)
            card.run_requested.connect(self._on_run_step)
            self._step_cards[step_name] = card
            cards_layout.addWidget(card)

        cards_layout.addStretch()
        scroll.setWidget(cards_widget)
        layout.addWidget(scroll)

        # Run All / Stop 버튼
        btn_row = QHBoxLayout()
        self._run_all_btn = QPushButton("▶ Run All")
        self._run_all_btn.setFixedHeight(32)
        self._run_all_btn.setStyleSheet(
            "QPushButton { background-color: #1a73e8; color: white; "
            "border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background-color: #1558b0; }"
            "QPushButton:disabled { background-color: #aaa; }"
        )
        self._run_all_btn.clicked.connect(self._on_run_all)

        self._stop_btn = QPushButton("⏹ Stop")
        self._stop_btn.setFixedHeight(32)
        self._stop_btn.setFixedWidth(80)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self.cancel_requested)

        btn_row.addWidget(self._run_all_btn)
        btn_row.addWidget(self._stop_btn)
        layout.addLayout(btn_row)

        return tab

    def _build_config_tab(self) -> QWidget:
        self._config_panel = ConfigPanel()
        return self._config_panel

    # ── 외부 API ──────────────────────────────────────────────────────

    def load_trial(self, trial: Trial, project: Project):
        """
        Trial 전환 시 호출 — Step Card 초기화 + Calib 드롭다운 갱신 + Config 로드.
        # Plan SC: SC-07 — Trial 전환 시 독립 설정 로드
        """
        self._trial = trial
        self._project = project

        # Step Cards 초기화
        for card in self._step_cards.values():
            card.reset()

        # Calib 드롭다운 갱신
        self._calib_combo.clear()
        for calib_path in project.list_calib_files():
            self._calib_combo.addItem(calib_path.name, userData=calib_path)

        # Config.toml 로드:
        # - 표시(읽기): trial Config.toml이 있으면 그것, 없으면 project root 기본값
        # - 저장 대상: 항상 trial Config.toml (없으면 새로 생성)
        trial_cfg = trial.config_path()
        project_cfg = project.get_config_path()
        display_path = trial_cfg if trial_cfg.exists() else project_cfg
        self._config_panel.load_config(display_path, save_path=trial_cfg)

    def connect_runner(self, runner: PipelineRunner):
        """PipelineRunner Signal을 이 패널에 연결."""
        self._runner = runner
        runner.step_started.connect(self._on_step_started)
        runner.step_progress.connect(self._on_step_progress)
        runner.step_completed.connect(self._on_step_completed)
        runner.pipeline_done.connect(self._on_pipeline_done)

    # ── 내부 이벤트 ───────────────────────────────────────────────────

    def _on_run_step(self, step_name: str):
        if self._trial:
            self.step_run_requested.emit(step_name, self._trial.path)

    def _on_run_all(self):
        if self._trial:
            enabled_steps = [
                step for step, card in self._step_cards.items()
                if card.is_enabled()
            ]
            if not enabled_steps:
                return
            self._run_all_btn.setEnabled(False)
            self._stop_btn.setEnabled(True)
            self.run_all_requested.emit(self._trial.path, enabled_steps)

    def _on_step_started(self, step_name: str):
        if step_name in self._step_cards:
            self._step_cards[step_name].set_status(StepStatus.RUNNING)
            self._stop_btn.setEnabled(True)

    def _on_step_progress(self, step_name: str, percent: int):
        if step_name in self._step_cards:
            self._step_cards[step_name].set_progress(percent)

    def _on_step_completed(self, step_name: str, success: bool):
        if step_name in self._step_cards:
            status = StepStatus.SUCCESS if success else StepStatus.FAILED
            self._step_cards[step_name].set_status(status)

    def _on_pipeline_done(self, success: bool):
        self._run_all_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)

    def flush_config(self) -> None:
        """ConfigPanel의 현재 위젯 값을 즉시 디스크에 저장."""
        self._config_panel.save_config()

    def selected_calib_path(self) -> Path | None:
        """현재 드롭다운에서 선택된 Calib.toml 경로."""
        idx = self._calib_combo.currentIndex()
        if idx < 0:
            return None
        return self._calib_combo.itemData(idx)

    def set_active_calib(self, path: Path) -> None:
        """
        사이드바에서 선택된 Calib.toml을 드롭다운에서 자동 선택.
        목록에 없으면 맨 앞에 추가.
        """
        for i in range(self._calib_combo.count()):
            item_path: Path = self._calib_combo.itemData(i)
            if item_path == path:
                self._calib_combo.setCurrentIndex(i)
                return
        # 목록에 없으면 추가 후 선택
        self._calib_combo.insertItem(0, path.name, userData=path)
        self._calib_combo.setCurrentIndex(0)
