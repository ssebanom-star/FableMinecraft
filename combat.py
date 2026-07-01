"""
combat.py - 전투 시스템.

- 플레이어 근접 공격 / 몹 피격 / 넉백 / 방어구 피해 감소
- 투사체 (화살 등)
- 폭발 (블록 파괴 + 범위 피해)
"""

import math
import random

from ursina import Entity, Color, destroy

import blocks as B
import items as I
from utils import dist_sq


def knockback_vector(from_pos, to_pos, strength=6.0):
    """from_pos -> to_pos 방향의 넉백 속도 벡터."""
    dx = to_pos[0] - from_pos[0]
    dz = to_pos[2] - from_pos[2]
    d = math.sqrt(dx * dx + dz * dz)
    if d < 1e-5:
        ang = random.uniform(0, math.tau)
        dx, dz, d = math.cos(ang), math.sin(ang), 1.0
    return [dx / d * strength, strength * 0.55, dz / d * strength]


def player_attack_mob(player, mob, game):
    """플레이어가 몹을 근접 공격한다."""
    stack = player.inventory.get_selected_item()
    item = I.get_item(stack["id"]) if stack else None
    damage = item.attack_damage if item else 1
    mob.take_damage(damage, game, source_pos=player.position)
    # 무기 내구도 감소 (무기/도구만)
    if item and item.max_durability > 0 and \
            item.category in ("weapon", "tool"):
        player.inventory.damage_selected(1)


def damage_player(player, amount, source_pos=None):
    """플레이어 피격 (방어구 감소 + 넉백 + 장비 내구도)."""
    if player.mode == "creative" or amount <= 0:
        return
    armor = player.inventory.total_armor()
    reduced = max(1, amount - armor * 0.5) if amount > 0 else 0
    player.take_damage(reduced)
    player.inventory.damage_armor(1)
    if source_pos is not None:
        kb = knockback_vector(source_pos, player.position, 5.0)
        player.body.velocity[0] += kb[0]
        player.body.velocity[1] += kb[1] * 0.6
        player.body.velocity[2] += kb[2]


# ---------------------------------------------------------------------------
# 투사체
# ---------------------------------------------------------------------------
class Projectile:
    """화살 등 직선 + 중력 투사체."""

    def __init__(self, position, direction, speed=24.0, damage=5,
                 owner="player", color=(0.75, 0.72, 0.68)):
        self.pos = list(position)
        d = math.sqrt(sum(c * c for c in direction)) or 1.0
        self.vel = [direction[0] / d * speed,
                    direction[1] / d * speed,
                    direction[2] / d * speed]
        self.damage = damage
        self.owner = owner          # "player" 또는 몹 참조
        self.age = 0.0
        self.dead = False
        self.entity = Entity(model='cube', scale=(0.08, 0.08, 0.4),
                             color=Color(*color, 1), position=tuple(position))

    def tick(self, game, dt):
        if self.dead:
            return
        self.age += dt
        if self.age > 8.0:
            self.kill()
            return
        self.vel[1] -= 14.0 * dt
        nx = self.pos[0] + self.vel[0] * dt
        ny = self.pos[1] + self.vel[1] * dt
        nz = self.pos[2] + self.vel[2] * dt

        # 블록 충돌
        bid = game.world.get_block(math.floor(nx), math.floor(ny),
                                   math.floor(nz))
        if bid in B.SOLID_IDS:
            self.kill()
            return

        self.pos = [nx, ny, nz]
        self.entity.position = tuple(self.pos)
        self.entity.look_at(
            (nx + self.vel[0], ny + self.vel[1], nz + self.vel[2]))

        # 대상 충돌
        if self.owner == "player":
            for mob in game.mobs.mobs:
                cx, cy, cz = mob.pos
                if dist_sq(self.pos, (cx, cy + mob.body.height * 0.5,
                                      cz)) < 0.8:
                    mob.take_damage(self.damage, game, source_pos=self.pos)
                    self.kill()
                    return
        else:
            p = game.player
            px, py, pz = p.position
            if dist_sq(self.pos, (px, py + 0.9, pz)) < 0.8:
                damage_player(p, self.damage, source_pos=self.pos)
                self.kill()
                return

    def kill(self):
        self.dead = True
        destroy(self.entity)


class ProjectileManager:
    def __init__(self):
        self.projectiles = []

    def spawn(self, *args, **kwargs):
        p = Projectile(*args, **kwargs)
        self.projectiles.append(p)
        return p

    def update(self, game, dt):
        for p in self.projectiles:
            p.tick(game, dt)
        self.projectiles = [p for p in self.projectiles if not p.dead]

    def clear(self):
        for p in self.projectiles:
            p.kill()
        self.projectiles.clear()


# ---------------------------------------------------------------------------
# 폭발
# ---------------------------------------------------------------------------
def explode(game, position, radius=3.5, max_damage=14, break_blocks=True):
    """폭발: 범위 내 블록 파괴 + 엔티티 피해 + 넉백."""
    ex, ey, ez = position
    world = game.world

    if break_blocks:
        r = int(math.ceil(radius))
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                for dz in range(-r, r + 1):
                    if dx * dx + dy * dy + dz * dz > radius * radius:
                        continue
                    bx, by, bz = int(ex + dx), int(ey + dy), int(ez + dz)
                    bid = world.get_block(bx, by, bz)
                    if bid == B.AIR:
                        continue
                    bdef = B.BLOCKS[bid]
                    if bdef.hardness < 0 or bdef.hardness > 10:
                        continue  # 기반암/흑암은 폭발 면역
                    world.set_block(bx, by, bz, B.AIR)
                    # 연쇄 폭발
                    if bid == B.BOOM_BLOCK:
                        explode(game, (bx + 0.5, by + 0.5, bz + 0.5),
                                radius * 0.8, max_damage)
                        continue
                    # 일부 블록은 아이템 드롭 (30%)
                    if random.random() < 0.3:
                        for item_id, cnt, prob in bdef.drops:
                            if random.random() < prob:
                                game.drops.spawn_item_drop(
                                    item_id, cnt,
                                    (bx + 0.5, by + 0.5, bz + 0.5))

    # 엔티티 피해 (거리 감쇠)
    def _apply(target_pos, apply_fn, body=None):
        d2 = dist_sq(position, target_pos)
        if d2 > (radius * 1.5) ** 2:
            return
        falloff = max(0.0, 1.0 - math.sqrt(d2) / (radius * 1.5))
        dmg = int(max_damage * falloff)
        if dmg > 0:
            apply_fn(dmg)
        if body is not None:
            kb = knockback_vector(position, target_pos, 8.0 * falloff)
            body.velocity[0] += kb[0]
            body.velocity[1] += kb[1]
            body.velocity[2] += kb[2]

    p = game.player
    _apply(list(p.position), lambda d: damage_player(p, d, position), p.body)
    for mob in list(game.mobs.mobs):
        _apply(mob.pos,
               lambda d, m=mob: m.take_damage(d, game, source_pos=position),
               mob.body)
