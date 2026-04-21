# Pose2SimUI

[Pose2Sim](https://github.com/perfanalytics/pose2sim) 모션 캡처 파이프라인을 위한 PyQt6 기반 GUI 애플리케이션입니다.  
카메라 캘리브레이션부터 Kinematics 분석까지 전체 파이프라인을 시각적으로 관리할 수 있습니다.

---

## 시스템 요구사항

| 항목 | 요구사항 |
|---|---|
| OS | macOS (Apple Silicon 권장), Windows 10/11 |
| Python | 3.12 |
| 패키지 관리자 | [Miniconda](https://docs.conda.io/en/latest/miniconda.html) 또는 Anaconda |

---

## 설치 방법

### 1. 저장소 클론

```bash
git clone <여기에_저장소_주소_입력>
cd Pose2SimUI
```

---

### 2. conda 환경 생성

```bash
conda create -n pose2simUI python=3.12 -y
conda activate pose2simUI
```

---

### 3. 의존성 설치

```bash
pip install -r requirements.txt
```

---

### 4. OpenSim 설치 (Kinematics 단계 필수)

OpenSim은 pip으로 설치할 수 없으며 반드시 conda 채널을 사용해야 합니다.

```bash
conda install -c opensim-org opensim -y
```

> **macOS Apple Silicon 주의사항**  
> OpenSim 4.5 이상부터 Apple Silicon을 공식 지원합니다.  
> OpenSim 없이도 앱은 실행되지만, Kinematics 단계 실행 시 오류가 발생합니다.

---

## 실행 방법

### macOS

```bash
./run.sh
```

또는

```bash
conda run -n pose2simUI python main.py
```

### Windows

```bat
conda run -n pose2simUI python main.py
```

> **macOS 주의사항**  
> Apple Silicon에서는 반드시 `conda run` 또는 `./run.sh`를 사용해야 합니다.  
> 직접 `python main.py` 실행 시 Bus Error가 발생할 수 있습니다.

---

## 프로젝트 폴더 구조

새 프로젝트 생성 시 아래 구조가 자동으로 만들어집니다.

```
프로젝트명/
├── calibration/
│   ├── intrinsics/       # 카메라 내부 파라미터 캘리브레이션 영상
│   └── extrinsics/       # 카메라 외부 파라미터 캘리브레이션 영상/이미지
├── Trial_01/
│   └── videos/           # 분석할 원본 영상
└── Config.toml           # 파이프라인 설정 파일
```

---

## 파이프라인 단계

| 단계 | 설명 |
|---|---|
| **Calibration** | 카메라 내부/외부 파라미터 캘리브레이션 |
| **Pose Estimation** | 각 영상에서 2D 관절 좌표 추출 |
| **Synchronization** | 다중 카메라 영상 시간 동기화 |
| **Person Association** | 다중 인물 환경에서 동일 인물 연결 |
| **Triangulation** | 2D 좌표 → 3D 좌표 변환 |
| **Filtering** | 3D 좌표 노이즈 필터링 |
| **Marker Augmentation** | 마커 보강 (LSTM 기반) |
| **Kinematics** | 관절 각도 계산 (OpenSim 필요) |

---

## 주요 기능

- **멀티 프로젝트** — 여러 프로젝트를 동시에 관리
- **실시간 설정 편집** — Config.toml을 GUI에서 직접 수정/저장
- **3D Keypoint 뷰어** — TRC 파일 기반 스켈레톤 애니메이션
- **Kinematics 뷰어** — MOT 파일 기반 관절 각도 그래프
- **GUI 파이프라인** — 각 단계를 별도 프로세스로 실행 (matplotlib GUI 지원)

---

## 문제 해결

**앱 실행 시 Bus Error (macOS)**
```bash
# .pyc 캐시 삭제 후 재실행
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
./run.sh
```

**Kinematics 실행 오류**
```bash
# OpenSim 설치 확인
conda run -n pose2simUI python -c "import opensim; print(opensim.__version__)"
```

---

## 빌드 방법

소스코드로부터 독립 실행 파일(.app / .exe)을 생성합니다.  
빌드 전에 conda 환경과 의존성이 모두 설치되어 있어야 합니다.

### 사전 준비

```bash
pip install pyinstaller==6.19.0
```

### macOS

```bash
# 일반 빌드
./build.sh

# 이전 빌드 결과를 완전히 제거하고 새로 빌드
./build.sh --clean
```

빌드 완료 후 결과물 위치:

```
dist/Pose2SimUI.app
```

실행:

```bash
open dist/Pose2SimUI.app
```

### Windows

```bat
REM 일반 빌드
build.bat

REM 이전 빌드 결과를 완전히 제거하고 새로 빌드
build.bat --clean
```

빌드 완료 후 결과물 위치:

```
dist\Pose2SimUI\Pose2SimUI.exe
```

> **빌드 주의사항**  
> - 빌드 시 `__pycache__` 가 자동으로 정리됩니다.  
> - macOS에서는 `conda run` 을 통해 PyInstaller가 실행되므로 반드시 conda 환경이 활성화되어 있어야 합니다.  
> - OpenSim을 포함한 전체 기능 빌드는 OpenSim conda 환경이 구성된 상태에서만 가능합니다.

---

## Demo
