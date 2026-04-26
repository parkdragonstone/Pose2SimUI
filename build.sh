#!/usr/bin/env bash
# build.sh — macOS build script for Pose2SimUI
# Usage: ./build.sh [--clean]
#
# macOS 15 문제를 패키지 수정 없이 해결:
#   tools/codesign  — ad-hoc 서명 시 --timestamp 제거 (macOS 15 호환)
#   Python 패치     — OpenVINO dylib에서 서명 제거 + __LINKEDIT 수정 + truncate
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

CONDA_ENV="pose2simUI"

# ── conda env 확인 ────────────────────────────────────────────────────────────
if ! conda env list | grep -q "^${CONDA_ENV} "; then
    echo "[ERROR] conda 환경 '${CONDA_ENV}'을 찾을 수 없습니다."
    exit 1
fi

# ── 선택적 clean ──────────────────────────────────────────────────────────────
if [[ "${1:-}" == "--clean" ]]; then
    echo "[build] 이전 빌드 결과 제거..."
    rm -rf build dist
fi

echo "[build] __pycache__ 정리..."
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# ── macOS 전용 ────────────────────────────────────────────────────────────────
if [[ "$(uname)" != "Darwin" ]]; then
    echo "[build] PyInstaller 빌드 시작..."
    conda run -n "${CONDA_ENV}" pyinstaller --noconfirm pose2simUI.spec
    exit 0
fi

# 1) tools/codesign wrapper — PATH 앞에 삽입
#    PyInstaller가 호출하는 `codesign -s - ... --timestamp`에서
#    --timestamp를 제거해 macOS 15의 ad-hoc 서명 오류를 방지.
#    패키지(PyInstaller osx.py) 수정 없이 프로젝트 로컬 파일로 해결.
export PATH="${SCRIPT_DIR}/tools:${PATH}"
echo "[build] codesign wrapper: ${SCRIPT_DIR}/tools/codesign"

# 2) conda env prefix 결정 (conda run 불필요 — 직접 경로 사용)
CONDA_BASE="$(conda info --base)"
CONDA_PREFIX="${CONDA_BASE}/envs/${CONDA_ENV}"

# 3) OpenVINO dylib 패치
#    - 서명 있는 파일(fresh): LC_CODE_SIGNATURE 제거 + __LINKEDIT 축소 + truncate
#    - 이미 패치됐지만 잘못된 파일: trailing zeros 스캔으로 truncate 지점 찾아 수정
OPENVINO_LIBS=""
for pyver in 3.12 3.11 3.10; do
    candidate="${CONDA_PREFIX}/lib/python${pyver}/site-packages/openvino/libs"
    if [[ -d "${candidate}" ]]; then
        OPENVINO_LIBS="${candidate}"
        break
    fi
done

if [[ -n "${OPENVINO_LIBS}" ]]; then
    echo "[build] OpenVINO dylib 패치: ${OPENVINO_LIBS}"
    python3 - "${OPENVINO_LIBS}" << 'PYEOF'
import struct, sys, pathlib

MH_MAGIC_64       = 0xFEEDFACF
LC_CODE_SIGNATURE = 0x1d
LC_SEGMENT_64     = 0x19
LINKEDIT_NAME     = b'__LINKEDIT\x00\x00\x00\x00\x00\x00'

def patch(path: str) -> str:
    """
    Remove code signature from a 64-bit LE Mach-O dylib.
    Handles two states:
      A) Fresh file: has LC_CODE_SIGNATURE → remove it, fix __LINKEDIT, truncate.
      B) Already zeroed (bad patch): trailing zeros → scan back, fix __LINKEDIT, truncate.
    """
    with open(path, 'rb') as f:
        data = bytearray(f.read())

    if struct.unpack_from('<I', data, 0)[0] != MH_MAGIC_64:
        return "skip"

    ncmds      = struct.unpack_from('<I', data, 16)[0]
    sizeofcmds = struct.unpack_from('<I', data, 20)[0]

    codesig_lc   = None; codesig_sz = None
    codesig_off  = None; codesig_size = None
    li_fsize_pos = None
    li_fileoff   = None; li_filesize = None

    lc = 32
    for _ in range(ncmds):
        cmd, sz = struct.unpack_from('<II', data, lc)
        if cmd == LC_CODE_SIGNATURE:
            codesig_lc   = lc;   codesig_sz   = sz
            codesig_off, codesig_size = struct.unpack_from('<II', data, lc + 8)
        elif cmd == LC_SEGMENT_64 and bytes(data[lc+8:lc+24]) == LINKEDIT_NAME:
            li_fileoff   = struct.unpack_from('<Q', data, lc + 40)[0]
            li_filesize  = struct.unpack_from('<Q', data, lc + 48)[0]
            li_fsize_pos = lc + 48
        lc += sz

    # ── Case A: fresh signed file ─────────────────────────────────────────────
    if codesig_lc is not None:
        if li_fsize_pos:
            struct.pack_into('<Q', data, li_fsize_pos, li_filesize - codesig_size)
        data[codesig_lc:codesig_lc + codesig_sz] = b'\x00' * codesig_sz
        struct.pack_into('<I', data, 16, ncmds - 1)
        struct.pack_into('<I', data, 20, sizeofcmds - codesig_sz)
        with open(path, 'wb') as f:
            f.write(data[:codesig_off])
        return f"patched ({len(data)} → {codesig_off})"

    # ── Case B: LC_CODE_SIGNATURE already zeroed but file not truncated ───────
    if li_fileoff is None:
        return "ok"
    i = len(data) - 1
    while i > li_fileoff and data[i] == 0:
        i -= 1
    truncate_at = (i + 1 + 7) & ~7   # align to 8 bytes
    if truncate_at >= len(data):
        return "ok"
    struct.pack_into('<Q', data, li_fsize_pos, truncate_at - li_fileoff)
    with open(path, 'wb') as f:
        f.write(data[:truncate_at])
    return f"repaired ({len(data)} → {truncate_at})"

for dylib in pathlib.Path(sys.argv[1]).glob('*.dylib'):
    try:
        r = patch(str(dylib))
        if r not in ('skip', 'ok'):
            print(f"  {dylib.name}: {r}")
    except Exception as e:
        print(f"  {dylib.name}: ERROR {e}")
PYEOF
else
    echo "[build] OpenVINO libs 없음 — 패치 건너뜀"
fi

# 4) PyInstaller bincache 무조건 초기화
#    conda env 재설치 후에도 bincache는 홈 디렉터리에 남아있어
#    이전 빌드의 깨진 캐시가 사용될 수 있다.
PYCACHE_BASE="${HOME}/Library/Application Support/pyinstaller"
echo "[build] PyInstaller bincache 초기화..."
find "${PYCACHE_BASE}" -maxdepth 1 -name "bincache*" -type d -exec rm -rf {} + 2>/dev/null || true

# ── PyInstaller 빌드 ──────────────────────────────────────────────────────────
echo "[build] PyInstaller 빌드 시작..."
conda run -n "${CONDA_ENV}" pyinstaller --noconfirm pose2simUI.spec

# ── 결과 확인 ─────────────────────────────────────────────────────────────────
if [[ -d "dist/Pose2SimUI.app" ]]; then
    echo ""
    echo "[build] 성공: dist/Pose2SimUI.app"
    echo "  실행: open dist/Pose2SimUI.app"
elif [[ -d "dist/Pose2SimUI" ]]; then
    echo ""
    echo "[build] 성공: dist/Pose2SimUI/"
else
    echo "[build] 빌드 실패"
    exit 1
fi
