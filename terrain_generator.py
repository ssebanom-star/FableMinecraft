"""
terrain_generator.py - 시드 기반 절차적 지형 생성.

- 같은 seed 는 항상 같은 월드를 생성한다 (해시 기반 value noise).
- 대륙/산 노이즈로 높이 결정, 온도/습도 노이즈로 바이옴 결정.
- 3D 노이즈 동굴, 깊이별 광물 분포, 바이옴별 나무/식물/지표 블록.
"""

import numpy as np

import blocks as B
import config
from utils import fbm_2d, value_noise_3d, hash_at, noise2

CHUNK = config.CHUNK_SIZE
HEIGHT = config.WORLD_HEIGHT
SEA = config.SEA_LEVEL

# 바이옴 정의: 지표/표토 블록, 나무 확률, 식물 확률, 이름
BIOMES = {
    "plains":    dict(surface=B.GRASS, filler=B.DIRT, tree=0.002, plant=0.06,
                      display="평야"),
    "forest":    dict(surface=B.GRASS, filler=B.DIRT, tree=0.045, plant=0.05,
                      display="숲"),
    "birch_forest": dict(surface=B.GRASS, filler=B.DIRT, tree=0.04, plant=0.04,
                         display="자작나무 숲"),
    "desert":    dict(surface=B.SAND, filler=B.SAND, tree=0.0, plant=0.008,
                      display="사막"),
    "snow":      dict(surface=B.SNOW_BLOCK, filler=B.DIRT, tree=0.012,
                      plant=0.005, display="설원"),
    "mountains": dict(surface=B.STONE, filler=B.STONE, tree=0.004,
                      plant=0.01, display="산악"),
    "swamp":     dict(surface=B.MUD, filler=B.DIRT, tree=0.02, plant=0.09,
                      display="늪지"),
    "beach":     dict(surface=B.SAND, filler=B.SAND, tree=0.0, plant=0.003,
                      display="해변"),
    "lake":      dict(surface=B.SAND, filler=B.DIRT, tree=0.0, plant=0.0,
                      display="호수"),
}

# 몹 스폰 확률 가중치 (mobs.py 에서 사용)
BIOME_SPAWN_WEIGHT = {
    "plains": 1.2, "forest": 1.0, "birch_forest": 1.0, "desert": 0.5,
    "snow": 0.6, "mountains": 0.5, "swamp": 1.1, "beach": 0.4, "lake": 0.1,
}


class TerrainGenerator:
    def __init__(self, seed):
        self.seed = int(seed)

    # ------------------------------------------------------------------
    # 높이/바이옴 필드
    # ------------------------------------------------------------------
    def _height_fields(self, xs, zs):
        """월드 좌표 배열 -> (높이맵 float, 산 강도)"""
        cont = fbm_2d(xs, zs, 150.0, self.seed + 11, octaves=4)
        hills = fbm_2d(xs, zs, 48.0, self.seed + 23, octaves=3)
        mount = fbm_2d(xs, zs, 230.0, self.seed + 47, octaves=3)

        height = 34.0 + cont * 30.0 + hills * 8.0
        mfac = np.clip((mount - 0.60) / 0.40, 0.0, 1.0)
        height = height + mfac * mfac * 55.0
        return height, mfac

    def _climate_fields(self, xs, zs):
        temp = fbm_2d(xs, zs, 170.0, self.seed + 101, octaves=3)
        moist = fbm_2d(xs, zs, 140.0, self.seed + 202, octaves=3)
        return temp, moist

    @staticmethod
    def _pick_biome(height, mfac, temp, moist):
        if height < SEA - 1:
            return "lake"
        if height <= SEA + 1:
            return "beach"
        if mfac > 0.35 or height > 82:
            return "mountains"
        if temp > 0.62 and moist < 0.45:
            return "desert"
        if temp < 0.34:
            return "snow"
        if moist > 0.68 and height < 58:
            return "swamp"
        if moist > 0.52:
            return "birch_forest" if temp > 0.55 else "forest"
        return "plains"

    def biome_at(self, x, z):
        """단일 좌표의 바이옴 이름 (HUD / 몹 스폰용)."""
        xs = np.array([float(x)])
        zs = np.array([float(z)])
        h, m = self._height_fields(xs, zs)
        t, mo = self._climate_fields(xs, zs)
        return self._pick_biome(float(h[0, 0]), float(m[0, 0]),
                                float(t[0, 0]), float(mo[0, 0]))

    def height_at(self, x, z):
        """지형 높이 근사값 (스폰 위치 탐색용, 동굴 미반영)."""
        xs = np.array([float(x)])
        zs = np.array([float(z)])
        h, _ = self._height_fields(xs, zs)
        return int(np.clip(h[0, 0], 4, HEIGHT - 10))

    # ------------------------------------------------------------------
    # 청크 생성
    # ------------------------------------------------------------------
    def generate_chunk(self, chunk_x, chunk_z):
        """
        반환: (blocks_array (16,H,16) uint8, biome_map (16,16) str,
               height_map (16,16) int)
        """
        x0 = chunk_x * CHUNK
        z0 = chunk_z * CHUNK
        xs = np.arange(x0, x0 + CHUNK, dtype=np.float64)
        zs = np.arange(z0, z0 + CHUNK, dtype=np.float64)

        height_f, mfac = self._height_fields(xs, zs)
        temp, moist = self._climate_fields(xs, zs)
        height = np.clip(height_f, 4, HEIGHT - 10).astype(np.int32)

        data = np.zeros((CHUNK, HEIGHT, CHUNK), dtype=np.uint8)
        ys = np.arange(HEIGHT, dtype=np.int32)[None, :, None]   # (1,H,1)
        hcol = height[:, None, :]                               # (16,1,16)

        # 기본 층: 기반암 / 돌 / 표토
        data[ys.repeat(CHUNK, 0).repeat(CHUNK, 2) == 0] = B.BEDROCK
        stone_mask = (ys > 0) & (ys < hcol - 3)
        filler_mask = (ys >= hcol - 3) & (ys < hcol)
        surface_mask = ys == hcol

        data[np.broadcast_to(stone_mask, data.shape)] = B.STONE

        # 바이옴 맵
        biome_map = np.empty((CHUNK, CHUNK), dtype=object)
        for lx in range(CHUNK):
            for lz in range(CHUNK):
                biome_map[lx, lz] = self._pick_biome(
                    float(height_f[lx, lz]), float(mfac[lx, lz]),
                    float(temp[lx, lz]), float(moist[lx, lz]))

        # 표토/지표 블록 (바이옴별)
        for lx in range(CHUNK):
            for lz in range(CHUNK):
                b = BIOMES[biome_map[lx, lz]]
                h = int(height[lx, lz])
                data[lx, max(1, h - 3):h, lz] = b["filler"]
                if h < HEIGHT:
                    data[lx, h, lz] = b["surface"]
                # 산악 상부는 눈으로 덮는다
                if biome_map[lx, lz] == "mountains" and h > 88:
                    data[lx, h, lz] = B.SNOW_BLOCK

        # 물 채우기 (해수면 아래)
        water_mask = (ys > hcol) & (ys <= SEA)
        data[np.broadcast_to(water_mask, data.shape) & (data == B.AIR)] = B.WATER

        # 설원 호수 표면은 얼음
        for lx in range(CHUNK):
            for lz in range(CHUNK):
                if biome_map[lx, lz] in ("snow",) and height[lx, lz] < SEA:
                    if data[lx, SEA, lz] == B.WATER:
                        data[lx, SEA, lz] = B.ICE

        # 동굴 (3D 노이즈 두 옥타브 곱)
        ys_f = np.arange(HEIGHT, dtype=np.float64)
        cave1 = value_noise_3d(xs, ys_f, zs, 26.0, self.seed + 501)
        cave2 = value_noise_3d(xs, ys_f, zs, 13.0, self.seed + 601)
        cave = cave1 * 0.65 + cave2 * 0.35
        cave_mask = (cave > 0.70) & (ys > 4) & (ys < hcol - 2)
        cave_mask = np.broadcast_to(cave_mask, data.shape) & \
            np.isin(data, (B.STONE, B.DIRT, B.MUD))
        data[cave_mask] = B.AIR

        # 광물 분포 (깊이별 확률, 동굴 주변에 더 많이)
        rnd = value_noise_3d(xs, ys_f, zs, 3.1, self.seed + 701)
        near_cave = (cave > 0.62)
        stone_cells = data == B.STONE
        y_grid = np.broadcast_to(ys, data.shape)

        def _ore(ore_id, max_y, threshold):
            th = np.where(near_cave, threshold * 0.988, threshold)
            mask = stone_cells & (y_grid < max_y) & (rnd > th)
            data[mask] = ore_id
            stone_cells[mask] = False

        # 희귀한 광물부터 배치 (낮은 임계값이 먼저 셀을 차지하지 않도록)
        _ore(B.ENERGY_ORE, 16, 0.957)
        _ore(B.CRYSTAL_ORE, 20, 0.952)
        _ore(B.GOLD_ORE, 30, 0.935)
        _ore(B.IRON_ORE, 52, 0.917)
        _ore(B.COPPER_ORE, 64, 0.912)
        _ore(B.COAL_ORE, 90, 0.895)

        # 최하층 흑암층
        deep = (y_grid >= 1) & (y_grid <= 3) & (data == B.STONE)
        deep_rnd = value_noise_3d(xs, ys_f[:5], zs, 2.0, self.seed + 801)
        data[:, 1:4, :][
            (deep[:, 1:4, :]) & (deep_rnd[:, 1:4, :] > 0.55)] = B.DARKROCK

        # 장식 (나무, 식물, 선인장 등)
        self._decorate(data, biome_map, height, x0, z0)

        return data, biome_map, height

    # ------------------------------------------------------------------
    # 장식물
    # ------------------------------------------------------------------
    def _decorate(self, data, biome_map, height, x0, z0):
        for lx in range(CHUNK):
            for lz in range(CHUNK):
                wx, wz = x0 + lx, z0 + lz
                biome = biome_map[lx, lz]
                info = BIOMES[biome]
                h = int(height[lx, lz])
                if h + 1 >= HEIGHT or h <= SEA - 1:
                    continue
                if data[lx, h, lz] not in (B.GRASS, B.SAND, B.SNOW_BLOCK,
                                           B.MUD, B.DIRT, B.STONE):
                    continue

                r = hash_at(wx, wz, self.seed + 900)
                # 나무 (수관이 청크 안에 들어오는 위치만)
                if r < info["tree"] and 2 <= lx <= 13 and 2 <= lz <= 13 \
                        and h + 7 < HEIGHT:
                    self._place_tree(data, lx, h + 1, lz, biome, wx, wz)
                    continue
                # 식물류
                r2 = hash_at(wx, wz, self.seed + 901)
                if r2 < info["plant"]:
                    data[lx, h + 1, lz] = self._pick_plant(biome, wx, wz)
                # 사막 선인장
                elif biome == "desert" and r2 < info["plant"] + 0.006:
                    ch = 2 + int(hash_at(wx, wz, self.seed + 902) * 2)
                    for dy in range(ch):
                        if h + 1 + dy < HEIGHT:
                            data[lx, h + 1 + dy, lz] = B.CACTUS
                # 호박 (희귀)
                elif biome in ("plains", "forest") and r2 > 0.9985:
                    data[lx, h + 1, lz] = B.PUMPKIN
                # 설원 눈 덮개
                if biome == "snow" and data[lx, h + 1, lz] == B.AIR:
                    if hash_at(wx, wz, self.seed + 903) < 0.5:
                        data[lx, h + 1, lz] = B.SNOW_LAYER

    def _pick_plant(self, biome, wx, wz):
        r = hash_at(wx, wz, self.seed + 910)
        if biome == "desert":
            return B.DEAD_BUSH
        if biome == "swamp":
            return B.MUSHROOM if r < 0.4 else B.TALL_GRASS
        if r < 0.65:
            return B.TALL_GRASS
        if r < 0.82:
            return B.FLOWER_YELLOW
        if r < 0.95:
            return B.FLOWER_RED
        return B.MUSHROOM

    def _place_tree(self, data, lx, y, lz, biome, wx, wz):
        if biome == "snow" or biome == "mountains":
            log, leaves = B.SPRUCE_LOG, B.SPRUCE_LEAVES
        elif biome == "birch_forest":
            log, leaves = B.BIRCH_LOG, B.BIRCH_LEAVES
        else:
            log, leaves = B.OAK_LOG, B.OAK_LEAVES

        trunk_h = 4 + int(hash_at(wx, wz, self.seed + 920) * 3)
        top = y + trunk_h
        # 수관 (잎)
        for dy in range(-2, 2):
            radius = 2 if dy < 0 else 1
            for dx in range(-radius, radius + 1):
                for dz in range(-radius, radius + 1):
                    if abs(dx) == radius and abs(dz) == radius and dy >= 0:
                        continue
                    px, py, pz = lx + dx, top + dy, lz + dz
                    if 0 <= px < CHUNK and 0 <= pz < CHUNK and 0 <= py < HEIGHT:
                        if data[px, py, pz] == B.AIR:
                            data[px, py, pz] = leaves
        if top + 2 < HEIGHT:
            data[lx, top + 1, lz] = leaves
        # 줄기
        for dy in range(trunk_h):
            if y + dy < HEIGHT:
                data[lx, y + dy, lz] = log


def biome_display_name(biome):
    return BIOMES.get(biome, {}).get("display", biome)
