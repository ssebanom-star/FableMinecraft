"""
drops.py - 드롭 아이템 엔티티와 관리자.

- 블록 파괴/몹 사망 시 spawn_item_drop() 으로 생성
- 중력 적용, 일정 시간 후 소멸, 근처 드롭끼리 병합
- 플레이어가 접근하면 자동 획득 (인벤토리 공간 필요)
"""

import math
import random

from ursina import Entity, Color, destroy

import config
import items as I
import physics
from utils import dist_sq

PICKUP_RANGE = 1.6
MERGE_RANGE = 1.0
PICKUP_DELAY = 0.6


class ItemDrop:
    """월드에 떨어진 아이템."""

    def __init__(self, stack, position, velocity=None):
        self.stack = stack
        self.pos = list(position)
        self.body = physics.PhysicsBody(half_width=0.12, height=0.25)
        if velocity:
            self.body.velocity = list(velocity)
        else:
            ang = random.uniform(0, math.tau)
            self.body.velocity = [math.cos(ang) * 1.5, 3.0,
                                  math.sin(ang) * 1.5]
        self.age = 0.0
        self.pickup_delay = PICKUP_DELAY
        self.lifetime = float(config.get("item_drop_lifetime"))
        item = I.get_item(stack["id"])
        col = item.color if item else (0.8, 0.8, 0.8)
        self.entity = Entity(
            model='cube', scale=0.28,
            color=Color(col[0], col[1], col[2], 1),
            position=(self.pos[0], self.pos[1] + 0.15, self.pos[2]),
        )

    def tick(self, world, dt):
        self.age += dt
        if self.pickup_delay > 0:
            self.pickup_delay -= dt
        physics.apply_gravity(self.body, dt, self.body.in_water)
        # 수평 감속
        self.body.velocity[0] *= 0.92
        self.body.velocity[2] *= 0.92
        self.pos = physics.move_body(world, self.body, self.pos, dt)
        self.entity.position = (self.pos[0], self.pos[1] + 0.15, self.pos[2])
        self.entity.rotation_y += dt * 90

    def remove(self):
        destroy(self.entity)

    def serialize(self):
        return {"stack": self.stack, "pos": self.pos, "age": self.age}


class DropManager:
    def __init__(self, world):
        self.world = world
        self.drops = []
        self.max_drops = int(config.get("max_item_drops"))

    # ------------------------------------------------------------------
    def spawn_item_drop(self, item_id, count, position, velocity=None):
        """item_id/count 로 드롭 생성 (count 는 스택 하나로)."""
        stack = I.make_stack(item_id, count)
        if stack is None:
            return None
        return self.spawn_stack(stack, position, velocity)

    def spawn_stack(self, stack, position, velocity=None):
        """스택(내구도 포함)을 그대로 드롭."""
        if stack is None or stack.get("count", 0) <= 0:
            return None
        # 드롭 수 제한: 가장 오래된 것 제거
        if len(self.drops) >= self.max_drops:
            oldest = max(self.drops, key=lambda d: d.age)
            oldest.remove()
            self.drops.remove(oldest)
        drop = ItemDrop(stack, position, velocity)
        self.drops.append(drop)
        return drop

    # ------------------------------------------------------------------
    def pickup_nearby_items(self, player):
        """플레이어 근처 드롭을 인벤토리에 넣는다."""
        px, py, pz = player.position
        for drop in list(self.drops):
            if drop.pickup_delay > 0:
                continue
            if dist_sq(drop.pos, (px, py, pz)) > PICKUP_RANGE ** 2:
                continue
            left = player.inventory.add_stack(drop.stack)
            if left == 0:
                drop.remove()
                self.drops.remove(drop)
            else:
                drop.stack["count"] = left

    def merge_nearby_drops(self):
        """같은 아이템 드롭끼리 가까우면 병합."""
        for i, a in enumerate(self.drops):
            if a.stack is None:
                continue
            for b in self.drops[i + 1:]:
                if b.stack is None or not I.can_merge(a.stack, b.stack):
                    continue
                if dist_sq(a.pos, b.pos) > MERGE_RANGE ** 2:
                    continue
                space = I.stack_max(a.stack) - a.stack["count"]
                take = min(space, b.stack["count"])
                if take > 0:
                    a.stack["count"] += take
                    b.stack["count"] -= take
        for drop in [d for d in self.drops
                     if d.stack and d.stack["count"] <= 0]:
            drop.remove()
            self.drops.remove(drop)

    def remove_expired_drops(self):
        for drop in [d for d in self.drops if d.age >= d.lifetime]:
            drop.remove()
            self.drops.remove(drop)

    # ------------------------------------------------------------------
    def update(self, dt, player):
        for drop in self.drops:
            drop.tick(self.world, dt)
        self.pickup_nearby_items(player)
        self.merge_nearby_drops()
        self.remove_expired_drops()

    def clear(self):
        for drop in self.drops:
            drop.remove()
        self.drops.clear()

    # ------------------------------------------------------------------
    def serialize(self):
        return [d.serialize() for d in self.drops]

    def deserialize(self, data):
        self.clear()
        for entry in data or []:
            drop = self.spawn_stack(entry["stack"], entry["pos"],
                                    velocity=[0, 0, 0])
            if drop:
                drop.age = float(entry.get("age", 0.0))
