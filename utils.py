"""
utils.py - 공용 유틸리티.

- 시드 기반 해시 노이즈 (2D/3D value noise, fBm)  : numpy 벡터화 구현
- 복셀 레이캐스트 (DDA)
- 기타 수학 헬퍼
"""

import math

import numpy as np


# ---------------------------------------------------------------------------
# 해시 기반 격자 난수
# ---------------------------------------------------------------------------
def _hash2(ix, iz, seed):
    """정수 격자 좌표 -> [0,1) 난수 (numpy 배열 지원)."""
    h = (ix * 374761393 + iz * 668265263 + seed * 144665) & 0x7FFFFFFF
    h = (h ^ (h >> 13)) * 1274126177 & 0x7FFFFFFF
    h = h ^ (h >> 16)
    return (h & 0xFFFFFF) / float(0x1000000)


def _hash3(ix, iy, iz, seed):
    h = (ix * 374761393 + iy * 2246822519 + iz * 668265263 + seed * 144665) & 0x7FFFFFFF
    h = (h ^ (h >> 13)) * 1274126177 & 0x7FFFFFFF
    h = h ^ (h >> 16)
    return (h & 0xFFFFFF) / float(0x1000000)


def _smooth(t):
    """smoothstep 보간 계수."""
    return t * t * (3.0 - 2.0 * t)


# ---------------------------------------------------------------------------
# 2D value noise (numpy)
# ---------------------------------------------------------------------------
def value_noise_2d(xs, zs, scale, seed):
    """
    xs, zs : 1D numpy 배열 (월드 좌표) - meshgrid 로 조합됨
    반환   : shape (len(xs), len(zs)) 의 [0,1) 노이즈
    """
    gx, gz = np.meshgrid(xs / scale, zs / scale, indexing="ij")
    x0 = np.floor(gx).astype(np.int64)
    z0 = np.floor(gz).astype(np.int64)
    tx = _smooth(gx - x0)
    tz = _smooth(gz - z0)

    v00 = _hash2(x0, z0, seed)
    v10 = _hash2(x0 + 1, z0, seed)
    v01 = _hash2(x0, z0 + 1, seed)
    v11 = _hash2(x0 + 1, z0 + 1, seed)

    a = v00 + (v10 - v00) * tx
    b = v01 + (v11 - v01) * tx
    return a + (b - a) * tz


def fbm_2d(xs, zs, scale, seed, octaves=4, persistence=0.5, lacunarity=2.0):
    """여러 옥타브의 value noise 를 합성한 프랙탈 노이즈. [0,1) 범위."""
    total = np.zeros((len(xs), len(zs)))
    amplitude = 1.0
    frequency = 1.0
    max_amp = 0.0
    for i in range(octaves):
        total += value_noise_2d(xs, zs, scale / frequency, seed + i * 1013) * amplitude
        max_amp += amplitude
        amplitude *= persistence
        frequency *= lacunarity
    return total / max_amp


# ---------------------------------------------------------------------------
# 3D value noise (numpy) - 동굴 생성용
# ---------------------------------------------------------------------------
def value_noise_3d(xs, ys, zs, scale, seed):
    """
    xs, ys, zs : 1D numpy 배열 (월드 좌표)
    반환       : shape (len(xs), len(ys), len(zs)) 의 [0,1) 노이즈
    """
    gx, gy, gz = np.meshgrid(xs / scale, ys / scale, zs / scale, indexing="ij")
    x0 = np.floor(gx).astype(np.int64)
    y0 = np.floor(gy).astype(np.int64)
    z0 = np.floor(gz).astype(np.int64)
    tx = _smooth(gx - x0)
    ty = _smooth(gy - y0)
    tz = _smooth(gz - z0)

    c000 = _hash3(x0, y0, z0, seed)
    c100 = _hash3(x0 + 1, y0, z0, seed)
    c010 = _hash3(x0, y0 + 1, z0, seed)
    c110 = _hash3(x0 + 1, y0 + 1, z0, seed)
    c001 = _hash3(x0, y0, z0 + 1, seed)
    c101 = _hash3(x0 + 1, y0, z0 + 1, seed)
    c011 = _hash3(x0, y0 + 1, z0 + 1, seed)
    c111 = _hash3(x0 + 1, y0 + 1, z0 + 1, seed)

    a = c000 + (c100 - c000) * tx
    b = c010 + (c110 - c010) * tx
    c = c001 + (c101 - c001) * tx
    d = c011 + (c111 - c011) * tx

    e = a + (b - a) * ty
    f = c + (d - c) * ty
    return e + (f - e) * tz


# ---------------------------------------------------------------------------
# 스칼라 노이즈 (한 점만 필요할 때)
# ---------------------------------------------------------------------------
def noise2(x, z, scale, seed):
    v = value_noise_2d(np.array([float(x)]), np.array([float(z)]), scale, seed)
    return float(v[0, 0])


def hash_at(x, z, seed):
    """단일 좌표 결정론적 난수 [0,1)."""
    return float(_hash2(int(x), int(z), int(seed)))


def hash3_at(x, y, z, seed):
    return float(_hash3(int(x), int(y), int(z), int(seed)))


# ---------------------------------------------------------------------------
# 복셀 레이캐스트 (Amanatides & Woo DDA)
# ---------------------------------------------------------------------------
def voxel_raycast(origin, direction, max_distance, is_hit):
    """
    origin        : (x, y, z) 시작 위치
    direction     : (dx, dy, dz) 정규화된 방향
    max_distance  : 최대 거리
    is_hit(x,y,z) : 해당 블록이 히트 대상인지 판정하는 콜백

    반환: (hit_pos, prev_pos) 블록 정수좌표 튜플, 없으면 (None, None)
    prev_pos 는 히트 블록 직전의 빈 칸 (블록 설치 위치).
    """
    x, y, z = origin
    dx, dy, dz = direction
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    if length < 1e-9:
        return None, None
    dx, dy, dz = dx / length, dy / length, dz / length

    ix, iy, iz = math.floor(x), math.floor(y), math.floor(z)
    step_x = 1 if dx > 0 else -1
    step_y = 1 if dy > 0 else -1
    step_z = 1 if dz > 0 else -1

    def _t_max(p, ip, d, step):
        if abs(d) < 1e-9:
            return float("inf")
        if step > 0:
            return (ip + 1 - p) / d
        return (ip - p) / d

    t_max_x = _t_max(x, ix, dx, step_x)
    t_max_y = _t_max(y, iy, dy, step_y)
    t_max_z = _t_max(z, iz, dz, step_z)
    t_delta_x = abs(1.0 / dx) if abs(dx) > 1e-9 else float("inf")
    t_delta_y = abs(1.0 / dy) if abs(dy) > 1e-9 else float("inf")
    t_delta_z = abs(1.0 / dz) if abs(dz) > 1e-9 else float("inf")

    prev = (ix, iy, iz)
    t = 0.0
    # 시작 블록 자체가 히트인 경우
    if is_hit(ix, iy, iz):
        return (ix, iy, iz), prev

    while t <= max_distance:
        prev = (ix, iy, iz)
        if t_max_x < t_max_y and t_max_x < t_max_z:
            ix += step_x
            t = t_max_x
            t_max_x += t_delta_x
        elif t_max_y < t_max_z:
            iy += step_y
            t = t_max_y
            t_max_y += t_delta_y
        else:
            iz += step_z
            t = t_max_z
            t_max_z += t_delta_z
        if t > max_distance:
            break
        if is_hit(ix, iy, iz):
            return (ix, iy, iz), prev
    return None, None


# ---------------------------------------------------------------------------
# 기타
# ---------------------------------------------------------------------------
def set_mouse_locked(state):
    """마우스 잠금 설정 (창이 없는 환경/테스트에서는 무시)."""
    from ursina import mouse
    try:
        mouse.locked = state
    except AttributeError:
        pass


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def lerp(a, b, t):
    return a + (b - a) * t


def dist_sq(a, b):
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2


def pos_key(x, y, z):
    """블록 좌표 -> 저장용 문자열 키."""
    return f"{int(x)},{int(y)},{int(z)}"


def key_pos(key):
    """저장용 문자열 키 -> 블록 좌표 튜플."""
    a, b, c = key.split(",")
    return int(a), int(b), int(c)
