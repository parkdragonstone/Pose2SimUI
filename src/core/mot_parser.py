"""
OpenSim .mot 파일 파서 — MOTData(joint_names, time, data)
# Design Ref: §4.3 — MOT 파싱 모델
"""
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass
class MOTData:
    """
    .mot 파일에서 파싱된 관절 각도 데이터.
    # Design Ref: §4.3 — MOTData
    """
    joint_names: list[str]              # ["knee_angle_r", "hip_flexion_r", ...]
    time: np.ndarray                    # shape: (N_frames,)  단위: 초
    data: dict[str, np.ndarray]         # joint_name → angle array (degrees)

    @property
    def n_frames(self) -> int:
        return len(self.time)

    @property
    def duration(self) -> float:
        """영상 총 길이 (초)."""
        return float(self.time[-1] - self.time[0]) if self.n_frames > 1 else 0.0


def parse_mot(path: Path) -> MOTData:
    """
    OpenSim .mot 파일 파싱.

    포맷:
      - 헤더 섹션: 'endheader' 행까지
      - 데이터 섹션: 탭 구분, 첫 행 = 열 이름, 이후 = 숫자 데이터
      - 첫 열 = time, 이후 열 = 관절별 각도 (degrees)

    # Design Ref: §4.3 — parse_mot
    """
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    # ── 헤더 끝 위치 탐색 ─────────────────────────────────────────
    header_end = 0
    for i, line in enumerate(lines):
        if line.strip().lower() == "endheader":
            header_end = i + 1
            break

    data_lines = [l for l in lines[header_end:] if l.strip()]
    if not data_lines:
        raise ValueError(f"데이터 행 없음: {path}")

    # ── 열 이름 행 ────────────────────────────────────────────────
    col_names = data_lines[0].strip().split()
    if not col_names:
        raise ValueError(f"열 이름 파싱 실패: {path}")

    # ── 숫자 데이터 ───────────────────────────────────────────────
    rows: list[list[float]] = []
    for line in data_lines[1:]:
        parts = line.strip().split()
        if len(parts) == len(col_names):
            try:
                rows.append([float(v) for v in parts])
            except ValueError:
                continue

    if not rows:
        raise ValueError(f"유효한 데이터 행 없음: {path}")

    arr = np.array(rows, dtype=np.float64)   # (N, n_cols)

    # 첫 열 = time, 나머지 = 관절
    time        = arr[:, 0]
    joint_names = col_names[1:]
    data        = {name: arr[:, i + 1] for i, name in enumerate(joint_names)}

    return MOTData(joint_names=joint_names, time=time, data=data)
