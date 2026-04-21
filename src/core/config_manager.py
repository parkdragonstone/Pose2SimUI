"""
Config.toml / Calib.toml 읽기·쓰기 관리자
# Design Ref: §5.3 — ConfigManager: tomllib(읽기) + tomli-w(쓰기)
"""
import copy
import tomllib
import tomli_w
from pathlib import Path

from src.utils.constants import DEFAULT_CONFIG


class ConfigManager:
    """
    TOML 설정 파일 읽기/쓰기 담당.
    Qt 위젯 import 없이 순수 파일 I/O만 수행.
    """

    def load(self, path: Path) -> dict:
        """TOML 파일을 읽어 dict로 반환. 파일이 없으면 빈 dict."""
        if not path.exists():
            return {}
        with open(path, "rb") as f:
            return tomllib.load(f)

    def save(self, data: dict, path: Path) -> None:
        """dict를 TOML 파일로 저장. 부모 디렉토리가 없으면 생성."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            tomli_w.dump(data, f)

    def get_default_config(self) -> dict:
        """Pose2Sim 기본 Config.toml 구조의 깊은 복사본 반환."""
        return copy.deepcopy(DEFAULT_CONFIG)

    def load_or_default(self, path: Path) -> dict:
        """
        파일이 있으면 로드, 없으면 기본 설정 반환.
        기본값과 병합해 누락된 키를 채운다.
        """
        base = self.get_default_config()
        if path.exists():
            loaded = self.load(path)
            _deep_merge(base, loaded)
        return base

    def create_project_config(self, project_dir: Path) -> None:
        """
        새 프로젝트용 Config.toml 생성.
        project.project_dir를 실제 경로로 설정.
        # Plan SC: SC-01 — 새 프로젝트 생성 시 Config.toml 자동 생성
        """
        config = self.get_default_config()
        config["project"]["project_dir"] = str(project_dir)
        self.save(config, project_dir / "Config.toml")


def _deep_merge(base: dict, override: dict) -> None:
    """override의 값을 base에 재귀적으로 병합 (override가 우선)."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
