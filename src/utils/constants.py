"""
앱 전역 상수
# Design Ref: §1.1 — utils/ 레이어: 순수 유틸리티, 상태 저장 금지
"""
from pathlib import Path

# 앱 메타
APP_NAME = "Pose2SimUI"
APP_VERSION = "0.1.0"

# 3D 뷰어 기본 TRC 파일명 (FR-09)
# Plan SC: SC-08a — filtered_LSTM.trc를 기본값으로 3D 뷰어에 자동 로드
DEFAULT_TRC = "filtered_LSTM.trc"

# Trial 탐지 시 제외할 폴더명 (Pose2Sim 예약 폴더 + 일반 시스템 폴더)
EXCLUDE_DIRS = {
    "calibration", "logs", ".git", "__pycache__",
    "pose", "pose3d", "kinematics", "videos",
}

# Pose2Sim 표준 프로젝트 폴더 구조 (새 프로젝트 생성 시 자동 생성)
# Plan SC: SC-01 — 새 프로젝트 생성 시 표준 폴더 구조 자동 생성
POSE2SIM_DIR_STRUCTURE = [
    "calibration/intrinsics",
    "calibration/extrinsics",
    "Trial_01/videos",
]

# Config.toml 기본 템플릿 (Pose2Sim 기본값 기반)
# 참조: /Users/yongseok/Downloads/Config.toml (Pose2Sim 공식 기본 Config)
DEFAULT_CONFIG: dict = {
    "project": {
        "project_dir": ".",
        "frame_rate": "auto",
        "frame_range": "auto",
        "multi_person": False,
        "nb_persons_to_detect": 1,
        "participant_height": "auto",
        "participant_mass": 70.0,
        "exclude_from_batch": [],
    },
    "pose": {
        "vid_img_extension": "mp4",
        "pose_model": "Body_with_feet",
        "mode": "balanced",
        "det_frequency": 4,
        "device": "auto",
        "backend": "auto",
        "parallel_workers_pose": "auto",
        "display_detection": False,
        "overwrite_pose": False,
        "save_video": "to_video",
        "output_format": "openpose",
        "tracking_mode": "sports2d",
        "max_distance_px": 100,
        "handle_LR_swap": False,
        "undistort_points": False,
    },
    "synchronization": {
        "synchronization_gui": False,
        "display_sync_plots": False,
        "save_sync_plots": False,
        "keypoints_to_consider": "all",
        "approx_time_maxspeed": "auto",
        "time_range_around_maxspeed": 2.0,
        "likelihood_threshold_synchronization": 0.4,
        "filter_cutoff": 6,
        "filter_order": 4,
    },
    "calibration": {
        "calibration_type": "load",
        "load": {
            "file": {
                "intrinsics_file": "",
                "extrinsics_file": "",
            }
        },
    },
    "personAssociation": {
        "likelihood_threshold_association": 0.3,
        "single_person": {
            "likelihood_threshold_association": 0.3,
            "reproj_error_threshold_association": 20,
            "tracked_keypoint": "Neck",
        },
        "multi_person": {
            "reconstruction_error_threshold": 0.1,
            "min_affinity": 0.2,
        },
    },
    "triangulation": {
        "reproj_error_threshold_triangulation": 15,
        "likelihood_threshold_triangulation": 0.3,
        "min_cameras_for_triangulation": 2,
        "interpolation": "linear",
        "interp_if_gap_smaller_than": 20,
        "show_interp_indices": True,
        "make_c3d": False,
        "max_distance_m": 1.0,
        "max_unseen_frames": 100,
        "remove_incomplete_frames": False,
        "sections_to_keep": "all",
        "min_chunk_size": 10,
        "fill_large_gaps_with": "last_value",
    },
    "filtering": {
        "reject_outliers": True,
        "filter": True,
        "filter_ik": False,
        "type": "butterworth",
        "display_figures": False,
        "overwrite_filterd": True,
        "save_filt_plots": False,
        "make_c3d": False,
        "butterworth": {"order": 4, "cut_off_frequency": 6},
        "kalman": {"trust_ratio": 500, "smooth": True},
        "one_euro": {"cut_off_frequency": 4.0, "beta": 1.5, "d_cut_off_frequency": 1.0},
        "gcv_spline": {"cut_off_frequency": "auto", "smoothing_factor": 1.0},
        "gaussian": {"sigma_kernel": 1},
        "loess": {"nb_values_used": 5},
        "median": {"kernel_size": 3},
        "butterworth_on_speed": {"order": 4, "cut_off_frequency": 10},
    },
    "markerAugmentation": {
        "feet_on_floor": False,
        "make_c3d": False,
    },
    "kinematics": {
        "use_augmentation": True,
        "use_simple_model": True,
        "parallel_workers_kinematics": "auto",
        "right_left_symmetry": True,
        "default_height": 1.7,
        "remove_individual_scaling_setup": True,
        "remove_individual_ik_setup": True,
        "fastest_frames_to_remove_percent": 0.1,
        "slowest_frames_to_remove_percent": 0.1,
        "large_hip_knee_angles": 135,
        "trimmed_extrema_percent": 0.5,
    },
    "logging": {
        "use_custom_logging": False,
    },
}
