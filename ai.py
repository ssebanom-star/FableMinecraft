"""
ai.py - 몹 AI 행동 로직.

ai_type 별 행동:
- passive : 랜덤 배회, 플레이어가 너무 가깝거나 맞으면 도망
- hostile : 플레이어 추적, 근접 공격
- ranged  : 거리를 유지하며 투사체 발사
- exploder: 접근 후 도화선 점화, 폭발
"""

import math
import random

import combat
from utils import dist_sq


def _steer(mob, dx, dz, dt, speed_mult=1.0):
    """수평 방향으로 이동 + 벽에 막히면 점프."""
    d = math.sqrt(dx * dx + dz * dz)
    if d < 1e-5:
        return
    speed = mob.type["speed"] * speed_mult
    mob.body.velocity[0] = dx / d * speed
    mob.body.velocity[2] = dz / d * speed
    mob.facing = math.degrees(math.atan2(dx, dz))
    if mob.body.hit_wall and mob.body.grounded:
        mob.body.velocity[1] = 8.0
    if mob.body.in_water:
        mob.body.velocity[1] = max(mob.body.velocity[1], 2.0)


def _stop(mob):
    mob.body.velocity[0] *= 0.6
    mob.body.velocity[2] *= 0.6


def _dir_to_player(mob, player):
    px, _, pz = player.position
    return px - mob.pos[0], pz - mob.pos[2]


# ---------------------------------------------------------------------------
def passive_ai(mob, game, dt):
    player = game.player
    dx, dz = _dir_to_player(mob, player)
    d2 = dx * dx + dz * dz

    # 도망 (맞았거나 플레이어가 매우 가까움)
    if mob.flee_timer > 0 or d2 < 2.5 ** 2:
        mob.flee_timer = max(0.0, mob.flee_timer - dt)
        _steer(mob, -dx, -dz, dt, speed_mult=1.4)
        return

    # 랜덤 배회
    mob.wander_timer -= dt
    if mob.wander_timer <= 0:
        mob.wander_timer = random.uniform(2.0, 6.0)
        if random.random() < 0.55:
            ang = random.uniform(0, math.tau)
            mob.wander_dir = (math.cos(ang), math.sin(ang))
        else:
            mob.wander_dir = None
    if mob.wander_dir:
        _steer(mob, mob.wander_dir[0], mob.wander_dir[1], dt, 0.5)
    else:
        _stop(mob)


# ---------------------------------------------------------------------------
def hostile_ai(mob, game, dt):
    player = game.player
    if player.dead:
        _stop(mob)
        return
    dx, dz = _dir_to_player(mob, player)
    d2 = dist_sq(mob.pos, list(player.position))

    detect = mob.type["detection_range"]
    if d2 > detect ** 2:
        passive_ai(mob, game, dt)   # 감지 밖에서는 배회
        return

    attack_range = mob.type["attack_range"]
    if d2 <= attack_range ** 2:
        _stop(mob)
        mob.attack_cooldown -= dt
        if mob.attack_cooldown <= 0:
            mob.attack_cooldown = 1.2
            combat.damage_player(player, mob.type["attack_damage"],
                                 source_pos=mob.pos)
    else:
        _steer(mob, dx, dz, dt)


# ---------------------------------------------------------------------------
def ranged_ai(mob, game, dt):
    player = game.player
    if player.dead:
        _stop(mob)
        return
    dx, dz = _dir_to_player(mob, player)
    d2 = dist_sq(mob.pos, list(player.position))
    detect = mob.type["detection_range"]
    if d2 > detect ** 2:
        passive_ai(mob, game, dt)
        return

    dist = math.sqrt(d2)
    if dist < 7.0:
        _steer(mob, -dx, -dz, dt)          # 너무 가까우면 후퇴
    elif dist > 13.0:
        _steer(mob, dx, dz, dt)            # 사거리 안으로 접근
    else:
        _stop(mob)

    mob.attack_cooldown -= dt
    if mob.attack_cooldown <= 0 and dist < 16.0:
        mob.attack_cooldown = 2.5
        px, py, pz = player.position
        origin = (mob.pos[0], mob.pos[1] + mob.body.height * 0.7,
                  mob.pos[2])
        direction = (px - origin[0], (py + 1.2) - origin[1],
                     pz - origin[2])
        game.projectiles.spawn(origin, direction, speed=18.0,
                               damage=mob.type["attack_damage"],
                               owner=mob, color=(0.85, 0.85, 0.85))


# ---------------------------------------------------------------------------
def exploder_ai(mob, game, dt):
    player = game.player
    if player.dead:
        _stop(mob)
        return
    dx, dz = _dir_to_player(mob, player)
    d2 = dist_sq(mob.pos, list(player.position))
    detect = mob.type["detection_range"]

    if mob.fuse > 0:
        # 도화선 점화 중: 정지 + 점멸
        _stop(mob)
        mob.fuse -= dt
        mob.flash_timer += dt
        if mob.fuse <= 0:
            center = (mob.pos[0], mob.pos[1] + 0.5, mob.pos[2])
            mob.health = 0
            mob.silent_death = True
            combat.explode(game, center, radius=3.2, max_damage=16)
        return

    if d2 > detect ** 2:
        passive_ai(mob, game, dt)
        return

    if d2 < 2.6 ** 2:
        mob.fuse = 1.4   # 점화
        _stop(mob)
    else:
        _steer(mob, dx, dz, dt)


AI_FUNCTIONS = {
    "passive": passive_ai,
    "hostile": hostile_ai,
    "ranged": ranged_ai,
    "exploder": exploder_ai,
}
