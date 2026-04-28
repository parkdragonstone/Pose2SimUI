"""
Pose2Sim API 호출 오케스트레이터
# Design Ref: §5.1 — PipelineRunner: STEP_ORDER, POSE2SIM_API, run_step(), cancel()
# Design Ref: §3.1 — Signals: step_started, step_progress, step_completed, log_line, pipeline_done
# Plan SC: SC-04 — 파이프라인 각 단계 개별 실행
# Plan SC: SC-05 — UI 블로킹 없음 (Worker → Signal)
"""
import re
from pathlib import Path

from PyQt5.QtCore import QObject, pyqtSignal

from src.core.workers.pipeline_worker import PipelineWorker, SubprocessPipelineWorker, SubprocessCalibWorker


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

    def run_step(self, step_name: str, working_dir: Path):
        """
        단일 파이프라인 단계 실행.
        이미 실행 중이면 무시.
        """
        if self._active_worker and self._active_worker.isRunning():
            self.log_line.emit(f"[WARN] 이미 실행 중입니다: {self._active_worker_step}")
            return

        if step_name not in self.STEP_ORDER:
            self.log_line.emit(f"[ERROR] 알 수 없는 단계: {step_name}")
            return

        self._sync_vid_extension(working_dir)
        self._migrate_config_keys(working_dir)

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
        SubprocessCalibWorker로 격리 실행 — PyQt5(Pose2Sim) / PyQt6(UI) 충돌 방지.
        # Design Ref: §8.2 — CalibPanel Run Intrinsic / Extrinsic
        """
        if self._active_worker and self._active_worker.isRunning():
            self.log_line.emit("[WARN] 이미 실행 중입니다.")
            return

        calib_dir = project_root / "calibration"
        if step == "intrinsic":
            cam_files = params.get("cam_files", {})
            if not any(cam_files.values()):
                self.log_line.emit("[ERROR] Intrinsic 미디어 파일이 선택되지 않았습니다. calibration/intrinsics/cam01/ 폴더 구조를 확인하세요.")
                return
            self._remove_macos_metadata(calib_dir / "intrinsics")
        else:
            cam_files = params.get("cam_files", {})
            method = params.get("method", "checkerboard")
            if method != "keypoints" and not any(cam_files.values()):
                self.log_line.emit("[ERROR] Extrinsic 미디어 파일이 선택되지 않았습니다. calibration/extrinsics/cam01/ 폴더 구조를 확인하세요.")
                return

            mismatch = self._check_cam_count_mismatch(cam_files, calib_dir)
            if mismatch:
                self.log_line.emit(f"[ERROR] {mismatch}")
                return
            self._remove_macos_metadata(calib_dir / "extrinsics")
            # Image_points.json 이 있으면 subprocess 내 tkinter 다이얼로그 방지를 위해 삭제
            img_pts = calib_dir / "Image_points.json"
            if img_pts.exists():
                try:
                    img_pts.unlink()
                    self.log_line.emit("[INFO] 이전 Image_points.json 제거 (tkinter 다이얼로그 방지)")
                except Exception:
                    pass

        config_dict = self._build_calib_config(step, params, project_root)
        image_coords_2d = params.get("image_coords_2d")


        self._active_worker_step = step
        worker = SubprocessCalibWorker(step, config_dict, image_coords_2d, project_root)
        worker.log_line.connect(self.log_line)
        worker.progress.connect(lambda p: self.step_progress.emit(step, p))
        worker.finished.connect(lambda ok, _: self._on_step_finished(step, ok))

        self._active_worker = worker
        self.step_started.emit(step)
        worker.start()

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

    def _sync_vid_extension(self, working_dir: Path) -> None:
        """
        working_dir/videos/ 폴더에서 실제 영상 확장자를 감지해
        Config.toml의 vid_img_extension을 자동 업데이트.
        """
        _VIDEO_EXTS = {".avi", ".mp4", ".mov", ".mkv", ".wmv"}
        videos_dir = working_dir / "videos"
        if not videos_dir.is_dir():
            return

        from collections import Counter
        counts: Counter = Counter()
        for f in videos_dir.iterdir():
            if f.is_file() and f.suffix.lower() in _VIDEO_EXTS:
                counts[f.suffix.lower().lstrip(".")] += 1
        if not counts:
            return

        detected_ext = counts.most_common(1)[0][0]

        config_path = working_dir / "Config.toml"
        if not config_path.exists():
            return

        try:
            import tomllib, tomli_w
            with open(config_path, "rb") as f:
                cfg = tomllib.load(f)
            current_ext = cfg.get("pose", {}).get("vid_img_extension", "")
            if current_ext == detected_ext:
                return
            cfg.setdefault("pose", {})["vid_img_extension"] = detected_ext
            with open(config_path, "wb") as f:
                tomli_w.dump(cfg, f)
            self.log_line.emit(
                f"[INFO] vid_img_extension 자동 업데이트: '{current_ext}' → '{detected_ext}'"
            )
        except Exception as e:
            self.log_line.emit(f"[WARN] Config.toml 확장자 업데이트 실패: {e}")

    def _migrate_config_keys(self, working_dir: Path) -> None:
        """이전 버전 Config.toml 키 마이그레이션 (현재는 처리할 rename 없음)."""
        pass

    def _build_calib_config(self, step: str, params: dict, project_root: Path) -> dict:
        """
        UI 파라미터 → Pose2Sim calibration config dict 변환.
        dict로 넘기면 Pose2Sim이 Config.toml 파일을 탐색하지 않음.
        """
        cam_files: dict = params.get("cam_files", {})

        # 첫 번째 유효 파일에서 확장자 추론 — Path.suffix 사용으로 경로 혼입 방지
        ext = "mp4"
        for file_path in cam_files.values():
            if file_path:
                suffix = Path(str(file_path)).suffix.lstrip(".")
                if suffix:
                    ext = suffix.lower()
                break

        # project_dir: Pose2Sim.py의 경고 방지용 (read_config_files에서 확인)
        # session_dir: calibration.py에서 calib 폴더 탐색에 사용
        # show_detection_intrinsics / show_reprojection_error: False
        #   → Pose2Sim이 matplotlib GUI 창을 백그라운드 스레드에서 열려 하면
        #     macOS에서 NSWindow 크래시 발생. GUI는 메인 스레드 전용이므로 비활성화.
        base: dict = {
            "project": {
                "project_dir": str(project_root),
                "session_dir": str(project_root),
            },
            "calibration": {
                "calibration_type": "calculate",
                "calculate": {},
            },
            "logging": {
                "use_custom_logging": False,
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
                "show_detection_intrinsics": True,    # subprocess 내 cv2.imshow → debug_images 파일 저장으로 리다이렉트
            }
            calc["extrinsics"] = {"calculate_extrinsics": False}

        else:  # extrinsic
            method = params.get("method", "checkerboard")
            # Pose2Sim 내부 메서드명: 'checkerboard' → 'board'
            p2s_method = "board" if method == "checkerboard" else method
            extr: dict = {
                "calculate_extrinsics": True,
                "extrinsics_method":    p2s_method,
            }
            # Pose2Sim은 extrinsics_extension을 method별 서브딕트에서 읽음
            # board → extr['board']['extrinsics_extension']
            # scene → extr['scene']['extrinsics_extension']
            if method == "checkerboard":
                extr["board"] = {
                    "extrinsics_extension":   ext,
                    "extrinsics_corners_nb":  [params.get("cols", 4), params.get("rows", 7)],
                    "extrinsics_square_size": params.get("square_size_mm", 60),
                    "show_reprojection_error": False,
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
                extr["scene"] = {
                    "extrinsics_extension":   ext,
                    "object_coords_3d":       coords,
                    "show_reprojection_error": False,
                }

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
