"""
physics.py - 복셀 월드 물리 (플레이어/몹/드롭 공용).

- AABB(축 정렬 박스) 를 축별로 이동시키며 solid 블록과 충돌 판정.
- position 은 발 밑 중심 좌표를 기준으로 한다.
- 중력, 접지 판정, 머리 충돌, 벽 충돌, 물속 판정, 반발/미끄러짐 지원.
"""

import math

import blocks as B
import config

GRAVITY = config.GRAVITY
TERMINAL_VELOCITY = 42.0


class PhysicsBody:
    """복셀 충돌을 갖는 이동체 상태."""

    def __init__(self, half_width=0.3, height=1.8):
        self.half_width = half_width
        self.height = height
        self.velocity = [0.0, 0.0, 0.0]
        self.grounded = False
        self.hit_ceiling = False
        self.hit_wall = False
        self.in_water = False
        self.head_in_water = False
        self.ground_block = B.AIR


def _collides(world, x, y, z, half_w, height):
    """AABB 가 solid 블록과 겹치는지 검사."""
    min_x = math.floor(x - half_w)
    max_x = math.floor(x + half_w)
    min_y = math.floor(y)
    max_y = math.floor(y + height - 1e-4)
    min_z = math.floor(z - half_w)
    max_z = math.floor(z + half_w)
    for bx in range(min_x, max_x + 1):
        for by in range(min_y, max_y + 1):
            for bz in range(min_z, max_z + 1):
                bid = world.get_block(bx, by, bz)
                if bid in B.SOLID_IDS:
                    bdef = B.BLOCKS[bid]
                    # 반블록은 아래 절반만 충돌
                    if bdef.shape == "slab":
                        if y >= by + 0.5:
                            continue
                    return True
    return False


def move_body(world, body, pos, dt):
    """
    body.velocity 를 적용해 pos 를 이동시키고 충돌을 해소한다.
    반환: 새 위치 [x, y, z]
    """
    x, y, z = pos
    vx, vy, vz = body.velocity
    hw, h = body.half_width, body.height
    body.grounded = False
    body.hit_ceiling = False
    body.hit_wall = False

    # --- X 축 ---
    nx = x + vx * dt
    if vx != 0 and _collides(world, nx, y, z, hw, h):
        step = 0.05 * (1 if vx > 0 else -1)
        while abs(nx - x) > 0.001 and _collides(world, nx, y, z, hw, h):
            nx -= step
            if (vx > 0 and nx < x) or (vx < 0 and nx > x):
                nx = x
                break
        if _collides(world, nx, y, z, hw, h):
            nx = x
        body.velocity[0] = 0.0
        body.hit_wall = True
    x = nx

    # --- Z 축 ---
    nz = z + vz * dt
    if vz != 0 and _collides(world, x, y, nz, hw, h):
        step = 0.05 * (1 if vz > 0 else -1)
        while abs(nz - z) > 0.001 and _collides(world, x, y, nz, hw, h):
            nz -= step
            if (vz > 0 and nz < z) or (vz < 0 and nz > z):
                nz = z
                break
        if _collides(world, x, y, nz, hw, h):
            nz = z
        body.velocity[2] = 0.0
        body.hit_wall = True
    z = nz

    # --- Y 축 ---
    ny = y + vy * dt
    if vy != 0 and _collides(world, x, ny, z, hw, h):
        if vy < 0:
            # 착지: 블록 윗면에 스냅
            ny = math.floor(ny) + 1.0
            while _collides(world, x, ny, z, hw, h):
                ny += 1.0
                if ny > y + 1:
                    ny = y
                    break
            body.grounded = True
        else:
            # 머리 충돌
            ny = y
            body.hit_ceiling = True
        body.velocity[1] = 0.0
    y = ny

    # 접지 재확인 (경사 없는 복셀이므로 바로 아래 검사)
    if body.velocity[1] <= 0 and _collides(world, x, y - 0.05, z, hw, h):
        body.grounded = True

    # 발 밑 블록 (마찰/반발 판정용)
    body.ground_block = world.get_block(
        math.floor(x), math.floor(y - 0.5), math.floor(z))

    # 물속 판정
    feet = world.get_block(math.floor(x), math.floor(y + 0.2), math.floor(z))
    head = world.get_block(math.floor(x), math.floor(y + h - 0.2),
                           math.floor(z))
    body.in_water = B.BLOCKS[feet].is_liquid or B.BLOCKS[head].is_liquid
    body.head_in_water = B.BLOCKS[head].is_liquid

    return [x, y, z]


def apply_gravity(body, dt, in_water=False):
    """중력 적용 (물속은 감쇠)."""
    g = GRAVITY * (0.35 if in_water else 1.0)
    body.velocity[1] -= g * dt
    limit = TERMINAL_VELOCITY * (0.25 if in_water else 1.0)
    if body.velocity[1] < -limit:
        body.velocity[1] = -limit


def ground_friction(body):
    """발 밑 블록의 마찰 계수 (0=미끄러짐 없음, 1=완전 미끄러움)."""
    bdef = B.BLOCKS.get(body.ground_block)
    return bdef.slipperiness if bdef else 0.0


def ground_bounciness(body):
    bdef = B.BLOCKS.get(body.ground_block)
    return bdef.bounciness if bdef else 0.0


def touching_damage_block(world, pos, half_w, height):
    """접촉 중인 블록의 접촉 피해량 최댓값."""
    x, y, z = pos
    dmg = 0
    for bx in range(math.floor(x - half_w - 0.1),
                    math.floor(x + half_w + 0.1) + 1):
        for by in range(math.floor(y - 0.1),
                        math.floor(y + height + 0.1) + 1):
            for bz in range(math.floor(z - half_w - 0.1),
                            math.floor(z + half_w + 0.1) + 1):
                bdef = B.BLOCKS.get(world.get_block(bx, by, bz))
                if bdef and bdef.damage > dmg:
                    dmg = bdef.damage
    return dmg
