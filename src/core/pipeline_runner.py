"""
Pose2Sim API 호출 오케스트레이터
# Design Ref: §5.1 — PipelineRunner: STEP_ORDER, POSE2SIM_API, run_step(), cancel()
# Design Ref: §3.1 — Signals: step_started, step_progress, step_completed, log_line, pipeline_done
# Plan SC: SC-04 — 파이프라인 각 단계 개별 실행
# Plan SC: SC-05 — UI 블로킹 없음 (Worker → Signal)
"""
import re
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

from src.core.workers.pipeline_worker import PipelineWorker, SubprocessPipelineWorker


class PipelineRunner(QObject):
    """
    파이프라인 단계 실행 오케스트레이터.

    Pose2Sim API를 직접 호출하지 않고 PipelineWorker(QThread)를 생성해 위임.
    UI 레이어는 이 객체의 Signal만 구독한다.

    Signals:
        step_started(str):         step_name
        step_progress(str, int):   step_name, percent (0~100)
        step_completed(str, bool): step_name, success
        log_line(str):             로그 한 줄
        pipeline_done(bool):       전체 완료 여부
    """

    step_started   = pyqtSignal(str)
    step_progress  = pyqtSignal(str, int)
    step_completed = pyqtSignal(str, bool)
    log_line       = pyqtSignal(str)
    pipeline_done  = pyqtSignal(bool)

    # ── Pose2Sim 파이프라인 단계 정의 ────────────────────────────────
    # Design Ref: §5.1 — STEP_ORDER (Calibration 제외: 사이드바에서 별도 관리)
    STEP_ORDER = [
        "pose_estimation",
        "synchronization",
        "person_association",
        "triangulation",
        "filtering",
        "marker_augmentation",
        "kinematics",
    ]

    STEP_LABELS = {
        "pose_estimation":    "Pose Estimation",
        "synchronization":    "Synchronization",
        "person_association": "Person Association",
        "triangulation":      "Triangulation",
        "filtering":          "Filtering",
        "marker_augmentation": "Marker Augmentation",
        "kinematics":         "Kinematics",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active_worker: PipelineWorker | None = None
        self._run_all_queue: list[str] = []
        self._run_all_success = True
        self._in_run_all = False

    def _get_pose2sim_api(self) -> dict:
        """
        Pose2Sim API 함수 매핑을 런타임에 임포트.
        Pose2Sim이 설치되지 않은 환경에서도 앱이 시작되도록 지연 임포트.
        실제 API: from Pose2Sim import Pose2Sim as P2S
        """
        try:
            from Pose2Sim import Pose2Sim as P2S
            return {
                "calibration":         P2S.calibration,
                "pose_estimation":     P2S.poseEstimation,
                "synchronization":     P2S.synchronization,
                "person_association":  P2S.personAssociation,
                "triangulation":       P2S.triangulation,
                "filtering":           P2S.filtering,
                "marker_augmentation": P2S.markerAugmentation,
                "kinematics":          P2S.kinematics,
            }
        except Exception as e:
            self.log_line.emit(f"[WARN] Pose2Sim 로드 실패: {e}")
            return {}

    def run_step(self, step_name: str, working_dir: Path):
        """
        단일 파이프라인 단계 실행.
        이미 실행 중이면 무시.
        """
        if self._active_worker and self._active_worker.isRunning():
            self.log_line.emit(f"[WARN] 이미 실행 중입니다: {self._active_worker_step}")
            return

        api_map = self._get_pose2sim_api()
        if step_name not in api_map:
            self.log_line.emit(f"[ERROR] 알 수 없는 단계: {step_name}")
            return

        self._active_worker_step = step_name
        worker = SubprocessPipelineWorker(
            step_name=self.STEP_LABELS.get(step_name, step_name),
            step_key=step_name,
            working_dir=working_dir,
        )
        worker.log_line.connect(self.log_line)
        worker.progress.connect(lambda p: self.step_progress.emit(step_name, p))
        worker.finished.connect(lambda ok, _: self._on_step_finished(step_name, ok))

        self._active_worker = worker
        self.step_started.emit(step_name)
        worker.start()

    def run_all(self, working_dir: Path, steps: list[str] | None = None):
        """
        여러 단계를 순서대로 실행 (완료 Signal을 받아 다음 단계 진행).
        steps=None이면 STEP_ORDER 전체.
        """
        self._run_all_queue = list(steps or self.STEP_ORDER)
        self._run_all_success = True
        self._in_run_all = True
        self._run_all_dir = working_dir
        self._advance_queue()

    def _advance_queue(self):
        if not self._run_all_queue:
            self.pipeline_done.emit(self._run_all_success)
            return
        next_step = self._run_all_queue.pop(0)
        # run_step 완료 후 _advance_queue가 다시 호출됨
        self.run_step(next_step, self._run_all_dir)

    def _on_step_finished(self, step_name: str, success: bool):
        self.step_completed.emit(step_name, success)
        if not success:
            self._run_all_success = False
            self._run_all_queue.clear()
        if self._run_all_queue:
            self._advance_queue()
        elif self._in_run_all:
            # run_all 컨텍스트: 마지막 단계 완료(성공·실패 모두) → pipeline_done emit
            self._in_run_all = False
            self.pipeline_done.emit(self._run_all_success)

    def run_calib_step(self, step: str, params: dict, project_root: Path):
        """
        Calibration 전용 실행 메서드.
        Config.toml 없이 params dict를 P2S.calibration(config_dict)에 직접 전달.
        # Design Ref: §8.2 — CalibPanel Run Intrinsic / Extrinsic
        """
        if self._active_worker and self._active_worker.isRunning():
            self.log_line.emit("[WARN] 이미 실행 중입니다.")
            return

        try:
            from Pose2Sim import Pose2Sim as P2S
        except Exception as e:
            self.log_line.emit(f"[WARN] Pose2Sim 로드 실패: {e}")
            return

        # Pose2Sim은 calibration/{intrinsics|extrinsics}/{cam_name}/*.mp4 구조를 요구.
        # 파일이 flat하게 있으면 per-camera 하위 폴더를 만들고 심볼릭 링크로 연결.
        calib_dir = project_root / "calibration"
        if step == "intrinsic":
            self._ensure_cam_subdirs(calib_dir / "intrinsics", params.get("cam_files", {}))
            # macOS .DS_Store 등 메타데이터 파일 제거 (Pose2Sim이 파일 수로 카메라 수 계산)
            self._remove_macos_metadata(calib_dir / "intrinsics")
        else:
            cam_files = params.get("cam_files", {})
            # Extrinsic 실행 전 카메라 수 일관성 검사
            mismatch = self._check_cam_count_mismatch(cam_files, calib_dir)
            if mismatch:
                self.log_line.emit(f"[ERROR] {mismatch}")
                return
            self._ensure_cam_subdirs(calib_dir / "extrinsics", cam_files)
            # macOS .DS_Store 등 메타데이터 파일 제거 (Pose2Sim이 파일 수로 카메라 수 계산)
            self._remove_macos_metadata(calib_dir / "extrinsics")

        config_dict = self._build_calib_config(step, params, project_root)

        # Scene 캘리브레이션: Qt 다이얼로그로 수집한 2D 좌표를 matplotlib.ginput 모킹으로 주입.
        # Extrinsic 캘리브레이션 GUI 패치:
        #  1) Image_points.json 삭제 — 이전 레이블이 있으면 Pose2Sim이 tkinter 다이얼로그를
        #     Worker Thread에서 호출하므로 macOS ARM64에서 강제 종료됨.
        #  2) matplotlib / tkinter 패치 — plt.gcf/show/subplots, tk.messagebox 를
        #     모두 Worker Thread에서 안전하게 억제.
        image_coords_2d = params.get("image_coords_2d")
        restore_fn = None
        if step == "extrinsic":
            img_pts = calib_dir / "Image_points.json"
            if img_pts.exists():
                try:
                    img_pts.unlink()
                    self.log_line.emit("[INFO] 이전 Image_points.json 제거 (tkinter 다이얼로그 방지)")
                except Exception:
                    pass
            restore_fn = self._patch_extrinsic_gui(image_coords_2d)

        api_fn = lambda cfg=config_dict: P2S.calibration(cfg)

        label = "Intrinsic 캘리브레이션" if step == "intrinsic" else "Extrinsic 캘리브레이션"
        self._active_worker_step = step

        debug_dir = calib_dir / ("intrinsics" if step == "intrinsic" else "extrinsics")
        self.log_line.emit(
            f"[INFO] 팝업 대신 디버그 이미지를 저장합니다 → {debug_dir}"
        )

        worker = PipelineWorker(label, api_fn, project_root)
        worker.log_line.connect(self.log_line)
        worker.progress.connect(lambda p: self.step_progress.emit(step, p))

        def _on_finished(ok, _msg, _rf=restore_fn):
            if _rf is not None:
                _rf()  # matplotlib 패치 복원
            self._on_step_finished(step, ok)

        worker.finished.connect(_on_finished)

        self._active_worker = worker
        self.step_started.emit(step)
        worker.start()

    @staticmethod
    def _patch_extrinsic_gui(image_coords_2d: dict | None):
        """
        Extrinsic 캘리브레이션 실행 전 GUI 관련 라이브러리를 Worker Thread 안전하게 패치.

        macOS ARM64에서 QThread 내 GUI 호출은 강제 종료를 유발하므로 전부 억제:
          - matplotlib: plt.show / plt.gcf / plt.subplots / plt.figure / plt.close /
                        plt.draw / plt.get_current_fig_manager → Stub 또는 no-op
          - tkinter: messagebox.askyesno → True 고정
                     (Image_points.json 존재 시 Pose2Sim이 호출하는 "satisfied?" 다이얼로그)

        image_coords_2d 가 None 이 아닌 경우(scene 방식):
          → imgp_objp_visualizer_clicker 도 Qt 수집 좌표 반환 Mock으로 교체.

        반환값: restore 함수 (worker.finished 신호 수신 후 메인 스레드에서 호출).
        # Design Ref: §8.2 — Extrinsic GUI macOS 스레드 제약 우회
        """
        try:
            import matplotlib
            import matplotlib.pyplot as plt

            original_backend = matplotlib.get_backend()
            original_show    = plt.show
            original_ginput  = plt.ginput
            original_gcf     = plt.gcf
            original_figure  = plt.figure
            original_close   = plt.close
            original_draw    = plt.draw
            original_gcfm    = plt.get_current_fig_manager

            # Agg: 비대화형 백엔드 — GUI 창 없음
            try:
                matplotlib.use("Agg")
            except Exception:
                pass

            # ── matplotlib stub ───────────────────────────────────────
            class _StubWindow:
                def showMaximized(self, *a, **k): pass
                def show(self, *a, **k): pass

            class _StubManager:
                window = _StubWindow()
                def set_window_title(self, *a, **k): pass
                def show(self, *a, **k): pass

            class _StubCanvas:
                manager = _StubManager()
                def draw(self, *a, **k): pass
                def mpl_connect(self, *a, **k): return 0
                def mpl_disconnect(self, *a, **k): pass

            class _StubAxes:
                def imshow(self, *a, **k): pass
                def axis(self, *a, **k): pass

            class _StubFigure:
                canvas = _StubCanvas()
                number = 999
                def show(self, *a, **k): pass
                def tight_layout(self, *a, **k): pass
                def savefig(self, *a, **k): pass
                def add_subplot(self, *a, **k): return _StubAxes()
                def subplots_adjust(self, *a, **k): pass

            _stub_fig = _StubFigure()
            _stub_axes = _StubAxes()

            plt.show   = lambda *a, **k: None
            plt.ginput = lambda *a, **k: []
            plt.gcf    = lambda: _stub_fig
            plt.figure = lambda *a, **k: _stub_fig
            plt.close  = lambda *a, **k: None
            plt.draw   = lambda *a, **k: None
            plt.get_current_fig_manager = lambda: _StubManager()

            # plt.subplots 도 패치 — checkerboard findCorners 내 호출 대비
            original_subplots = getattr(plt, "subplots", None)
            plt.subplots = lambda *a, **k: (_stub_fig, _stub_axes)

            # ── tkinter messagebox 패치 ───────────────────────────────
            # Pose2Sim이 Image_points.json 존재 시 "이전 레이블에 만족하시나요?" 를 물음.
            # Worker Thread에서 tk.Tk() → NSWindow crash.
            original_tk_askyesno = None
            try:
                import tkinter.messagebox as _tkbox
                original_tk_askyesno = _tkbox.askyesno
                _tkbox.askyesno = lambda *a, **k: True   # 항상 "예" — 이전 레이블 재사용
            except Exception:
                pass

            # ── scene 방식: imgp_objp_visualizer_clicker 교체 ─────────
            original_clicker = None
            if image_coords_2d:
                sorted_cams = sorted(image_coords_2d.keys())
                cam_coords_list = [image_coords_2d[c] for c in sorted_cams]
                cam_coords_iter = iter(cam_coords_list)

                try:
                    import numpy as _np
                    import Pose2Sim.calibration as _p2s_calib
                    original_clicker = _p2s_calib.imgp_objp_visualizer_clicker

                    def _mock_clicker(img, imgp=None, objp=None, img_path=None):
                        try:
                            pts_2d = next(cam_coords_iter)
                            imgp_result = _np.array(
                                [[float(p[0]), float(p[1])] for p in pts_2d],
                                dtype=_np.float32,
                            )
                        except StopIteration:
                            imgp_result = imgp if imgp is not None else _np.zeros((0, 2), dtype=_np.float32)
                        return imgp_result, objp

                    _p2s_calib.imgp_objp_visualizer_clicker = _mock_clicker
                except Exception:
                    pass

            def restore():
                try:
                    plt.show   = original_show
                    plt.ginput = original_ginput
                    plt.gcf    = original_gcf
                    plt.figure = original_figure
                    plt.close  = original_close
                    plt.draw   = original_draw
                    plt.get_current_fig_manager = original_gcfm
                    if original_subplots is not None:
                        plt.subplots = original_subplots
                    # 백엔드 복원은 skipped — matplotlib.use() 재호출이 일부 환경에서 불안정
                except Exception:
                    pass
                try:
                    if original_tk_askyesno is not None:
                        import tkinter.messagebox as _tkbox
                        _tkbox.askyesno = original_tk_askyesno
                except Exception:
                    pass
                try:
                    if original_clicker is not None:
                        import Pose2Sim.calibration as _p2s_calib
                        _p2s_calib.imgp_objp_visualizer_clicker = original_clicker
                except Exception:
                    pass

            return restore
        except ImportError:
            return None

    def _ensure_cam_subdirs(self, base_dir: Path, cam_files: dict) -> None:
        """
        Pose2Sim은 calibration/{intrinsics|extrinsics}/{cam_name}/*.ext 구조를 요구.
        파일이 base_dir 바로 아래 flat하게 있으면 per-camera 하위 폴더를 만들고
        해당 파일의 심볼릭 링크를 생성한다 (원본 파일 이동 없음).

        cam_files: {"cam01": "/abs/path/to/file.mp4", ...}  (get_cam_files() 반환 형식)
        # Design Ref: §8.2 — Pose2Sim folder convention
        """
        import shutil as _shutil
        if not base_dir.exists():
            base_dir.mkdir(parents=True, exist_ok=True)

        valid_cams = {k for k, v in cam_files.items() if v}

        # 현재 cam_files에 없는 스테일 하위 폴더 제거 (카메라 수 불일치 방지)
        if base_dir.exists():
            for child in list(base_dir.iterdir()):
                if child.is_dir() and child.name not in valid_cams:
                    _shutil.rmtree(child, ignore_errors=True)
                    self.log_line.emit(f"[INFO] 스테일 폴더 제거: {child.name}")

        for cam_name, file_path in cam_files.items():
            if not file_path:
                continue
            fp = Path(file_path)
            if not fp.exists():
                self.log_line.emit(f"[WARN] 파일 없음: {fp}")
                continue
            cam_subdir = base_dir / cam_name
            cam_subdir.mkdir(exist_ok=True)
            link = cam_subdir / fp.name
            if link.exists() or link.is_symlink():
                continue  # 이미 있음
            try:
                link.symlink_to(fp.resolve())
                self.log_line.emit(f"[INFO] 링크 생성: {cam_name}/{fp.name}")
            except Exception:
                # 심볼릭 링크 실패 시(Windows 권한 등) 파일 복사
                _shutil.copy2(fp, link)
                self.log_line.emit(f"[INFO] 파일 복사: {cam_name}/{fp.name}")

    def _check_cam_count_mismatch(self, extr_cam_files: dict, calib_dir: Path) -> str | None:
        """
        Extrinsic 실행 전 카메라 수 일관성 검사.
        기존 Calib*.toml 또는 intrinsics/ 서브폴더의 카메라 수와 비교.
        불일치 시 한국어 설명 반환, 일치하면 None.
        # Design Ref: §8.2 — 카메라 수 일관성 검사
        """
        n_extr = sum(1 for v in extr_cam_files.values() if v)
        if n_extr == 0:
            return None

        # 1. Calib*.toml 파일에서 카메라 수 확인 (intrinsic 결과 파일)
        calib_file = next(calib_dir.glob("Calib*.toml"), None)
        if calib_file:
            try:
                import tomllib
                with open(calib_file, "rb") as fp:
                    data = tomllib.load(fp)
                cam_keys = [k for k in data if re.match(r"cam\d+", k, re.IGNORECASE)]
                n_calib = len(cam_keys)
                if n_calib > 0 and n_extr != n_calib:
                    return (
                        f"카메라 수 불일치: Extrinsic 파일 {n_extr}대, "
                        f"기존 캘리브레이션 파일({calib_file.name}) {n_calib}대.\n"
                        f"해결 방법: Intrinsic 캘리브레이션을 {n_extr}대로 다시 실행하거나, "
                        f"Extrinsic 파일을 {n_calib}대로 맞추세요."
                    )
            except Exception:
                pass

        # 2. intrinsics/ 서브폴더 수로 확인
        intrinsic_dir = calib_dir / "intrinsics"
        if intrinsic_dir.exists():
            n_intr = sum(1 for d in intrinsic_dir.iterdir() if d.is_dir())
            if n_intr > 0 and n_extr != n_intr:
                return (
                    f"카메라 수 불일치: Extrinsic 파일 {n_extr}대, "
                    f"Intrinsic 폴더 {n_intr}대.\n"
                    f"해결 방법: Intrinsic 캘리브레이션을 {n_extr}대로 다시 실행하거나, "
                    f"Extrinsic 파일을 {n_intr}대로 맞추세요."
                )

        return None

    @staticmethod
    def _remove_macos_metadata(directory: Path) -> None:
        """
        Pose2Sim은 `max(len(subdirs), len(files))`로 카메라 수를 계산하므로
        macOS가 자동 생성하는 .DS_Store / ._* 파일이 카메라 수를 오염시킨다.
        캘리브레이션 실행 전 해당 디렉토리(와 하위 cam 폴더)의 메타데이터 파일을 제거.
        # Design Ref: §8.2 — macOS .DS_Store 카운팅 오류 우회
        """
        _meta_patterns = (".DS_Store", "._")
        if not directory.exists():
            return
        for p in directory.rglob("*"):
            if not p.is_file():
                continue
            if any(p.name.startswith(pat) for pat in _meta_patterns):
                try:
                    p.unlink()
                except Exception:
                    pass

    def _build_calib_config(self, step: str, params: dict, project_root: Path) -> dict:
        """
        UI 파라미터 → Pose2Sim calibration config dict 변환.
        dict로 넘기면 Pose2Sim이 Config.toml 파일을 탐색하지 않음.
        """
        cam_files: dict = params.get("cam_files", {})

        # 첫 번째 파일에서 확장자 추론 (cam_files 값은 파일 경로 문자열)
        ext = "mp4"
        for file_path in cam_files.values():
            if file_path:
                ext = str(file_path).rsplit(".", 1)[-1].lower()
                break

        # project_dir: Pose2Sim.py의 경고 방지용 (read_config_files에서 확인)
        # session_dir: calibration.py에서 calib 폴더 탐색에 사용
        # show_detection_intrinsics / show_reprojection_error: False
        #   → Pose2Sim이 matplotlib GUI 창을 백그라운드 스레드에서 열려 하면
        #     macOS에서 NSWindow 크래시 발생. GUI는 메인 스레드 전용이므로 비활성화.
        #     대신 save_debug_images=True 로 이미지 파일로 저장.
        base: dict = {
            "project": {
                "project_dir": str(project_root),
                "session_dir": str(project_root),
            },
            "calibration": {
                "calibration_type": "calculate",
                "calculate": {"save_debug_images": True},
            },
        }
        calc = base["calibration"]["calculate"]

        if step == "intrinsic":
            calc["intrinsics"] = {
                "overwrite_intrinsics":      True,
                "intrinsics_extension":      ext,
                "extract_every_N_sec":       1,
                "intrinsics_corners_nb":     [params.get("cols", 4), params.get("rows", 7)],
                "intrinsics_square_size":    params.get("square_size_mm", 60),
                "show_detection_intrinsics": False,   # macOS 메인스레드 제약으로 비활성화
            }
            calc["extrinsics"] = {"calculate_extrinsics": False}

        else:  # extrinsic
            method = params.get("method", "checkerboard")
            # Pose2Sim 내부 메서드명: 'checkerboard' → 'board'
            p2s_method = "board" if method == "checkerboard" else method
            extr: dict = {
                "calculate_extrinsics":    True,
                "extrinsics_method":       p2s_method,
                "extrinsics_extension":    ext,
                "show_reprojection_error": False,     # macOS 메인스레드 제약으로 비활성화
            }
            if method == "checkerboard":
                extr["board"] = {
                    "extrinsics_corners_nb":  [params.get("cols", 4), params.get("rows", 7)],
                    "extrinsics_square_size": params.get("square_size_mm", 60),
                }
            elif method == "scene":
                raw = params.get("scene_coords", "")
                coords = []
                for line in raw.strip().splitlines():
                    parts = line.strip().split()
                    if len(parts) == 3:
                        try:
                            coords.append([float(p) for p in parts])
                        except ValueError:
                            pass
                extr["scene"] = {"object_coords_3d": coords}

            calc["intrinsics"] = {"overwrite_intrinsics": False}
            calc["extrinsics"] = extr

        return base

    def cancel(self):
        """현재 실행 중인 Worker 취소 요청."""
        self._run_all_queue.clear()
        if self._active_worker and self._active_worker.isRunning():
            self._active_worker.requestInterruption()
            self.log_line.emit("[INFO] 취소 요청됨 — 현재 단계 완료 후 중단됩니다.")

    def is_running(self) -> bool:
        return bool(self._active_worker and self._active_worker.isRunning())
