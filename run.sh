#!/bin/bash
# Pose2SimUI launcher — uses conda run for correct env setup on macOS ARM64
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# stderr 필터: FFmpeg 프로브 출력, codec 경고, macOS 시스템 노이즈, conda 정상 종료 오탐 제거.
# Python traceback / 실제 예외는 보존 (패턴이 충분히 specific 함).
#
#  ^\[.*@ 0x[0-9a-f]                  — [mpeg4 @ 0x...] 등 FFmpeg codec 경고
#  ^Input #[0-9]                       — FFmpeg 파일 프로브 헤더
#  ^  (Stream|Metadata:|Duration:...)  — 스트림/메타데이터 섹션 헤더
#  ^    (major_brand|...)              — 메타데이터 값 행
#  Consider increasing.*analyzeduration — 특수 포맷 프로브 경고
#  TSM AdjustCapsLockLED               — macOS 텍스트 서비스 내부 로그
#  resource_tracker.*leaked semaphore  — pose2sim multiprocessing 정리 경고
#  ^ERROR conda\.cli                   — 정상 종료 시 conda 오탐 오류 메시지
#  `conda run.*` failed\.              — conda 오류 부연 설명
_ffmpeg_filter() {
    grep -Ev \
        '^\[.*@ 0x[0-9a-f]|^Input #[0-9]|^  (Stream|Metadata:|Duration:|Program |Side data:)|^    (major_brand|minor_version|compatible_brands|encoder|handler_name|vendor_id|creation_time|location|Ambient)|Consider increasing.*analyzeduration|TSM AdjustCapsLockLED|resource_tracker.*leaked semaphore|^ERROR conda\.cli|`conda run.*` failed\.' \
        >&2
}

# exit code 매핑:
#   143 = 128+15 (SIGTERM)  — 정상 종료 (Cmd+Q)
#   133 = 128+5  (SIGTRAP)  — Qt multimedia 정리 중 비정상 종료 (apac/MPEG4 코덱 관련)
AV_LOG_LEVEL=quiet conda run -n pose2simUI python "$SCRIPT_DIR/main.py" "$@" \
    2> >(_ffmpeg_filter)

EXIT=$?
{ [ $EXIT -eq 143 ] || [ $EXIT -eq 133 ]; } && exit 0 || exit $EXIT
