"""
.trc 파일 파서 — Pose2Sim Triangulation 결과 3D 좌표 로드
# Design Ref: §4.2 — TRCData dataclass, parse_trc()
"""
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class TRCData:
    """
    .trc 파일에서 파싱된 3D 마커 데이터.
    # Design Ref: §4.2 — TRCData
    """
    marker_names: list[str]    # ["Hip", "LKnee", ...]
    frame_rate: float
    frames: np.ndarray         # shape: (N_frames, N_markers, 3)  [mm 단위]
    timestamps: np.ndarray     # shape: (N_frames,)  [초 단위]

    @property
    def n_frames(self) -> int:
        return len(self.frames)

    @property
    def n_markers(self) -> int:
        return len(self.marker_names)

    @property
    def duration(self) -> float:
        """전체 재생 시간 (초)."""
        return float(self.timestamps[-1]) if len(self.timestamps) > 0 else 0.0


def parse_trc(path: Path) -> TRCData:
    """
    .trc 포맷 파싱.

    TRC 파일 구조:
      Line 1: PathFileType  4  (X/Y/Z) <filename>
      Line 2: DataRate  CameraRate  NumFrames  NumMarkers  Units  ...
      Line 3: Frame#  Time  <Marker1>  <Marker1>  <Marker1>  <Marker2> ...
               (마커 이름이 X, Y, Z 3열씩 반복)
      Line 4: (공백 행)
      Line 5: 빈 줄
      Line 6+: 데이터 행  Frame#  Time  X1  Y1  Z1  X2  Y2  Z2 ...

    # Design Ref: §4.2 — parse_trc
    """
    with open(path, "r", encoding="utf-8-sig") as f:
        lines = f.readlines()

    if len(lines) < 6:
        raise ValueError(f"TRC 파일 형식 오류: 줄 수 부족 ({path.name})")

    # ── 포맷 감지 ──────────────────────────────────────────────────
    # 표준 TRC: lines[1] = 값(DataRate=25...), lines[2] = 마커명(Frame# Time ...)
    # Pose2Sim: lines[1] = 레이블("DataRate\tCameraRate\t..."), lines[2] = 값, lines[3] = 마커명
    first_token = lines[1].strip().split("\t")[0] if lines[1].strip() else ""
    is_posesim_format = not first_token.replace(".", "").replace("-", "").isdigit()

    values_line  = lines[2] if is_posesim_format else lines[1]
    markers_line = lines[3] if is_posesim_format else lines[2]

    # ── 헤더 파싱 ────────────────────────────────────────────────
    header2 = values_line.strip().split("\t")
    try:
        frame_rate  = float(header2[0]) if header2[0].replace(".", "").isdigit() else 30.0
        num_frames  = int(header2[2])
        num_markers = int(header2[3])
    except (IndexError, ValueError):
        frame_rate  = 30.0
        num_frames  = 0
        num_markers = 0

    # 마커명 행: Frame#  Time  Marker1  (blank)(blank)  Marker2 ...  (마커당 3열)
    header3 = markers_line.strip().split("\t")
    # 첫 2열(Frame#, Time) 제외 후 마커 이름 추출 (3열 간격)
    raw_names = header3[2:]
    marker_names: list[str] = []
    for i, name in enumerate(raw_names):
        if i % 3 == 0:
            cleaned = name.strip()
            if cleaned:
                marker_names.append(cleaned)

    # num_markers가 0이면 실제 이름 수로 결정
    if num_markers == 0:
        num_markers = len(marker_names)

    # ── 데이터 파싱 ───────────────────────────────────────────────
    # 헤더 5줄 이후부터 데이터 (빈 줄 건너뜀)
    data_lines = [l for l in lines[5:] if l.strip()]

    if not data_lines:
        # 빈 파일 → 빈 데이터 반환
        return TRCData(
            marker_names=marker_names,
            frame_rate=frame_rate,
            frames=np.zeros((0, max(num_markers, 1), 3)),
            timestamps=np.array([]),
        )

    rows = []
    timestamps_list = []
    for line in data_lines:
        parts = line.strip().split("\t")
        if len(parts) < 2:
            continue
        try:
            t = float(parts[1])
        except ValueError:
            continue
        timestamps_list.append(t)

        # X1 Y1 Z1 X2 Y2 Z2 ... (parts[2:])
        vals = parts[2:]
        marker_row = np.zeros((num_markers, 3))
        for m in range(num_markers):
            base = m * 3
            try:
                x = float(vals[base])     if base     < len(vals) else 0.0
                y = float(vals[base + 1]) if base + 1 < len(vals) else 0.0
                z = float(vals[base + 2]) if base + 2 < len(vals) else 0.0
            except (ValueError, IndexError):
                x, y, z = 0.0, 0.0, 0.0
            marker_row[m] = [x, y, z]
        rows.append(marker_row)

    frames     = np.array(rows)     if rows else np.zeros((0, num_markers, 3))
    timestamps = np.array(timestamps_list)

    return TRCData(
        marker_names=marker_names[:num_markers],
        frame_rate=frame_rate,
        frames=frames,
        timestamps=timestamps,
    )
