"""
mobs.py - 몹 정의와 스폰/관리.

- 수동 몹 5종 + 적대 몹 5종 (총 10종)
- 몸통+머리 두 개의 큐브로 렌더링 (블록당 Entity 금지 원칙과 무관한 소수 엔티티)
- AI 업데이트는 플레이어와의 거리로 제한한다.
"""

import math
import random

from ursina import Entity, Color, destroy

import ai
import blocks as B
import config
import physics
import terrain_generator as TG
from utils import dist_sq

# ---------------------------------------------------------------------------
# 몹 데이터 (id, 이름, 체력, 속도, 공격, 사거리, 감지, 드롭, 스폰 바이옴/시간, AI)
# drops: (item_id, 최소, 최대, 확률)
# ---------------------------------------------------------------------------
MOB_TYPES = {
    # --- 수동 몹 ---
    "pig": dict(
        name="돼지", health=10, speed=2.2, attack_damage=0, attack_range=0,
        detection_range=0, ai_type="passive",
        drops=[("raw_meat", 1, 2, 1.0)],
        spawn_biomes=("plains", "forest", "birch_forest", "swamp"),
        spawn_time="day", color=(0.92, 0.65, 0.65), size=(0.9, 0.8, 1.1),
    ),
    "cow": dict(
        name="소", health=12, speed=2.0, attack_damage=0, attack_range=0,
        detection_range=0, ai_type="passive",
        drops=[("raw_meat", 1, 3, 1.0), ("leather", 0, 2, 0.8)],
        spawn_biomes=("plains", "forest", "birch_forest"),
        spawn_time="day", color=(0.45, 0.32, 0.25), size=(0.95, 1.0, 1.3),
    ),
    "sheep": dict(
        name="양", health=8, speed=2.0, attack_damage=0, attack_range=0,
        detection_range=0, ai_type="passive",
        drops=[("raw_meat", 1, 2, 1.0), ("string", 1, 2, 0.9)],
        spawn_biomes=("plains", "mountains", "snow"),
        spawn_time="day", color=(0.92, 0.92, 0.92), size=(0.9, 0.9, 1.1),
    ),
    "chicken": dict(
        name="닭", health=4, speed=2.4, attack_damage=0, attack_range=0,
        detection_range=0, ai_type="passive",
        drops=[("raw_chicken", 1, 1, 1.0), ("feather", 0, 2, 0.9)],
        spawn_biomes=("plains", "forest", "birch_forest", "swamp"),
        spawn_time="day", color=(0.95, 0.93, 0.85), size=(0.5, 0.6, 0.6),
    ),
    "rabbit": dict(
        name="토끼", health=3, speed=3.4, attack_damage=0, attack_range=0,
        detection_range=0, ai_type="passive",
        drops=[("raw_meat", 0, 1, 0.6), ("leather", 0, 1, 0.4)],
        spawn_biomes=("plains", "desert", "snow", "beach"),
        spawn_time="day", color=(0.80, 0.72, 0.60), size=(0.45, 0.5, 0.6),
    ),
    # --- 적대 몹 ---
    "shambler": dict(
        name="괴인", health=20, speed=2.6, attack_damage=4, attack_range=1.6,
        detection_range=18, ai_type="hostile",
        drops=[("raw_meat", 0, 1, 0.4), ("string", 0, 1, 0.3)],
        spawn_biomes=("plains", "forest", "birch_forest", "swamp",
                      "desert", "snow", "mountains", "beach"),
        spawn_time="night", color=(0.35, 0.55, 0.35), size=(0.7, 1.8, 0.5),
        burns_in_day=True,
    ),
    "spinner": dict(
        name="독거미", health=14, speed=3.4, attack_damage=3, attack_range=1.5,
        detection_range=15, ai_type="hostile",
        drops=[("string", 1, 3, 1.0), ("spider_eye", 0, 1, 0.4)],
        spawn_biomes=("forest", "birch_forest", "swamp", "mountains"),
        spawn_time="night", color=(0.20, 0.18, 0.22), size=(1.1, 0.6, 1.1),
    ),
    "boneshot": dict(
        name="해골 사수", health=18, speed=2.4, attack_damage=4,
        attack_range=14, detection_range=18, ai_type="ranged",
        drops=[("bone", 1, 3, 1.0), ("arrow", 0, 3, 0.7)],
        spawn_biomes=("plains", "forest", "snow", "mountains", "desert"),
        spawn_time="night", color=(0.85, 0.85, 0.80), size=(0.6, 1.8, 0.4),
        burns_in_day=True,
    ),
    "boomer": dict(
        name="폭발 덩굴", health=16, speed=2.6, attack_damage=0,
        attack_range=2.5, detection_range=16, ai_type="exploder",
        drops=[("gunpowder", 1, 2, 1.0)],
        spawn_biomes=("plains", "forest", "birch_forest", "swamp",
                      "desert", "beach"),
        spawn_time="night", color=(0.30, 0.65, 0.30), size=(0.6, 1.6, 0.6),
    ),
    "crawler": dict(
        name="동굴 기어다니개", health=12, speed=3.8, attack_damage=3,
        attack_range=1.4, detection_range=14, ai_type="hostile",
        drops=[("coal", 0, 2, 0.6), ("glow_dust", 0, 1, 0.25)],
        spawn_biomes=("plains", "forest", "birch_forest", "swamp", "desert",
                      "snow", "mountains", "beach"),
        spawn_time="cave", color=(0.45, 0.40, 0.55), size=(0.8, 0.5, 0.8),
    ),
}

PASSIVE_TYPES = [k for k, v in MOB_TYPES.items() if v["ai_type"] == "passive"]
HOSTILE_TYPES = [k for k, v in MOB_TYPES.items() if v["ai_type"] != "passive"]


class Mob:
    def __init__(self, type_id, position):
        self.type_id = type_id
        self.type = MOB_TYPES[type_id]
        self.pos = list(position)
        w, h, d = self.type["size"]
        self.body = physics.PhysicsBody(half_width=max(w, d) * 0.5, height=h)
        self.health = self.type["health"]
        self.attack_cooldown = 0.0
        self.wander_timer = 0.0
        self.wander_dir = None
        self.flee_timer = 0.0
        self.fuse = 0.0
        self.flash_timer = 0.0
        self.hurt_timer = 0.0
        self.burn_timer = 0.0
        self.facing = 0.0
        self.silent_death = False
        self.dead = False

        c = self.type["color"]
        self.root = Entity(position=tuple(position))
        self.body_ent = Entity(
            parent=self.root, model='cube',
            color=Color(c[0], c[1], c[2], 1),
            scale=(w, h * 0.65, d), position=(0, h * 0.42, 0))
        self.head_ent = Entity(
            parent=self.root, model='cube',
            color=Color(min(1, c[0] * 1.15), min(1, c[1] * 1.15),
                        min(1, c[2] * 1.15), 1),
            scale=(w * 0.6, h * 0.35, w * 0.6),
            position=(0, h * 0.9, d * 0.25))

    # ------------------------------------------------------------------
    def tick(self, game, dt):
        # AI (거리 제한은 MobManager 가 결정)
        ai.AI_FUNCTIONS[self.type["ai_type"]](self, game, dt)

        physics.apply_gravity(self.body, dt, self.body.in_water)
        self.pos = physics.move_body(game.world, self.body, self.pos, dt)
        self.root.position = tuple(self.pos)
        self.root.rotation_y = self.facing

        # 피격 플래시 복구
        if self.hurt_timer > 0:
            self.hurt_timer -= dt
            if self.hurt_timer <= 0:
                self._reset_color()

        # 폭발형 점멸
        if self.fuse > 0 and int(self.flash_timer * 8) % 2 == 0:
            self.body_ent.color = Color(1, 1, 1, 1)
        elif self.fuse > 0:
            self._reset_color()

        # 낮에 불타는 몹 (비가 오면 타지 않음)
        if self.type.get("burns_in_day") and game.time_system.is_day() \
                and game.weather.kind not in ("rain", "storm"):
            if game.world.light_at(self.pos[0], self.pos[1] + 1,
                                   self.pos[2]) >= 14:
                self.burn_timer += dt
                if self.burn_timer >= 1.5:
                    self.burn_timer = 0.0
                    self.take_damage(2, game)

        # 접촉 피해 블록 / 낙사
        if self.pos[1] < -8:
            self.health = 0
            self.silent_death = True
        if self.health <= 0 and not self.dead:
            self.die(game)

    def _reset_color(self):
        c = self.type["color"]
        self.body_ent.color = Color(c[0], c[1], c[2], 1)

    # ------------------------------------------------------------------
    def take_damage(self, amount, game, source_pos=None):
        if self.dead:
            return
        self.health -= amount
        self.hurt_timer = 0.25
        self.body_ent.color = Color(1, 0.25, 0.25, 1)
        self.flee_timer = 5.0   # 수동 몹은 도망
        if source_pos is not None:
            import combat
            kb = combat.knockback_vector(source_pos, self.pos, 6.0)
            self.body.velocity[0] += kb[0]
            self.body.velocity[1] += kb[1]
            self.body.velocity[2] += kb[2]
        if self.health <= 0:
            self.die(game)

    def die(self, game):
        if self.dead:
            return
        self.dead = True
        # 드롭 테이블 (폭발 자폭 등 silent_death 는 드롭 없음)
        if not self.silent_death:
            for item_id, lo, hi, prob in self.type["drops"]:
                if random.random() < prob:
                    cnt = random.randint(lo, hi)
                    if cnt > 0:
                        game.drops.spawn_item_drop(
                            item_id, cnt,
                            (self.pos[0], self.pos[1] + 0.5, self.pos[2]))
        game.player.gain_xp(3 if self.type["ai_type"] != "passive" else 1)
        self.remove()

    def remove(self):
        destroy(self.root)

    def serialize(self):
        return {"type": self.type_id, "pos": self.pos, "health": self.health}


# ---------------------------------------------------------------------------
class MobManager:
    def __init__(self, world):
        self.world = world
        self.mobs = []
        self.spawn_timer = 0.0
        self.max_mobs = int(config.get("max_mobs"))
        self.update_distance = float(config.get("mob_update_distance"))
        self.enabled = bool(config.get("mob_spawning"))

    # ------------------------------------------------------------------
    def spawn_mob(self, type_id, position):
        mob = Mob(type_id, position)
        self.mobs.append(mob)
        return mob

    def try_spawn(self, game):
        """플레이어 주변 임의 위치에 조건이 맞으면 몹 스폰."""
        if not self.enabled or len(self.mobs) >= self.max_mobs:
            return
        player = game.player
        px, _, pz = player.position

        ang = random.uniform(0, math.tau)
        dist = random.uniform(16, 34)
        x = px + math.cos(ang) * dist
        z = pz + math.sin(ang) * dist

        # 지표면 찾기
        y = self.world.surface_height(x, z) + 1
        ground = self.world.get_block(math.floor(x), y - 1, math.floor(z))
        if ground not in B.SOLID_IDS:
            return
        if self.world.get_block(math.floor(x), y, math.floor(z)) != B.AIR:
            return

        biome = self.world.biome_at(x, z)
        weight = TG.BIOME_SPAWN_WEIGHT.get(biome, 1.0)
        if random.random() > weight:
            return

        is_day = game.time_system.is_day()
        light = self.world.light_at(x, y, z)
        storm_boost = 1.5 if game.weather.kind == "storm" else 1.0

        candidates = []
        for tid, t in MOB_TYPES.items():
            if biome not in t["spawn_biomes"]:
                continue
            st = t["spawn_time"]
            if st == "day" and (not is_day or light < 8):
                continue
            if st == "night" and is_day and light >= 8:
                continue
            if st == "cave" and light > 5:
                continue
            candidates.append(tid)
        if not candidates:
            return

        # 밤/폭풍에는 적대 몹 확률 증가
        hostile_bias = 0.75 * storm_boost if not is_day else 0.25
        hostiles = [c for c in candidates if c in HOSTILE_TYPES]
        passives = [c for c in candidates if c in PASSIVE_TYPES]
        if hostiles and random.random() < hostile_bias:
            tid = random.choice(hostiles)
        elif passives:
            tid = random.choice(passives)
        else:
            tid = random.choice(candidates)
        self.spawn_mob(tid, (x, y, z))

    # ------------------------------------------------------------------
    def update(self, game, dt):
        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            self.spawn_timer = 2.0
            self.try_spawn(game)

        px, py, pz = game.player.position
        limit2 = self.update_distance ** 2
        despawn2 = (self.update_distance * 1.8) ** 2
        for mob in list(self.mobs):
            d2 = dist_sq(mob.pos, (px, py, pz))
            if d2 > despawn2:
                mob.remove()
                self.mobs.remove(mob)
                continue
            if d2 <= limit2:     # AI 업데이트 거리 제한
                mob.tick(game, dt)
            if mob.dead:
                if mob in self.mobs:
                    self.mobs.remove(mob)

    def mob_near_player_ray(self, origin, direction, max_dist=4.0):
        """시선 방향의 몹 탐색 (근접 공격 대상)."""
        best, best_t = None, max_dist
        ox, oy, oz = origin
        dx, dy, dz = direction
        for mob in self.mobs:
            cx = mob.pos[0] - ox
            cy = (mob.pos[1] + mob.body.height * 0.5) - oy
            cz = mob.pos[2] - oz
            t = cx * dx + cy * dy + cz * dz     # 시선 방향 투영 거리
            if t < 0 or t > best_t:
                continue
            # 시선과 몹 중심의 수직 거리
            perp2 = (cx - dx * t) ** 2 + (cy - dy * t) ** 2 + \
                (cz - dz * t) ** 2
            if perp2 < (mob.body.half_width + 0.55) ** 2:
                best, best_t = mob, t
        return best

    def clear(self):
        for mob in self.mobs:
            mob.remove()
        self.mobs.clear()

    # ------------------------------------------------------------------
    def serialize(self):
        return [m.serialize() for m in self.mobs]

    def deserialize(self, data):
        self.clear()
        for entry in data or []:
            if entry.get("type") in MOB_TYPES:
                mob = self.spawn_mob(entry["type"], entry["pos"])
                mob.health = entry.get("health", mob.health)
