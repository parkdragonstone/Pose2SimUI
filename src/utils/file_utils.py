"""
파일/폴더 헬퍼 유틸리티
# Design Ref: §1.1 — utils/ 레이어: 순수 유틸리티, 상태 저장 금지
"""
import os
import subprocess
import sys
from pathlib import Path


def ensure_dir(path: Path) -> Path:
    """디렉토리가 없으면 생성 후 반환."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def open_in_explorer(path: Path) -> None:
    """OS 기본 파일 탐색기로 경로를 연다. 크로스플랫폼."""
    if not path.exists():
        return
    if sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    elif sys.platform == "win32":
        os.startfile(str(path))
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


def find_files(directory: Path, pattern: str) -> list[Path]:
    """디렉토리에서 glob 패턴에 맞는 파일 목록 반환 (수정 시간 역순)."""
    if not directory.exists():
        return []
    return sorted(directory.glob(pattern),
                  key=lambda p: p.stat().st_mtime,
                  reverse=True)


def safe_stem(path: Path) -> str:
    """파일명에서 확장자를 제거한 이름 반환."""
    return path.stem
