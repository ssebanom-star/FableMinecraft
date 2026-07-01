"""
lighting.py - 청크 조명 계산.

- 하늘빛: 위에서 아래로 감쇠(불투명=차단, 물/잎=부분 감쇠). 동굴은 자동으로 어두워진다.
- 블록빛: 횃불/발광 블록에서 BFS 전파 (청크 내부).
- 최종 광량 = max(하늘빛, 블록빛), 0~15.
- 낮/밤 전체 밝기는 game.py 에서 청크 엔티티 틴트로 곱해진다
  (하늘빛 성분만 다시 굽지 않고 근사 처리).
"""

from collections import deque

import numpy as np

import blocks as B
import config

CHUNK = config.CHUNK_SIZE
HEIGHT = config.WORLD_HEIGHT

# 블록별 빛 감쇠량 (15 = 완전 차단)
_ATTEN_LUT = np.zeros(256, dtype=np.int16)
for _b in B.BLOCKS.values():
    if _b.id in B.OPAQUE_IDS:
        _ATTEN_LUT[_b.id] = 15
    elif _b.is_liquid:
        _ATTEN_LUT[_b.id] = 2
    elif _b.name in ("oak_leaves", "birch_leaves", "spruce_leaves"):
        _ATTEN_LUT[_b.id] = 2
    elif _b.name == "ice":
        _ATTEN_LUT[_b.id] = 1

# 통과 가능(빛 전파) 블록: 불투명 큐브가 아니면 통과
_PASS_LUT = np.ones(256, dtype=bool)
for _id in B.OPAQUE_IDS:
    _PASS_LUT[_id] = False

_SOURCE_LUT = np.zeros(256, dtype=np.uint8)
for _b in B.BLOCKS.values():
    if _b.emits_light:
        _SOURCE_LUT[_b.id] = _b.light_level


def compute_sky_light(block_array):
    """
    하늘빛 배열 계산. shape (16, H, 16), 0~15.
    각 열에서 위에서부터 감쇠를 누적한다.
    """
    atten = _ATTEN_LUT[block_array]                     # (16,H,16)
    # 위(y=H-1)에서 아래로: 자기 셀 위쪽 블록들의 감쇠 누적
    flipped = atten[:, ::-1, :]
    cum = np.cumsum(flipped, axis=1)
    # 현재 셀에 도달하는 빛은 "위쪽" 감쇠까지만 반영 (자기 자신 제외)
    cum_above = cum - flipped
    sky = 15 - cum_above[:, ::-1, :]
    return np.clip(sky, 0, 15).astype(np.uint8)


def compute_block_light(block_array):
    """블록 광원에서 BFS 전파. shape (16, H, 16), 0~15."""
    light = np.zeros((CHUNK, HEIGHT, CHUNK), dtype=np.uint8)
    sources = np.argwhere(_SOURCE_LUT[block_array] > 0)
    if len(sources) == 0:
        return light

    q = deque()
    for (x, y, z) in sources:
        lv = int(_SOURCE_LUT[block_array[x, y, z]])
        light[x, y, z] = lv
        q.append((int(x), int(y), int(z), lv))

    passable = _PASS_LUT[block_array]
    while q:
        x, y, z, lv = q.popleft()
        nl = lv - 1
        if nl <= 0:
            continue
        for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0),
                           (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            nx, ny, nz = x + dx, y + dy, z + dz
            if not (0 <= nx < CHUNK and 0 <= ny < HEIGHT and 0 <= nz < CHUNK):
                continue
            if not passable[nx, ny, nz]:
                continue
            if light[nx, ny, nz] >= nl:
                continue
            light[nx, ny, nz] = nl
            q.append((nx, ny, nz, nl))
    return light


def compute_chunk_light(block_array):
    """최종 광량 = max(하늘빛, 블록빛)."""
    sky = compute_sky_light(block_array)
    blk = compute_block_light(block_array)
    return np.maximum(sky, blk)


def light_to_brightness(light):
    """광량(0~15) -> 정점 밝기 계수 (동굴이 완전한 검정이 되지 않게 하한 유지)."""
    return 0.16 + 0.84 * (light / 15.0)
