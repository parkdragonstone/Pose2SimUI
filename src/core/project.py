"""
Project / Trial 데이터 모델
# Design Ref: §4.1 — Project/Trial dataclass, list_calib_files()
"""
from dataclasses import dataclass, field
from pathlib import Path

from src.utils.constants import DEFAULT_TRC


@dataclass
class Trial:
    """
    프로젝트 루트 아래의 단일 Trial(측정 세션).
    파일 존재 여부로 분석 완료 상태를 판단한다.
    """
    name: str
    path: Path

    # ── 분석 완료 여부 (파일 존재 여부로 판단) ──────────────────────────

    @property
    def has_pose_video(self) -> bool:
        """pose/ 폴더에 *_pose.mp4 파일이 존재하는지 확인."""
        return bool(list((self.path / "pose").glob("*_pose.mp4")))

    @property
    def has_trc(self) -> bool:
        """pose-3d/ 폴더에 .trc 파일이 존재하는지 확인."""
        return bool(list((self.path / "pose-3d").glob("*.trc")))

    @property
    def has_kinematics(self) -> bool:
        """kinematics/ 폴더에 .mot 파일이 존재하는지 확인."""
        return bool(list((self.path / "kinematics").glob("*.mot")))

    @property
    def status_label(self) -> str:
        """사이드바 배지용 짧은 상태 문자열."""
        parts = []
        if self.has_trc:
            parts.append("3D")
        if self.has_kinematics:
            parts.append("Kin")
        return " | ".join(parts) if parts else ""

    # ── 파일 경로 헬퍼 ────────────────────────────────────────────────

    def default_trc_path(self) -> Path | None:
        """
        filtered_LSTM.trc 우선, 없으면 가장 최근 .trc 파일 반환.
        # Plan SC: SC-08a — filtered_LSTM.trc를 기본값으로 3D 뷰어에 자동 로드
        """
        preferred = self.path / "pose-3d" / DEFAULT_TRC
        if preferred.exists():
            return preferred
        files = sorted(
            (self.path / "pose-3d").glob("*.trc"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return files[0] if files else None

    def raw_videos(self) -> list[Path]:
        """videos/ 폴더의 원본 영상 목록 (이름 순)."""
        vid_dir = self.path / "videos"
        if not vid_dir.exists():
            return []
        exts = {".avi", ".mp4", ".mov"}
        return sorted(f for f in vid_dir.iterdir()
                      if f.is_file() and f.suffix.lower() in exts)

    def pose_videos(self) -> list[Path]:
        """pose/ 폴더의 카메라별 렌더링 영상 목록 (이름 순)."""
        pose_dir = self.path / "pose"
        if not pose_dir.exists():
            return []
        return sorted(pose_dir.glob("*_pose.mp4"))

    def trc_files(self) -> list[Path]:
        """pose-3d/ 폴더의 .trc 파일 목록 (수정 시간 역순)."""
        trc_dir = self.path / "pose-3d"
        if not trc_dir.exists():
            return []
        return sorted(trc_dir.glob("*.trc"),
                      key=lambda p: p.stat().st_mtime, reverse=True)

    def mot_files(self) -> list[Path]:
        """kinematics/ 폴더의 .mot 파일 목록 (수정 시간 역순)."""
        kin_dir = self.path / "kinematics"
        if not kin_dir.exists():
            return []
        return sorted(kin_dir.glob("*.mot"),
                      key=lambda p: p.stat().st_mtime, reverse=True)

    def config_path(self) -> Path:
        """Trial 디렉토리 내 Config.toml 경로."""
        return self.path / "Config.toml"


@dataclass
class Project:
    """
    Pose2Sim 프로젝트 루트를 나타내는 모델.
    Calibration 파일 목록과 Trial 목록을 관리한다.
    """
    name: str
    root_path: Path
    trials: list[Trial] = field(default_factory=list)
    active_trial: Trial | None = None

    def get_config_path(self) -> Path:
        """프로젝트 루트의 Config.toml 경로."""
        return self.root_path / "Config.toml"

    def list_calib_files(self) -> list[Path]:
        """
        프로젝트 루트 및 calibration/ 서브폴더의 Calib*.toml 파일 목록 반환 (수정 시간 역순).
        Pose2Sim은 calibration/ 아래에 Calib.toml을 생성하므로 두 위치 모두 탐색.
        # Design Ref: §4.1 — 복수 Calib.toml 파일 지원
        """
        files: list[Path] = list(self.root_path.glob("Calib*.toml"))
        calib_subdir = self.root_path / "calibration"
        if calib_subdir.is_dir():
            files += list(calib_subdir.glob("Calib*.toml"))
        seen: set[Path] = set()
        unique = [f for f in files if not (f in seen or seen.add(f))]  # type: ignore[func-returns-value]
        return sorted(unique, key=lambda p: p.stat().st_mtime, reverse=True)

    def get_active_config_path(self) -> Path:
        """
        현재 활성 Trial의 Config.toml이 있으면 그것을, 없으면 프로젝트 루트의 Config.toml 반환.
        """
        if self.active_trial:
            trial_cfg = self.active_trial.config_path()
            if trial_cfg.exists():
                return trial_cfg
        return self.get_config_path()
