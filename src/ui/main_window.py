"""
메인 윈도우 — 전체 레이아웃 및 컨텍스트 전환 오케스트레이션
# Design Ref: §2.1 — QMainWindow, QSplitter(좌 사이드바 + 우 중앙/뷰어)
# Design Ref: §2.1 — QStackedWidget 중앙 패널: Calibration 선택↔Trial 선택 전환
"""
import re
from pathlib import Path

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QSplitter,
    QVBoxLayout, QHBoxLayout, QStackedWidget,
    QLabel, QFrame, QSizePolicy, QStatusBar, QAction,
)
from PyQt5.QtCore import Qt, pyqtSignal

from src.core.project import Project, Trial
from src.core.pipeline_runner import PipelineRunner
from src.ui.panels.project_panel import ProjectPanel
from src.ui.panels.pipeline_panel import PipelinePanel
from src.ui.panels.log_panel import LogPanel
from src.ui.panels.calib_sidebar import CalibSidebar
from src.ui.panels.calib_panel import CalibPanel
from src.ui.panels.trial_panel import TrialPanel
from src.ui.viewers.result_viewer import ResultViewerWidget


class _PlaceholderWidget(QWidget):
    """미구현 패널의 플레이스홀더."""
    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        lbl = QLabel(label)
        lbl.setStyleSheet("color: gray; font-size: 14px;")
        lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl)


class _WelcomeWidget(QWidget):
    """프로젝트 미선택 상태의 환영 화면."""
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(16)

        title = QLabel("Pose2SimUI")
        title.setObjectName("welcome_title")
        title.setAlignment(Qt.AlignCenter)

        sub = QLabel("왼쪽 패널에서 프로젝트를 열거나 생성하세요.")
        sub.setObjectName("welcome_sub")
        sub.setAlignment(Qt.AlignCenter)

        hint = QLabel("Ctrl+N  새 프로젝트   |   Ctrl+O  기존 프로젝트 열기")
        hint.setStyleSheet("color: #94A3B8; font-size: 11px;")
        hint.setAlignment(Qt.AlignCenter)

        layout.addWidget(title)
        layout.addWidget(sub)
        layout.addWidget(hint)


class MainWindow(QMainWindow):
    """
    앱 메인 윈도우.

    레이아웃:
    ┌────────────┬─────────────────────────────────────────┐
    │ Left       │ Center (QStackedWidget) + Right (Viewer) │
    │ Sidebar    │                                          │
    └────────────┴─────────────────────────────────────────┘

    중앙 패널 스택 인덱스:
      0: WelcomeWidget          — 프로젝트 미선택
      1: CalibPanel placeholder — Calibration 선택 (M6에서 구현)
      2: PipelinePanel placeholder — Trial 선택 (M5에서 구현)
    """

    # ── center_stack 인덱스 ──────────────────────────────────────────
    _IDX_WELCOME  = 0
    _IDX_CALIB    = 1
    _IDX_VIEWER   = 2   # ResultViewerWidget (Trial 선택 시)

    # ── right_stack 인덱스 ───────────────────────────────────────────
    _RIDX_EMPTY    = 0
    _RIDX_PIPELINE = 1
    _RIDX_CALIB_SETTINGS = 2

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pose2SimUI")
        self.resize(1280, 800)
        self.setMinimumSize(900, 600)

        self._current_project: Project | None = None
        self._active_calib_path: Path | None = None   # 사이드바에서 선택된 Calib.toml
        self._runner = PipelineRunner(self)
        self._setup_ui()
        self._setup_menu()
        self._setup_status_bar()
        self._connect_runner()

    # ────────────────────────────────────────────────────────────────
    # UI 구성
    # ────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── 최상위 수평 스플리터: 사이드바 | 중앙 | 오른쪽 패널 ────────
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setHandleWidth(1)
        root_layout.addWidget(main_splitter, 1)

        # 1. 왼쪽 사이드바 ─────────────────────────────────────────
        self._sidebar = self._build_sidebar()
        main_splitter.addWidget(self._sidebar)

        # 2. 중앙 패널 (QStackedWidget) ────────────────────────────
        # idx 0: Welcome
        # idx 1: CalibPanel (M6)
        # idx 2: ResultViewerWidget (Trial 선택 시)
        self._center_stack = QStackedWidget()
        self._center_stack.addWidget(_WelcomeWidget())          # idx 0

        self._calib_panel = CalibPanel()
        self._center_stack.addWidget(self._calib_panel)         # idx 1

        self._result_viewer = ResultViewerWidget()
        self._center_stack.addWidget(self._result_viewer)       # idx 2

        main_splitter.addWidget(self._center_stack)

        # 3. 오른쪽 패널 (QStackedWidget) ──────────────────────────
        # idx 0: 빈 위젯 (Welcome)
        # idx 1: PipelinePanel (Trial 선택 시)
        # idx 2: CalibSettingsPanel (Calibration 선택 시)
        self._right_stack = QStackedWidget()
        self._right_stack.addWidget(QWidget())                  # idx 0 empty

        self._pipeline_panel = PipelinePanel()
        self._right_stack.addWidget(self._pipeline_panel)       # idx 1

        # CalibSettingsPanel — CalibPanel 소유이지만 right_stack에 배치
        self._right_stack.addWidget(self._calib_panel.get_settings_panel())  # idx 2

        self._right_stack.setCurrentIndex(0)
        self._right_stack.setMaximumWidth(360)
        self._right_stack.setMinimumWidth(200)
        main_splitter.addWidget(self._right_stack)

        # ── LogPanel (하단 고정) ───────────────────────────────────
        self._log_panel = LogPanel()
        self._log_panel.setFixedHeight(140)
        root_layout.addWidget(self._log_panel)

        # 스플리터 비율: 사이드바 220 : 중앙 700 : 오른쪽 320
        main_splitter.setSizes([220, 700, 320])

        self._main_splitter = main_splitter

    def _build_sidebar(self) -> QWidget:
        """
        왼쪽 사이드바 구성:
          ProjectPanel
          CalibSidebar (M6 구현 완료)
          구분선
          TrialPanel  (M7에서 구현 — 현재는 플레이스홀더)
        # Design Ref: §2.1 — Calibration 섹션(위) + 구분선 + Trial List(아래)
        """
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setMinimumWidth(180)
        sidebar.setMaximumWidth(300)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Project Panel
        self._project_panel = ProjectPanel()
        self._project_panel.project_opened.connect(self._on_project_opened)
        layout.addWidget(self._project_panel)

        separator_top = self._make_separator()
        layout.addWidget(separator_top)

        # Calibration 사이드바 (M6)
        self._calib_sidebar = CalibSidebar()
        self._calib_sidebar.setMinimumHeight(40)
        self._calib_sidebar.setMaximumHeight(120)
        self._calib_sidebar.hide()   # 프로젝트 열기 전 숨김
        self._calib_sidebar.calib_selected.connect(self._on_calib_selected)
        self._calib_sidebar.new_calib_requested.connect(
            lambda: self.switch_to_calib_panel(None)
        )
        layout.addWidget(self._calib_sidebar)

        separator_mid = self._make_separator()
        separator_mid.hide()
        self._sidebar_separator = separator_mid
        layout.addWidget(separator_mid)

        # Trial 패널 (M7)
        self._trial_panel = TrialPanel()
        self._trial_panel.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        self._trial_panel.hide()   # 프로젝트 열기 전 숨김
        self._trial_panel.trial_selected.connect(self.switch_to_trial_panel)
        layout.addWidget(self._trial_panel)

        # 프로젝트 미선택 상태에서 남은 빈 공간을 아래로 밀어냄
        layout.addStretch()

        return sidebar

    def _make_separator(self) -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        return sep

    def _setup_menu(self):
        menubar = self.menuBar()

        # File 메뉴
        file_menu = menubar.addMenu("File")
        new_action = QAction("새 프로젝트", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self._project_panel._on_new_project)
        file_menu.addAction(new_action)

        open_action = QAction("프로젝트 열기", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._project_panel._on_open_project)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        quit_action = QAction("종료", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # Help 메뉴
        help_menu = menubar.addMenu("Help")
        about_action = QAction("Pose2SimUI 정보", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_status_bar(self):
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("준비")

    # ────────────────────────────────────────────────────────────────
    # 이벤트 핸들러 / 컨텍스트 전환
    # ────────────────────────────────────────────────────────────────

    def _on_project_opened(self, project: Project):
        """
        프로젝트 열기/생성 시 호출.
        사이드바 Calibration + Trial 섹션 표시, 중앙 패널 초기화.
        """
        self._current_project = project
        self._status_bar.showMessage(f"프로젝트: {project.name}  |  {project.root_path}")

        # 사이드바 섹션 표시
        self._calib_sidebar.set_project(project.root_path)
        self._calib_panel.set_project(project.root_path)
        self._calib_panel.calib_saved.connect(self._calib_sidebar.refresh_list)
        self._calib_sidebar.show()
        self._sidebar_separator.show()
        self._trial_panel.set_project(project)
        self._trial_panel.show()

        # 중앙 패널: WelcomeWidget → 유지 (Trial/Calib 선택 전까지)
        self._center_stack.setCurrentIndex(self._IDX_WELCOME)
        self._right_stack.setCurrentIndex(self._RIDX_EMPTY)

    def switch_to_calib_panel(self, calib_path: Path | None = None):
        """
        Calibration 사이드바 항목 클릭 시 중앙 패널을 CalibPanel로 전환.
        # Design Ref: §2.1 — (A) Calibration 선택 시: CalibPanel 표시
        calib_path=None이면 새 캘리브 모드.
        """
        self._calib_panel.load_calib(calib_path)
        self._center_stack.setCurrentIndex(self._IDX_CALIB)
        self._right_stack.setCurrentIndex(self._RIDX_CALIB_SETTINGS)
        if self._current_project:
            self._status_bar.showMessage(
                f"Calibration  |  {self._current_project.name}"
                + (f"  |  {calib_path.name}" if calib_path else "  |  새 캘리브")
            )

    def _connect_runner(self):
        """
        PipelineRunner Signal → LogPanel + PipelinePanel 연결.
        # Design Ref: §3.2 — Signal 흐름: runner → log_panel, pipeline_panel
        """
        self._runner.log_line.connect(self._log_panel.append_log)
        self._pipeline_panel.connect_runner(self._runner)
        self._pipeline_panel.step_run_requested.connect(self._on_step_run_requested)
        self._pipeline_panel.run_all_requested.connect(self._on_run_all_requested)
        self._pipeline_panel.cancel_requested.connect(self._runner.cancel)

        # 파이프라인 로그 → trial/logs/pipeline.log 파일 저장
        self._trial_log_path: Path | None = None
        self._runner.log_line.connect(self._write_pipeline_log)

        # Calibration Run Intrinsic / Run Extrinsic 버튼 연결
        self._calib_panel.run_requested.connect(self._on_calib_run_requested)

        # 캘리브레이션 완료 시 결과 팝업
        self._runner.step_completed.connect(self._on_calib_step_completed)
        self._calib_log_lines: list[str] = []
        self._collecting_calib_log = False
        self._runner.log_line.connect(self._collect_calib_log)
        self._runner.step_started.connect(
            lambda s: self._start_calib_log_collect() if s in ("intrinsic", "extrinsic") else None
        )

    def _start_calib_log_collect(self):
        self._calib_log_lines.clear()
        self._collecting_calib_log = True

    def _collect_calib_log(self, line: str):
        """캘리브레이션 실행 중 로그를 팝업 표시용으로 수집."""
        if self._collecting_calib_log:
            self._calib_log_lines.append(line)

    def _on_calib_step_completed(self, step: str, success: bool):
        """intrinsic/extrinsic 완료 시 결과 팝업 표시."""
        self._collecting_calib_log = False
        if step not in ("intrinsic", "extrinsic"):
            return
        log_lines = list(self._calib_log_lines)
        self._calib_log_lines.clear()
        if success:
            text = self._format_calib_result(log_lines, step)
            self._calib_panel.get_settings_panel().show_result(step, text)
            # Calib.toml 생성 후 사이드바 자동 갱신
            self._calib_sidebar.refresh_list()

    @staticmethod
    def _format_calib_result(log_lines: list[str], step: str) -> str:
        """
        캘리브레이션 로그에서 핵심 수치만 추출해 깔끔한 표로 포맷.
        보여줄 정보: 카메라별 RMS, 평균, 저장 경로, 소요 시간.
        """
        cam_errors: dict[str, float] = {}
        current_cam: str | None = None
        rms_px: list[float] = []
        rms_mm: list[float] = []
        duration = ""
        saved_path = ""

        def _extract_floats(bracket_content: str) -> list[float]:
            """np.float32(8.76) 또는 순수 숫자 형태 모두 처리."""
            nums = re.findall(r"np\.float\d+\(([\d.]+)\)", bracket_content)
            if not nums:
                nums = re.findall(r"([\d]+\.[\d]+|[\d]+)", bracket_content)
            return [float(x) for x in nums]

        for raw in log_lines:
            line = raw.strip()

            # 카메라 이름 추출: "Camera cam01:"
            m = re.match(r"Camera (cam\d+):", line)
            if m:
                current_cam = m.group(1)
                continue

            # Intrinsic 개별 오류: "Intrinsics error: 0.326 px for each cameras."
            m = re.search(r"Intrinsics error:\s*([\d.]+)\s*px", line)
            if m and current_cam:
                cam_errors[current_cam] = float(m.group(1))
                continue

            # Extrinsic 단일 행: "Camera cam01 reprojection error: 5.243 px"
            m = re.search(r"Camera (cam\d+)[^:]*[Rr]eprojection error.*?([\d.]+)\s*px", line)
            if m:
                cam_errors[m.group(1)] = float(m.group(2))
                continue

            # Extrinsic 개별 오류 (multi-line): reprojection 값만 있는 행 (current_cam 선설정)
            m = re.search(r"[Rr]eprojection error.*?([\d.]+)\s*px", line)
            if m and current_cam:
                cam_errors[current_cam] = float(m.group(1))
                continue

            # RMS 요약 (1행): "--> Residual (RMS) ... [np.float32(8.76), ...] px"
            # 같은 행에 mm 값이 있으면 함께 추출; 없으면 다음 행에서 처리.
            m = re.search(r"Residual \(RMS\).*?\[([^\]]+)\]\s*px(?:.*?\[([^\]]+)\]\s*mm)?", line)
            if m:
                rms_px = _extract_floats(m.group(1))
                rms_mm = _extract_floats(m.group(2)) if m.group(2) else []
                continue

            # RMS 단위 보충 (2행): "which corresponds to [np.float64(11.22), ...] mm."
            # Pose2Sim이 px 행과 mm 행을 별도 줄로 출력하는 경우 처리.
            m = re.search(r"which corresponds to.*?\[([^\]]+)\]\s*mm", line)
            if m and rms_px and not rms_mm:
                rms_mm = _extract_floats(m.group(1))
                continue

            # 소요 시간
            m = re.search(r"Calibration took ([\d.]+)\s*seconds", line)
            if m:
                duration = m.group(1)
                continue

            # 저장 경로
            m = re.search(r"Calibration file is stored at\s+(.+)", line)
            if m:
                saved_path = m.group(1).strip()

        # ── 포맷 ────────────────────────────────────────────────────────
        label = "Intrinsic" if step == "intrinsic" else "Extrinsic"
        dur_str = f"  ({duration}s)" if duration else ""
        out = [f"{label} Calibration 완료{dur_str}\n"]

        # 오류 값 결정: 개별 파싱 우선, 없으면 RMS 요약 사용
        # mm 값: RMS 요약 행의 rms_mm 리스트를 카메라 순서 기준으로 매핑.
        #   cam_errors 경우: sorted 키 순서 == Pose2Sim 처리 순서 → rms_mm 인덱스와 일치
        #   rms_px 경우: 인덱스 그대로 매핑
        errors_px: dict[str, float] = {}
        errors_mm: dict[str, float] = {}
        if cam_errors:
            errors_px = dict(sorted(cam_errors.items()))
            # rms_mm이 있고 카메라 수가 맞으면 순서대로 매핑
            if rms_mm and len(rms_mm) == len(errors_px):
                errors_mm = {cam: rms_mm[i] for i, cam in enumerate(errors_px)}
        elif rms_px:
            errors_px = {f"cam{i+1:02d}": v for i, v in enumerate(rms_px)}
            errors_mm = {f"cam{i+1:02d}": v for i, v in enumerate(rms_mm)}

        if errors_px:
            col_w = max(len(k) for k in errors_px) + 2
            has_mm = bool(errors_mm)
            hdr = f"  {'Camera':<{col_w}}  {'RMS (px)':<12}" + ("  RMS (mm)" if has_mm else "")
            sep = "  " + "─" * (col_w + (26 if has_mm else 14))
            out.append(hdr)
            out.append(sep)
            for cam, px in errors_px.items():
                mm_str = f"  {errors_mm[cam]:.3f} mm" if (has_mm and cam in errors_mm) else ""
                out.append(f"  {cam:<{col_w}}  {px:<12.3f}{mm_str}")
            if len(errors_px) > 1:
                mean_px = sum(errors_px.values()) / len(errors_px)
                out.append(sep)
                if has_mm:
                    mean_mm = sum(errors_mm.values()) / len(errors_mm)
                    out.append(f"  {'Mean':<{col_w}}  {mean_px:<12.3f}  {mean_mm:.3f} mm")
                else:
                    out.append(f"  {'Mean':<{col_w}}  {mean_px:.3f} px")

        if saved_path:
            fname = Path(saved_path).name
            out.append(f"\n  저장됨  →  {fname}")

        return "\n".join(out)

    def _on_calib_run_requested(self, step: str, params: dict):
        """
        CalibPanel의 Run Intrinsic / Run Extrinsic 버튼 처리.
        캘리브레이션 폴더를 working_dir로 사용해 PipelineRunner에 위임.
        """
        if self._current_project is None:
            self._log_panel.append_log("[ERROR] 프로젝트가 열려 있지 않습니다.")
            return

        if self._runner.is_running():
            self._log_panel.append_log("[WARN] 이미 실행 중입니다. 완료 후 재시도하세요.")
            return

        project_root = self._current_project.root_path
        calib_dir = project_root / "calibration"
        label = {"intrinsic": "Intrinsic", "extrinsic": "Extrinsic"}.get(step, step)
        cam_count = len(params.get("cam_files", {}))
        self._log_panel.append_log(
            f"[INFO] {label} 캘리브레이션 시작  |  카메라 {cam_count}개  |  폴더: {calib_dir}"
        )
        self._begin_pipeline_log(project_root, f"Calibration {label}")
        self._runner.run_calib_step(step, params, project_root)

    def _on_step_run_requested(self, step_name: str, trial_path: Path):
        """
        PipelinePanel 단계 실행 버튼 처리.
        Config.toml이 없으면 자동 생성 후 runner에 위임.
        """
        if self._current_project is None:
            return
        self._pipeline_panel.flush_config()
        calib_path = self._pipeline_panel.selected_calib_path()
        self._ensure_trial_config(trial_path, calib_path)
        self._begin_pipeline_log(trial_path, step_name)
        self._runner.run_step(step_name, trial_path)

    def _on_run_all_requested(self, trial_path: Path, enabled_steps: list):
        """
        PipelinePanel 전체 실행 버튼 처리.
        체크박스로 선택된 스텝만 실행한다.
        """
        if self._current_project is None:
            return
        self._pipeline_panel.flush_config()
        calib_path = self._pipeline_panel.selected_calib_path()
        self._ensure_trial_config(trial_path, calib_path)
        self._begin_pipeline_log(trial_path, "run_all")
        self._runner.run_all(trial_path, steps=enabled_steps)

    def _begin_pipeline_log(self, working_dir: Path, label: str) -> None:
        """project_root/project.log 에 모든 세션 로그를 누적 기록.
        Trial별 분산 대신 프로젝트 단위 단일 파일로 통합.
        """
        import datetime
        project_root = (
            self._current_project.root_path
            if self._current_project is not None
            else working_dir
        )
        self._trial_log_path = project_root / "project.log"
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._trial_log_path.open("a", encoding="utf-8") as f:
            f.write(f"\n=== {label}  [{ts}] ===\n")

    def _write_pipeline_log(self, line: str) -> None:
        """log_line 신호 수신 시 trial 로그 파일에 추가 기록."""
        if self._trial_log_path is None:
            return
        try:
            with self._trial_log_path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass

    def _ensure_trial_config(self, trial_path: Path, calib_path: Path | None) -> None:
        """
        실행 전 trial Config.toml의 project_dir / calib 경로를 조용히 갱신.
        - trial Config.toml이 없으면 아무것도 하지 않음 (자동 생성 금지).
          사용자가 Config 탭에서 저장해야 trial Config.toml이 생성됨.
        - 존재하는 경우에만 project_dir·calib 경로를 업데이트하고 저장.
        """
        from src.core.config_manager import ConfigManager
        config_path = trial_path / "Config.toml"
        if not config_path.exists():
            return  # 자동 생성 하지 않음

        cm = ConfigManager()
        config = cm.load_or_default(config_path)

        config.setdefault("project", {})["project_dir"] = str(trial_path)

        # synchronization 호환 키
        sync = config.get("synchronization", {})
        if "likelihood_threshold_synchronization" in sync:
            sync["likelihood_threshold"] = sync["likelihood_threshold_synchronization"]

        # 선택된 Calib.toml 반영
        if calib_path and calib_path.exists():
            calib_str = str(calib_path)
            config.setdefault("calibration", {})
            config["calibration"]["calibration_type"] = "load"
            config["calibration"].setdefault("load", {})
            config["calibration"]["load"].setdefault("file", {})
            config["calibration"]["load"]["file"]["intrinsics_file"] = calib_str
            config["calibration"]["load"]["file"]["extrinsics_file"] = calib_str

        cm.save(config, config_path)

    def _on_calib_selected(self, calib_path: Path):
        """
        CalibSidebar에서 기존 Calib.toml 클릭 시 — 분석에 적용, 패널 전환 없음.
        PipelinePanel 드롭다운을 동기화하고 활성 Trial Config.toml도 갱신한다.
        """
        self._active_calib_path = calib_path
        # PipelinePanel 드롭다운 동기화 (Trial 패널이 열려 있을 때만 유효)
        self._pipeline_panel.set_active_calib(calib_path)
        # 활성 Trial의 Config.toml에 선택된 calib 경로 반영
        if self._current_project and self._current_project.active_trial:
            self._ensure_trial_config(
                self._current_project.active_trial.path, calib_path
            )
        # 상태바에 선택된 calib 파일명 표시
        if self._current_project:
            self._status_bar.showMessage(
                f"프로젝트: {self._current_project.name}"
                f"  |  캘리브: {calib_path.name}"
            )

    def switch_to_trial_panel(self, trial: Trial):
        """
        Trial 클릭 시 중앙 패널을 PipelinePanel로 전환하고 뷰어를 표시.
        # Design Ref: §2.1 — (B) Trial 선택 시: Pipeline/Config 탭 + 뷰어
        # Plan SC: SC-07 — Trial 전환 시 독립 설정 로드
        """
        if self._current_project is None:
            return
        # Calibration 페이지를 벗어나면 미디어 그리드 초기화
        self._calib_panel.clear_media()
        self._current_project.active_trial = trial
        self._pipeline_panel.load_trial(trial, self._current_project)
        # 사이드바에서 이미 calib을 선택했으면 드롭다운에 적용
        if self._active_calib_path:
            self._pipeline_panel.set_active_calib(self._active_calib_path)
        self._result_viewer.load_trial(trial)
        self._center_stack.setCurrentIndex(self._IDX_VIEWER)
        self._right_stack.setCurrentIndex(self._RIDX_PIPELINE)
        self._status_bar.showMessage(
            f"Trial: {trial.name}  |  {self._current_project.name}"
        )

    def closeEvent(self, event):
        """
        앱 종료 시 백그라운드 워커와 QMediaPlayer를 안전하게 정리.
        정리 없이 종료하면 SIGTRAP(Trace/BPT trap: 5) 크래시가 발생할 수 있음.
        """
        # 실행 중인 파이프라인 취소
        if self._runner.is_running():
            self._runner.cancel()
        # 모든 QMediaPlayer 소스 해제 (Qt multimedia 내부 디코더 정리)
        if hasattr(self, '_result_viewer'):
            video_player = getattr(self._result_viewer, 'video_player', None)
            if video_player is not None:
                video_player.stop_all_players()
        event.accept()

    def _show_about(self):
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.about(
            self, "Pose2SimUI 정보",
            "<b>Pose2SimUI v0.1.0</b><br><br>"
            "Pose2Sim 바이오메카닉스 파이프라인을 위한 GUI 앱.<br>"
            "PyQt5 기반, 크로스플랫폼 (macOS / Windows).",
        )
