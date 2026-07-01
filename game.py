"""
game.py - 게임 상태 총괄 (월드/플레이어/몹/드롭/시간/날씨/저장 연결).

메인 루프는 main.py 의 컨트롤러 엔티티가 game.update(dt)/game.input(key)
를 호출하는 구조다.
"""

import math
import random

from ursina import window, mouse, scene, Color

import blocks as B
import config
import furnace as F
import save_system
from combat import ProjectileManager
from drops import DropManager
from mobs import MobManager
from player import Player
from terrain_generator import biome_display_name
from world import World
from utils import set_mouse_locked


# ---------------------------------------------------------------------------
# 시간 시스템 (낮과 밤)
# ---------------------------------------------------------------------------
class TimeSystem:
    """time_of_day: 0.0~1.0 (0.0 = 06:00 아침, 0.5 = 18:00 저녁)."""

    def __init__(self):
        self.time_of_day = 0.05
        self.day_count = 1
        self.day_length = float(config.get("day_length"))

    def update(self, dt):
        self.time_of_day += dt / self.day_length
        if self.time_of_day >= 1.0:
            self.time_of_day -= 1.0
            self.day_count += 1

    def is_day(self):
        return self.time_of_day < 0.5

    def brightness(self):
        """전체 밝기 0.22(밤) ~ 1.0(낮), 새벽/황혼 부드러운 전환."""
        t = self.time_of_day
        if t < 0.45:
            b = 1.0
        elif t < 0.55:                      # 황혼
            b = 1.0 - (t - 0.45) / 0.10 * 0.78
        elif t < 0.95:                      # 밤
            b = 0.22
        else:                               # 새벽
            b = 0.22 + (t - 0.95) / 0.05 * 0.78
        return b * float(config.get("brightness"))

    def clock_string(self):
        """06:00 기준 24시간 시계 문자열."""
        hours = (self.time_of_day * 24.0 + 6.0) % 24.0
        h = int(hours)
        m = int((hours - h) * 60)
        return f"{self.day_count}일차 {h:02d}:{m:02d}"


# ---------------------------------------------------------------------------
# 날씨 시스템
# ---------------------------------------------------------------------------
class Weather:
    KINDS = ("clear", "rain", "snow", "fog", "storm")
    WEIGHTS = (0.55, 0.18, 0.08, 0.12, 0.07)
    BRIGHTNESS = {"clear": 1.0, "rain": 0.75, "snow": 0.85,
                  "fog": 0.8, "storm": 0.55}

    def __init__(self):
        self.kind = "clear"
        self.timer = random.uniform(90, 180)

    def update(self, dt):
        self.timer -= dt
        if self.timer <= 0:
            self.kind = random.choices(self.KINDS, self.WEIGHTS)[0]
            self.timer = random.uniform(60, 240)
            return True
        return False

    def brightness_modifier(self):
        return self.BRIGHTNESS.get(self.kind, 1.0)

    def display_for_biome(self, biome):
        """설원 바이옴에서는 비가 눈으로 표시된다."""
        if self.kind == "rain" and biome == "snow":
            return "눈"
        return {"clear": "맑음", "rain": "비", "snow": "눈",
                "fog": "안개", "storm": "폭풍"}.get(self.kind, self.kind)

    def fog_density(self):
        return {"fog": 0.035, "storm": 0.02, "rain": 0.012,
                "snow": 0.012}.get(self.kind, 0.0)


# ---------------------------------------------------------------------------
# 게임 본체
# ---------------------------------------------------------------------------
class Game:
    def __init__(self, world_name, seed=None, mode=None, load_existing=False):
        self.world_name = world_name
        self.paused = False
        self.debug_visible = False
        self.time_system = TimeSystem()
        self.weather = Weather()

        if load_existing:
            saved_seed = save_system.read_world_seed(world_name)
            seed = saved_seed if saved_seed is not None else seed
        if seed is None or seed == 0:
            seed = random.randint(1, 2 ** 31 - 1)

        self.world = World(seed)
        self.drops = DropManager(self.world)
        self.mobs = MobManager(self.world)
        self.projectiles = ProjectileManager()

        # 저장된 블록 변경을 청크 생성 전에 로드해야 지형에 반영된다
        if load_existing:
            save_system.load_modified_blocks(self, world_name)
            save_system.load_containers(self, world_name)

        spawn = self.world.find_spawn_point()
        self.player = Player(self, spawn,
                             mode=mode or config.get("start_mode"))

        if load_existing:
            meta = save_system.load_world_meta(world_name)
            if meta:
                self.time_system.time_of_day = float(
                    meta.get("time_of_day", 0.05))
                self.time_system.day_count = int(meta.get("day_count", 1))
                self.weather.kind = meta.get("weather", "clear")
                self.weather.timer = float(meta.get("weather_timer", 90.0))
            save_system.load_player(self, world_name)
            save_system.load_inventory(self, world_name)

        # 초기 청크 동기 로드 (플레이어 주변)
        px, _, pz = self.player.position
        self.world.load_chunks_around_player(px, pz, budget=999)
        self.world.rebuild_dirty_chunks(px, pz, budget=999)

        # 스폰 지점이 지형 속이면 위로 올린다
        self._fix_spawn_position()

        if load_existing:
            save_system.load_entities(self, world_name)

        self.ambient_applied = -1.0
        self.unload_timer = 0.0
        self.autosave_timer = float(config.get("autosave_interval"))
        self.ui = None   # main.py 에서 GameUI 연결

        set_mouse_locked(True)

    # ------------------------------------------------------------------
    def _fix_spawn_position(self):
        px, py, pz = self.player.position
        x, z = math.floor(px), math.floor(pz)
        h = self.world.surface_height(px, pz)
        if py < h + 1:
            self.player.position[1] = h + 1.5
        if not self.player.spawn_point:
            self.player.spawn_point = list(self.player.position)

    # ------------------------------------------------------------------
    def update(self, dt):
        if self.paused or dt <= 0:
            return
        dt = min(dt, 0.1)   # 프레임 급락 시 물리 폭주 방지

        # 시간/날씨
        self.time_system.update(dt)
        self.weather.update(dt)
        self._apply_sky()

        if not self.player.dead:
            self.player.update(dt)

        # 청크 스트리밍
        px, _, pz = self.player.position
        self.world.load_chunks_around_player(px, pz, budget=1)
        self.world.rebuild_dirty_chunks(px, pz, budget=2)
        self.unload_timer -= dt
        if self.unload_timer <= 0:
            self.unload_timer = 3.0
            self.world.unload_far_chunks(px, pz)

        # 엔티티
        self.drops.update(dt, self.player)
        self.mobs.update(self, dt)
        self.projectiles.update(self, dt)

        # 화로 갱신 (로드된 컨테이너 전체)
        for cont in self.world.containers.values():
            if cont.get("type") == "furnace":
                F.update_furnace(cont, dt)

        # 자동 저장
        self.autosave_timer -= dt
        if self.autosave_timer <= 0:
            self.autosave_timer = float(config.get("autosave_interval"))
            self.save()

        if self.ui:
            self.ui.update_hud(dt)

    # ------------------------------------------------------------------
    def _apply_sky(self):
        b = self.time_system.brightness() * \
            self.weather.brightness_modifier()
        # 청크 틴트는 변화가 충분할 때만 (전체 순회 비용)
        if abs(b - self.ambient_applied) > 0.02:
            self.ambient_applied = b
            self.world.set_ambient(max(0.18, b))

        # 하늘색
        day_sky = (0.45, 0.70, 0.95)
        night_sky = (0.03, 0.04, 0.10)
        t = max(0.0, min(1.0, (b - 0.22) / 0.78))
        sky = tuple(night_sky[i] + (day_sky[i] - night_sky[i]) * t
                    for i in range(3))
        wm = self.weather.brightness_modifier()
        window.color = Color(sky[0] * wm, sky[1] * wm, sky[2] * wm, 1)

        # 안개
        density = self.weather.fog_density()
        scene.fog_color = Color(sky[0], sky[1], sky[2], 1)
        scene.fog_density = density

    # ------------------------------------------------------------------
    # 상호작용 (우클릭)
    # ------------------------------------------------------------------
    def interact(self):
        """우클릭/F: 상호작용 블록 > 활 > 블록 설치."""
        p = self.player
        if p.target_block is not None:
            x, y, z = p.target_block
            bid = self.world.get_block(x, y, z)
            if bid == B.WORKBENCH:
                self.ui.open_workbench()
                return True
            if bid == B.FURNACE:
                state = self.world.get_container(x, y, z, "furnace")
                self.ui.open_furnace(state)
                return True
            if bid == B.CHEST:
                state = self.world.get_container(x, y, z, "chest")
                self.ui.open_chest(state)
                return True
            if bid == B.DOOR:
                self.world.set_block(x, y, z, B.DOOR_OPEN)
                return True
            if bid == B.DOOR_OPEN:
                self.world.set_block(x, y, z, B.DOOR)
                return True
        if p.try_shoot_bow():
            return True
        return p.try_place_block()

    # ------------------------------------------------------------------
    # 입력 (컨트롤러에서 위임)
    # ------------------------------------------------------------------
    def input(self, key):
        if self.player.dead:
            return
        ui_open = self.ui and self.ui.screen_open()

        if key == 'escape':
            if ui_open:
                self.ui.close_screen()
            else:
                self.ui.toggle_pause()
            return
        if self.paused:
            return

        if key == 'e':
            if ui_open:
                self.ui.close_screen()
            else:
                self.ui.open_inventory()
            return
        if ui_open:
            return

        if key in '123456789':
            self.player.inventory.selected_index = int(key) - 1
        elif key == 'scroll down':
            self.player.inventory.selected_index = \
                (self.player.inventory.selected_index + 1) % 9
        elif key == 'scroll up':
            self.player.inventory.selected_index = \
                (self.player.inventory.selected_index - 1) % 9
        elif key == 'q':
            dropped = self.player.inventory.drop_selected_item()
            if dropped:
                fx, fy, fz = self.player.forward_dir
                ex, ey, ez = self.player.eye_pos
                self.drops.spawn_stack(
                    dropped, (ex + fx, ey - 0.3, ez + fz),
                    velocity=[fx * 5, 2.0, fz * 5])
        elif key == 'c':
            self.player.mode = "creative" \
                if self.player.mode == "survival" else "survival"
        elif key == 'f3':
            self.debug_visible = not self.debug_visible
        elif key in ('right mouse down', 'f'):
            self.interact()

    # ------------------------------------------------------------------
    def on_player_death(self):
        if self.ui:
            self.ui.show_death_screen()

    def respawn_player(self):
        self.player.respawn()
        if self.ui:
            self.ui.hide_death_screen()
        set_mouse_locked(True)

    # ------------------------------------------------------------------
    def save(self):
        save_system.save_game(self, self.world_name)

    def current_biome(self):
        px, _, pz = self.player.position
        return biome_display_name(self.world.biome_at(px, pz))

    def shutdown(self):
        """게임 종료 정리 (메뉴로 복귀용)."""
        self.save()
        for chunk in list(self.world.chunks.values()):
            chunk.destroy_entities()
        self.world.chunks.clear()
        self.drops.clear()
        self.mobs.clear()
        self.projectiles.clear()
        scene.fog_density = 0.0
        set_mouse_locked(False)
