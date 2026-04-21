#!/usr/bin/env bash
# build.sh — macOS / Linux build script for Pose2SimUI
# Usage: ./build.sh [--clean]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ── conda env 확인 ────────────────────────────────────────────────────────────
CONDA_ENV="pose2simUI"
if ! conda env list | grep -q "^${CONDA_ENV} "; then
    echo "[ERROR] conda 환경 '${CONDA_ENV}'을 찾을 수 없습니다."
    echo "  conda env create -n ${CONDA_ENV} python=3.11"
    echo "  conda install -c opensim-org opensim"
    echo "  pip install -r requirements.txt pyinstaller"
    exit 1
fi

# ── 선택적 clean ──────────────────────────────────────────────────────────────
if [[ "${1:-}" == "--clean" ]]; then
    echo "[build] 이전 빌드 결과 제거..."
    rm -rf build dist
fi

# ── 캐시 정리 (버스 오류 방지) ─────────────────────────────────────────────
echo "[build] __pycache__ 정리..."
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# ── PyInstaller 실행 ──────────────────────────────────────────────────────────
echo "[build] PyInstaller 빌드 시작..."
conda run -n "${CONDA_ENV}" pyinstaller \
    --noconfirm \
    pose2simUI.spec

# ── 결과 확인 ─────────────────────────────────────────────────────────────────
if [[ -d "dist/Pose2SimUI.app" ]]; then
    echo ""
    echo "[build] 성공: dist/Pose2SimUI.app"
    echo "  실행: open dist/Pose2SimUI.app"
elif [[ -d "dist/Pose2SimUI" ]]; then
    echo ""
    echo "[build] 성공: dist/Pose2SimUI/"
    echo "  실행: ./dist/Pose2SimUI/Pose2SimUI"
else
    echo "[build] 빌드 실패 — dist/ 디렉터리를 확인하세요."
    exit 1
fi
