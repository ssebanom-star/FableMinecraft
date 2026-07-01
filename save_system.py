"""
save_system.py - 저장/불러오기.

저장 구조:
  saves/<world_name>/world.json            (seed, 시간, 날씨)
  saves/<world_name>/player.json           (위치/체력/허기/산소/모드 ...)
  saves/<world_name>/inventory.json        (인벤토리 + 장비)
  saves/<world_name>/containers.json       (상자/화로 내용)
  saves/<world_name>/modified_blocks.json  (변경된 블록)
  saves/<world_name>/entities.json         (몹 + 드롭 아이템)
"""

import json
import os

import config


def world_dir(world_name):
    return os.path.join(config.SAVE_DIR, world_name)


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)


def _read_json(path, default=None):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


# ---------------------------------------------------------------------------
# 개별 저장/로드
# ---------------------------------------------------------------------------
def save_player(game, world_name):
    _write_json(os.path.join(world_dir(world_name), "player.json"),
                game.player.serialize())


def load_player(game, world_name):
    data = _read_json(os.path.join(world_dir(world_name), "player.json"))
    if data:
        game.player.deserialize(data)
    return data is not None


def save_inventory(game, world_name):
    _write_json(os.path.join(world_dir(world_name), "inventory.json"),
                game.player.inventory.serialize())


def load_inventory(game, world_name):
    data = _read_json(os.path.join(world_dir(world_name), "inventory.json"))
    if data:
        game.player.inventory.deserialize(data)
    return data is not None


def save_modified_blocks(game, world_name):
    _write_json(os.path.join(world_dir(world_name), "modified_blocks.json"),
                game.world.modified_blocks)


def load_modified_blocks(game, world_name):
    data = _read_json(
        os.path.join(world_dir(world_name), "modified_blocks.json"), {})
    game.world.modified_blocks = {k: int(v) for k, v in (data or {}).items()}
    return bool(data)


def save_containers(game, world_name):
    _write_json(os.path.join(world_dir(world_name), "containers.json"),
                game.world.containers)


def load_containers(game, world_name):
    data = _read_json(
        os.path.join(world_dir(world_name), "containers.json"), {})
    game.world.containers = data or {}


def save_entities(game, world_name):
    _write_json(os.path.join(world_dir(world_name), "entities.json"), {
        "mobs": game.mobs.serialize(),
        "drops": game.drops.serialize(),
    })


def load_entities(game, world_name):
    data = _read_json(os.path.join(world_dir(world_name), "entities.json"))
    if data:
        game.mobs.deserialize(data.get("mobs"))
        game.drops.deserialize(data.get("drops"))


def save_world_meta(game, world_name):
    _write_json(os.path.join(world_dir(world_name), "world.json"), {
        "seed": game.world.seed,
        "time_of_day": game.time_system.time_of_day,
        "day_count": game.time_system.day_count,
        "weather": game.weather.kind,
        "weather_timer": game.weather.timer,
    })


def load_world_meta(world_name):
    return _read_json(os.path.join(world_dir(world_name), "world.json"))


# ---------------------------------------------------------------------------
# 전체 저장/불러오기
# ---------------------------------------------------------------------------
def save_game(game, world_name):
    """게임 전체 상태를 저장한다."""
    save_world_meta(game, world_name)
    save_player(game, world_name)
    save_inventory(game, world_name)
    save_modified_blocks(game, world_name)
    save_containers(game, world_name)
    save_entities(game, world_name)


def load_game(game, world_name):
    """저장된 상태를 game 객체에 적용한다 (world 생성 후 호출)."""
    meta = load_world_meta(world_name)
    if meta:
        game.time_system.time_of_day = float(meta.get("time_of_day", 0.3))
        game.time_system.day_count = int(meta.get("day_count", 0))
        game.weather.kind = meta.get("weather", "clear")
        game.weather.timer = float(meta.get("weather_timer", 60.0))
    load_modified_blocks(game, world_name)
    load_containers(game, world_name)
    load_player(game, world_name)
    load_inventory(game, world_name)
    load_entities(game, world_name)
    return meta


def world_exists(world_name):
    return os.path.exists(os.path.join(world_dir(world_name), "world.json"))


def list_worlds():
    """저장된 월드 이름 목록."""
    if not os.path.isdir(config.SAVE_DIR):
        return []
    result = []
    for name in sorted(os.listdir(config.SAVE_DIR)):
        if world_exists(name):
            result.append(name)
    return result


def read_world_seed(world_name):
    meta = load_world_meta(world_name)
    return meta.get("seed") if meta else None
