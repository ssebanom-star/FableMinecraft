"""
player.py - 1인칭 플레이어.

- 마우스 시점, WASD 이동, 점프/달리기/웅크리기, 크리에이티브 비행
- 체력/허기/스태미나/산소/경험치
- 레이캐스트 기반 블록 파괴(도구 속도/내구도 반영), 설치, 음식 섭취
- 낙하 피해, 익사, 접촉 피해 블록, 반발/미끄럼 블록
"""

import math
import random

from ursina import camera, mouse, held_keys

import blocks as B
import combat
import config
import items as I
import physics
from inventory import Inventory
from utils import voxel_raycast, clamp

EYE_HEIGHT = 1.62
WALK_SPEED = 4.3
SPRINT_SPEED = 6.2
CROUCH_SPEED = 1.8
FLY_SPEED = 10.0
JUMP_SPEED = 8.2


class Player:
    def __init__(self, game, position, mode="survival"):
        self.game = game
        self.position = list(position)
        self.body = physics.PhysicsBody(half_width=0.3, height=1.8)
        self.yaw = 0.0
        self.pitch = 0.0
        self.mode = mode

        # 상태
        self.max_health = 20.0
        self.health = 20.0
        self.max_hunger = 20.0
        self.hunger = 20.0
        self.max_stamina = 100.0
        self.stamina = 100.0
        self.max_oxygen = 100.0
        self.oxygen = 100.0
        self.xp = 0
        self.dead = False

        self.inventory = Inventory()
        self.spawn_point = list(position)

        # 진행 상태
        self.target_block = None       # 바라보는 블록 좌표
        self.target_prev = None        # 설치 위치
        self.break_progress = 0.0
        self.breaking_pos = None
        self.attack_cooldown = 0.0
        self.eat_timer = 0.0
        self.hunger_timer = 0.0
        self.regen_timer = 0.0
        self.damage_tick = 0.0
        self.prev_vy = 0.0

        camera.fov = float(config.get("fov"))

    # ------------------------------------------------------------------
    # 시점/방향
    # ------------------------------------------------------------------
    @property
    def eye_pos(self):
        return (self.position[0], self.position[1] + EYE_HEIGHT,
                self.position[2])

    @property
    def forward_dir(self):
        cy = math.radians(self.yaw)
        cp = math.radians(self.pitch)
        return (math.sin(cy) * math.cos(cp), -math.sin(cp),
                math.cos(cy) * math.cos(cp))

    def apply_camera(self):
        camera.position = self.eye_pos
        camera.rotation_x = self.pitch
        camera.rotation_y = self.yaw

    def update_look(self, dt):
        if not mouse.locked:
            return
        sens = float(config.get("mouse_sensitivity"))
        self.yaw += mouse.velocity[0] * sens
        self.pitch -= mouse.velocity[1] * sens * 1.4
        self.pitch = clamp(self.pitch, -89.0, 89.0)

    # ------------------------------------------------------------------
    # 이동
    # ------------------------------------------------------------------
    def update_movement(self, dt):
        cy = math.radians(self.yaw)
        fx, fz = math.sin(cy), math.cos(cy)
        rx, rz = math.cos(cy), -math.sin(cy)

        mx = held_keys['d'] - held_keys['a']
        mz = held_keys['w'] - held_keys['s']
        dx = fx * mz + rx * mx
        dz = fz * mz + rz * mx
        d = math.sqrt(dx * dx + dz * dz)
        if d > 1e-5:
            dx, dz = dx / d, dz / d

        sprinting = (held_keys['shift'] or held_keys['left shift']) \
            and mz > 0 and self.stamina > 1 and self.hunger > 6
        crouching = held_keys['control'] or held_keys['left control']

        if self.mode == "creative":
            speed = FLY_SPEED
            self.body.velocity[0] = dx * speed
            self.body.velocity[2] = dz * speed
            self.body.velocity[1] = 0.0
            if held_keys['space']:
                self.body.velocity[1] = FLY_SPEED
            if crouching:
                self.body.velocity[1] = -FLY_SPEED
        else:
            speed = SPRINT_SPEED if sprinting else \
                CROUCH_SPEED if crouching else WALK_SPEED
            if self.body.in_water:
                speed *= 0.55
            # 미끄러운 블록 위에서는 관성 유지 (slip=0 이면 즉시 반응)
            slip = physics.ground_friction(self.body) \
                if self.body.grounded else 0.0
            blend = 1.0 - slip
            self.body.velocity[0] = \
                self.body.velocity[0] * slip + dx * speed * blend
            self.body.velocity[2] = \
                self.body.velocity[2] * slip + dz * speed * blend

            if held_keys['space']:
                if self.body.in_water:
                    self.body.velocity[1] = 3.2   # 헤엄
                elif self.body.grounded:
                    self.body.velocity[1] = JUMP_SPEED

            physics.apply_gravity(self.body, dt, self.body.in_water)

            # 스태미나
            if sprinting and d > 0:
                self.stamina = max(0.0, self.stamina - 12.0 * dt)
            else:
                self.stamina = min(self.max_stamina,
                                   self.stamina + 8.0 * dt)

        self.prev_vy = self.body.velocity[1]
        self.position = physics.move_body(
            self.game.world, self.body, self.position, dt)

        # 낙하 피해 / 반발 블록
        if self.body.grounded and self.prev_vy < -12.0:
            bounce = physics.ground_bounciness(self.body)
            if bounce > 0:
                self.body.velocity[1] = -self.prev_vy * bounce
            elif self.mode == "survival" and not self.body.in_water:
                dmg = int((-self.prev_vy - 12.0) * 0.7)
                if dmg > 0:
                    self.take_damage(dmg)

        # 월드 밖 추락
        if self.position[1] < -12:
            if self.mode == "survival":
                self.take_damage(4)
            self.position[1] = float(config.WORLD_HEIGHT)
            self.body.velocity[1] = 0

    # ------------------------------------------------------------------
    # 생존 스탯
    # ------------------------------------------------------------------
    def update_survival(self, dt):
        if self.mode != "survival" or self.dead:
            return

        # 허기 자연 감소
        self.hunger_timer += dt
        if self.hunger_timer >= 24.0:
            self.hunger_timer = 0.0
            self.hunger = max(0.0, self.hunger - 1.0)

        # 허기에 따른 회복/피해
        self.damage_tick += dt
        if self.hunger >= 16 and self.health < self.max_health:
            self.regen_timer += dt
            if self.regen_timer >= 3.0:
                self.regen_timer = 0.0
                self.health = min(self.max_health, self.health + 1.0)
        elif self.hunger <= 0 and self.damage_tick >= 3.0:
            self.damage_tick = 0.0
            self.take_damage(1)

        # 산소
        if self.body.head_in_water:
            self.oxygen = max(0.0, self.oxygen - 8.0 * dt)
            if self.oxygen <= 0 and self.damage_tick >= 1.5:
                self.damage_tick = 0.0
                self.take_damage(2)   # 익사
        else:
            self.oxygen = min(self.max_oxygen, self.oxygen + 25.0 * dt)

        # 접촉 피해 블록 (선인장/가시)
        dmg = physics.touching_damage_block(
            self.game.world, self.position,
            self.body.half_width, self.body.height)
        if dmg > 0 and self.damage_tick >= 0.8:
            self.damage_tick = 0.0
            self.take_damage(dmg)

    def take_damage(self, amount):
        if self.mode == "creative" or self.dead:
            return
        self.health -= amount
        if self.health <= 0:
            self.health = 0
            self.die()

    def heal(self, amount):
        self.health = min(self.max_health, self.health + amount)

    def gain_xp(self, amount):
        self.xp += amount

    def die(self):
        """사망: 아이템 일부 드롭 후 사망 화면."""
        self.dead = True
        inv = self.inventory
        for i, stack in enumerate(inv.slots):
            if stack and random.random() < 0.4:   # 일부만 드롭
                self.game.drops.spawn_stack(
                    stack, (self.position[0], self.position[1] + 1,
                            self.position[2]))
                inv.slots[i] = None
        self.game.on_player_death()

    def respawn(self):
        self.position = list(self.spawn_point)
        self.body.velocity = [0.0, 0.0, 0.0]
        self.health = self.max_health
        self.hunger = self.max_hunger
        self.stamina = self.max_stamina
        self.oxygen = self.max_oxygen
        self.dead = False

    # ------------------------------------------------------------------
    # 레이캐스트 / 블록 상호작용
    # ------------------------------------------------------------------
    def update_target(self):
        world = self.game.world

        def _hit(x, y, z):
            bid = world.get_block(x, y, z)
            return bid != B.AIR and not B.BLOCKS[bid].is_liquid

        self.target_block, self.target_prev = voxel_raycast(
            self.eye_pos, self.forward_dir, config.PLAYER_REACH, _hit)

    def _mining_speed_for(self, bdef):
        """현재 도구 기준 파괴 시간 (초). 드롭 가능 여부도 반환."""
        stack = self.inventory.get_selected_item()
        item = I.get_item(stack["id"]) if stack else None
        speed = 1.0
        tool_level = 0
        if item and item.tool_type:
            tool_level = item.tool_level
            if item.tool_type == bdef.required_tool:
                speed = item.mining_speed
        # 필요한 도구 등급 미달이면 드롭 없음 + 채굴 느림
        can_drop = tool_level >= bdef.required_tool_level
        break_time = bdef.break_time / speed
        if not can_drop:
            break_time *= 3.0
        return break_time, can_drop

    def update_breaking(self, dt):
        """좌클릭 유지: 몹 공격 또는 블록 파괴."""
        self.attack_cooldown = max(0.0, self.attack_cooldown - dt)
        if not mouse.locked or not held_keys['left mouse']:
            self.break_progress = 0.0
            self.breaking_pos = None
            return

        # 1) 시선의 몹 공격
        mob = self.game.mobs.mob_near_player_ray(
            self.eye_pos, self.forward_dir, max_dist=3.5)
        if mob is not None:
            if self.attack_cooldown <= 0:
                stack = self.inventory.get_selected_item()
                item = I.get_item(stack["id"]) if stack else None
                self.attack_cooldown = 1.0 / (item.attack_speed if item
                                              else 2.5)
                combat.player_attack_mob(self, mob, self.game)
            self.break_progress = 0.0
            return

        # 2) 블록 파괴
        if self.target_block is None:
            self.break_progress = 0.0
            self.breaking_pos = None
            return
        x, y, z = self.target_block
        bid = self.game.world.get_block(x, y, z)
        if bid == B.AIR:
            return
        bdef = B.BLOCKS[bid]
        if bdef.hardness < 0 and self.mode != "creative":
            return   # 기반암 등 파괴 불가

        if self.breaking_pos != self.target_block:
            self.breaking_pos = self.target_block
            self.break_progress = 0.0

        if self.mode == "creative":
            self.finish_break(x, y, z, bdef, drops=False)
            return

        break_time, can_drop = self._mining_speed_for(bdef)
        self.break_progress += dt / max(0.05, break_time)
        if self.break_progress >= 1.0:
            self.finish_break(x, y, z, bdef, drops=can_drop)

    def finish_break(self, x, y, z, bdef, drops=True):
        world = self.game.world
        world.set_block(x, y, z, B.AIR)
        self.break_progress = 0.0
        self.breaking_pos = None

        # 컨테이너 블록이면 내용물 드롭
        if bdef.id in (B.CHEST,):
            cont = world.containers.get(f"{x},{y},{z}")
            if cont:
                for s in cont.get("slots", []):
                    if s:
                        self.game.drops.spawn_stack(
                            s, (x + 0.5, y + 0.5, z + 0.5))
                world.remove_container(x, y, z)
        elif bdef.id == B.FURNACE:
            cont = world.containers.get(f"{x},{y},{z}")
            if cont:
                for key in ("input", "fuel", "output"):
                    if cont.get(key):
                        self.game.drops.spawn_stack(
                            cont[key], (x + 0.5, y + 0.5, z + 0.5))
                world.remove_container(x, y, z)

        # 폭발 블록은 채굴 시 기폭
        if bdef.id == B.BOOM_BLOCK:
            combat.explode(self.game, (x + 0.5, y + 0.5, z + 0.5))
            return

        # 드롭 생성
        if drops and self.mode == "survival":
            for item_id, cnt, prob in bdef.drops:
                if random.random() < prob:
                    self.game.drops.spawn_item_drop(
                        item_id, cnt, (x + 0.5, y + 0.4, z + 0.5))
            # 도구 내구도
            stack = self.inventory.get_selected_item()
            item = I.get_item(stack["id"]) if stack else None
            if item and item.tool_type:
                self.inventory.damage_selected(1)

    # ------------------------------------------------------------------
    def try_place_block(self):
        """우클릭: 블록 설치 (플레이어와 겹치면 불가)."""
        if self.target_prev is None or self.target_block is None:
            return False
        stack = self.inventory.get_selected_item()
        item = I.get_item(stack["id"]) if stack else None
        if item is None or item.placeable_block_id is None:
            return False
        bdef = B.BLOCKS[item.placeable_block_id]
        x, y, z = self.target_prev
        if self.game.world.get_block(x, y, z) != B.AIR:
            return False

        # 플레이어 몸과 겹침 검사
        if bdef.collision_box:
            px, py, pz = self.position
            if (abs(x + 0.5 - px) < 0.8 + self.body.half_width and
                    abs(z + 0.5 - pz) < 0.8 + self.body.half_width and
                    py - 1 < y < py + self.body.height):
                return False

        self.game.world.set_block(x, y, z, bdef.id)
        if self.mode == "survival":
            self.inventory.consume_selected(1)
        return True

    def try_eat(self, dt):
        """우클릭 유지: 음식 섭취."""
        stack = self.inventory.get_selected_item()
        item = I.get_item(stack["id"]) if stack else None
        if item is None or item.food_value <= 0:
            self.eat_timer = 0.0
            return False
        if self.hunger >= self.max_hunger and not item.can_eat_when_full:
            self.eat_timer = 0.0
            return False
        self.eat_timer += dt
        if self.eat_timer >= item.eat_time:
            self.eat_timer = 0.0
            self.hunger = min(self.max_hunger,
                              self.hunger + item.food_value)
            if item.heal_value > 0:
                self.heal(item.heal_value)
            # 생고기는 낮은 확률로 배탈 (허기 추가 감소)
            if item.id in ("raw_meat", "raw_chicken") and \
                    random.random() < 0.3:
                self.hunger = max(0.0, self.hunger - 3.0)
            if self.mode == "survival":
                self.inventory.consume_selected(1)
        return True

    def try_shoot_bow(self):
        """활 발사 (화살 소모)."""
        stack = self.inventory.get_selected_item()
        item = I.get_item(stack["id"]) if stack else None
        if item is None or item.projectile_type != "arrow":
            return False
        if self.mode == "survival":
            if not self.inventory.remove_item("arrow", 1):
                return False
            self.inventory.damage_selected(1)
        arrow = I.get_item("arrow")
        self.game.projectiles.spawn(
            self.eye_pos, self.forward_dir, speed=30.0,
            damage=arrow.attack_damage, owner="player")
        return True

    # ------------------------------------------------------------------
    def update(self, dt):
        if self.dead:
            return
        self.update_look(dt)
        self.update_movement(dt)
        self.update_survival(dt)
        self.update_target()
        self.update_breaking(dt)

        # 우클릭 유지 = 음식 섭취
        if mouse.locked and held_keys['right mouse']:
            self.try_eat(dt)
        else:
            self.eat_timer = 0.0

        self.apply_camera()

    # ------------------------------------------------------------------
    # 저장/불러오기
    # ------------------------------------------------------------------
    def serialize(self):
        return {
            "position": self.position,
            "yaw": self.yaw, "pitch": self.pitch,
            "health": self.health, "hunger": self.hunger,
            "stamina": self.stamina, "oxygen": self.oxygen,
            "xp": self.xp, "mode": self.mode,
            "spawn_point": self.spawn_point,
        }

    def deserialize(self, data):
        self.position = list(data.get("position", self.position))
        self.yaw = float(data.get("yaw", 0.0))
        self.pitch = float(data.get("pitch", 0.0))
        self.health = float(data.get("health", 20.0))
        self.hunger = float(data.get("hunger", 20.0))
        self.stamina = float(data.get("stamina", 100.0))
        self.oxygen = float(data.get("oxygen", 100.0))
        self.xp = int(data.get("xp", 0))
        self.mode = data.get("mode", "survival")
        self.spawn_point = list(data.get("spawn_point", self.position))
