"""
config.py - 게임 전역 설정 관리.

settings.json 이 존재하면 그 값을 읽어 기본값을 덮어쓴다.
게임 내에서 변경된 설정은 save_settings() 로 다시 기록된다.
"""

import json
import os

SETTINGS_FILE = "settings.json"

# ---------------------------------------------------------------------------
# 기본 설정값
# ---------------------------------------------------------------------------
DEFAULTS = {
    # 화면
    "resolution": [1280, 720],
    "fullscreen": False,
    "max_fps": 60,
    "fov": 90,
    "brightness": 1.0,

    # 조작
    "mouse_sensitivity": 40.0,

    # 월드
    "render_distance": 3,        # 청크 단위 (플레이어 중심 반경)
    "chunk_size": 16,            # X/Z 크기
    "world_height": 128,         # Y 크기
    "seed": 0,                   # 0 이면 무작위
    "day_length": 600.0,         # 하루 길이(초)
    "difficulty": "normal",      # easy / normal / hard
    "start_mode": "survival",    # survival / creative

    # 사운드 (에셋 미포함 - 볼륨 값만 유지)
    "sound_volume": 0.5,

    # 엔티티
    "mob_spawning": True,
    "max_mobs": 24,
    "mob_update_distance": 40.0,
    "item_drop_lifetime": 180.0,  # 드롭 아이템 유지 시간(초)
    "max_item_drops": 120,

    # 저장
    "autosave_interval": 120.0,
}

# 현재 설정 (모듈 로드시 파일에서 갱신)
SETTINGS = dict(DEFAULTS)


def load_settings():
    """settings.json 을 읽어 SETTINGS 를 갱신한다."""
    global SETTINGS
    SETTINGS = dict(DEFAULTS)
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for key, value in data.items():
                if key in SETTINGS:
                    SETTINGS[key] = value
        except (json.JSONDecodeError, OSError):
            pass
    return SETTINGS


def save_settings():
    """현재 SETTINGS 를 settings.json 에 기록한다."""
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(SETTINGS, f, indent=2, ensure_ascii=False)
    except OSError:
        pass


def get(key):
    return SETTINGS.get(key, DEFAULTS.get(key))


def set_value(key, value):
    SETTINGS[key] = value


# 모듈 로드시 자동 적용
load_settings()

# ---------------------------------------------------------------------------
# 자주 쓰이는 상수 (설정에서 파생)
# ---------------------------------------------------------------------------
CHUNK_SIZE = int(get("chunk_size"))
WORLD_HEIGHT = int(get("world_height"))
SEA_LEVEL = 48                 # 해수면 높이
GRAVITY = 24.0                 # 중력 가속도
PLAYER_REACH = 5.0             # 상호작용 거리
SAVE_DIR = "saves"
