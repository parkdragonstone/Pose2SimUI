@echo off
REM build.bat — Windows build script for Pose2SimUI
REM Usage: build.bat [--clean]

setlocal enabledelayedexpansion
cd /d "%~dp0"

REM ── conda env 확인 ─────────────────────────────────────────────────────────
set CONDA_ENV=pose2simUI
conda env list | findstr /C:"%CONDA_ENV%" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] conda 환경 '%CONDA_ENV%'을 찾을 수 없습니다.
    echo   conda env create -n %CONDA_ENV% python=3.11
    echo   pip install -r requirements.txt pyinstaller
    exit /b 1
)

REM ── 선택적 clean ──────────────────────────────────────────────────────────
if "%1"=="--clean" (
    echo [build] 이전 빌드 결과 제거...
    if exist build rmdir /s /q build
    if exist dist  rmdir /s /q dist
)

REM ── __pycache__ 정리 ──────────────────────────────────────────────────────
echo [build] __pycache__ 정리...
for /d /r . %%d in (__pycache__) do (
    if exist "%%d" rmdir /s /q "%%d" 2>nul
)

REM ── PyInstaller 실행 ──────────────────────────────────────────────────────
echo [build] PyInstaller 빌드 시작...
conda run -n %CONDA_ENV% pyinstaller --noconfirm pose2simUI.spec
if errorlevel 1 (
    echo [build] 빌드 실패 — 위 오류를 확인하세요.
    exit /b 1
)

REM ── 결과 확인 ─────────────────────────────────────────────────────────────
if exist "dist\Pose2SimUI\Pose2SimUI.exe" (
    echo.
    echo [build] 성공: dist\Pose2SimUI\Pose2SimUI.exe
) else (
    echo [build] 빌드 실패 — dist\ 디렉터리를 확인하세요.
    exit /b 1
)

endlocal
