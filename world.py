"""
world.py - 청크 기반 월드 관리.

- 플레이어 주변 청크만 로드하고 멀어지면 언로드한다.
- 블록 변경은 modified_blocks 에 기록되어 저장/불러오기에 쓰인다.
- 변경된 청크는 dirty 로 표시되고 프레임당 예산만큼만 재빌드한다.
"""

import math

import blocks as B
import config
from chunk import Chunk, build_chunk_mesh, apply_chunk_mesh
from terrain_generator import TerrainGenerator
from utils import pos_key

CHUNK = config.CHUNK_SIZE
HEIGHT = config.WORLD_HEIGHT


class World:
    def __init__(self, seed):
        self.seed = int(seed)
        self.generator = TerrainGenerator(self.seed)
        self.chunks = {}                # (cx, cz) -> Chunk
        self.modified_blocks = {}       # "x,y,z" -> block_id
        self.containers = {}            # "x,y,z" -> dict (상자/화로 상태)
        self.ambient = 1.0              # 낮/밤 밝기 (game 이 갱신)
        self.render_distance = int(config.get("render_distance"))

    # ------------------------------------------------------------------
    # 좌표 변환
    # ------------------------------------------------------------------
    @staticmethod
    def to_chunk_coords(x, z):
        return math.floor(x / CHUNK), math.floor(z / CHUNK)

    # ------------------------------------------------------------------
    # 블록 접근
    # ------------------------------------------------------------------
    def get_block(self, x, y, z):
        x, y, z = int(math.floor(x)), int(math.floor(y)), int(math.floor(z))
        if y < 0 or y >= HEIGHT:
            return B.AIR
        cx, cz = math.floor(x / CHUNK), math.floor(z / CHUNK)
        chunk = self.chunks.get((cx, cz))
        if chunk is None:
            return B.AIR
        return chunk.get_block(x - cx * CHUNK, y, z - cz * CHUNK)

    def get_block_def(self, x, y, z):
        return B.get_block_def(self.get_block(x, y, z))

    def is_solid_at(self, x, y, z):
        return self.get_block(x, y, z) in B.SOLID_IDS

    def set_block(self, x, y, z, block_id, record=True):
        x, y, z = int(math.floor(x)), int(math.floor(y)), int(math.floor(z))
        if y < 0 or y >= HEIGHT:
            return False
        cx, cz = math.floor(x / CHUNK), math.floor(z / CHUNK)
        chunk = self.chunks.get((cx, cz))
        if chunk is None:
            # 로드되지 않은 청크의 변경은 기록만 해두고 로드시 적용
            if record:
                self.modified_blocks[pos_key(x, y, z)] = int(block_id)
            return True
        lx, lz = x - cx * CHUNK, z - cz * CHUNK
        chunk.set_block(lx, y, lz, block_id)
        if record:
            self.modified_blocks[pos_key(x, y, z)] = int(block_id)

        # 청크 경계면이면 이웃 청크도 다시 빌드
        if lx == 0:
            self._mark_dirty(cx - 1, cz)
        elif lx == CHUNK - 1:
            self._mark_dirty(cx + 1, cz)
        if lz == 0:
            self._mark_dirty(cx, cz - 1)
        elif lz == CHUNK - 1:
            self._mark_dirty(cx, cz + 1)
        return True

    def _mark_dirty(self, cx, cz):
        chunk = self.chunks.get((cx, cz))
        if chunk is not None:
            chunk.dirty = True

    # ------------------------------------------------------------------
    # 청크 생성/로드/언로드
    # ------------------------------------------------------------------
    def generate_chunk(self, chunk_x, chunk_z):
        """청크를 생성하고 저장된 블록 변경을 적용한다."""
        data, biome_map, height_map = self.generator.generate_chunk(
            chunk_x, chunk_z)
        chunk = Chunk(chunk_x, chunk_z, data, biome_map, height_map)

        # 저장된 변경 블록 적용
        x0, z0 = chunk_x * CHUNK, chunk_z * CHUNK
        for key, bid in self.modified_blocks.items():
            sx, sy, sz = key.split(",")
            wx, wy, wz = int(sx), int(sy), int(sz)
            if x0 <= wx < x0 + CHUNK and z0 <= wz < z0 + CHUNK:
                if 0 <= wy < HEIGHT:
                    chunk.blocks[wx - x0, wy, wz - z0] = bid
        chunk.modified = False
        chunk.dirty = True

        self.chunks[(chunk_x, chunk_z)] = chunk
        # 새로 로드된 청크와 맞닿은 기존 청크의 경계면 다시 빌드
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            self._mark_dirty(chunk_x + dx, chunk_z + dz)
        return chunk

    def load_chunks_around_player(self, px, pz, budget=2):
        """
        플레이어 주변 render_distance 내 청크를 로드한다.
        budget: 프레임당 최대 생성 청크 수 (프레임 드랍 방지)
        반환: 이번에 생성한 청크 수
        """
        pcx, pcz = self.to_chunk_coords(px, pz)
        rd = self.render_distance
        needed = []
        for dx in range(-rd, rd + 1):
            for dz in range(-rd, rd + 1):
                key = (pcx + dx, pcz + dz)
                if key not in self.chunks:
                    needed.append((dx * dx + dz * dz, key))
        needed.sort()
        made = 0
        for _, (cx, cz) in needed:
            if made >= budget:
                break
            self.generate_chunk(cx, cz)
            made += 1
        return made

    def unload_far_chunks(self, px, pz):
        """render_distance + 1 밖의 청크를 언로드한다."""
        pcx, pcz = self.to_chunk_coords(px, pz)
        limit = self.render_distance + 1
        to_remove = []
        for (cx, cz), chunk in self.chunks.items():
            if abs(cx - pcx) > limit or abs(cz - pcz) > limit:
                to_remove.append((cx, cz))
        for key in to_remove:
            self.chunks[key].destroy_entities()
            del self.chunks[key]
        return len(to_remove)

    def rebuild_dirty_chunks(self, px=0, pz=0, budget=2):
        """dirty 청크를 가까운 순서로 예산만큼 재빌드한다."""
        pcx, pcz = self.to_chunk_coords(px, pz)
        dirty = [((c.cx - pcx) ** 2 + (c.cz - pcz) ** 2, key)
                 for key, c in self.chunks.items() if c.dirty]
        dirty.sort()
        done = 0
        for _, key in dirty:
            if done >= budget:
                break
            chunk = self.chunks[key]
            solid, alpha = build_chunk_mesh(chunk, self)
            apply_chunk_mesh(chunk, solid, alpha, self.ambient)
            done += 1
        return done

    def set_ambient(self, brightness):
        self.ambient = brightness
        for chunk in self.chunks.values():
            chunk.set_ambient(brightness)

    # ------------------------------------------------------------------
    # 스폰/조회 헬퍼
    # ------------------------------------------------------------------
    def find_spawn_point(self):
        """(0,0) 근처의 물 밖 지표면 스폰 위치를 찾는다."""
        for radius in range(0, 64, 8):
            for x, z in ((radius, 0), (-radius, 0), (0, radius), (0, -radius),
                         (radius, radius)):
                h = self.generator.height_at(x, z)
                if h > config.SEA_LEVEL:
                    return (x + 0.5, h + 2.0, z + 0.5)
        return (0.5, config.SEA_LEVEL + 12.0, 0.5)

    def surface_height(self, x, z):
        """실제 로드된 블록 기준 지표 높이 (없으면 근사값)."""
        cx, cz = self.to_chunk_coords(x, z)
        chunk = self.chunks.get((cx, cz))
        if chunk is None:
            return self.generator.height_at(x, z)
        lx = int(math.floor(x)) - cx * CHUNK
        lz = int(math.floor(z)) - cz * CHUNK
        for y in range(HEIGHT - 1, 0, -1):
            if chunk.blocks[lx, y, lz] in B.SOLID_IDS:
                return y
        return 0

    def biome_at(self, x, z):
        cx, cz = self.to_chunk_coords(x, z)
        chunk = self.chunks.get((cx, cz))
        if chunk is not None:
            lx = int(math.floor(x)) - cx * CHUNK
            lz = int(math.floor(z)) - cz * CHUNK
            return chunk.biome_map[lx, lz]
        return self.generator.biome_at(x, z)

    def light_at(self, x, y, z):
        """조명 값 조회 (몹 스폰 등)."""
        cx, cz = self.to_chunk_coords(x, z)
        chunk = self.chunks.get((cx, cz))
        if chunk is None or chunk.light is None:
            return 15
        lx = int(math.floor(x)) - cx * CHUNK
        lz = int(math.floor(z)) - cz * CHUNK
        y = int(math.floor(y))
        if 0 <= y < HEIGHT:
            return int(chunk.light[lx, y, lz])
        return 15

    # ------------------------------------------------------------------
    # 컨테이너 (상자/화로)
    # ------------------------------------------------------------------
    def get_container(self, x, y, z, kind):
        """해당 위치의 컨테이너 상태를 가져오거나 만든다."""
        key = pos_key(x, y, z)
        if key not in self.containers:
            if kind == "chest":
                self.containers[key] = {"type": "chest",
                                        "slots": [None] * 27}
            elif kind == "furnace":
                self.containers[key] = {
                    "type": "furnace", "input": None, "fuel": None,
                    "output": None, "burn_time": 0.0, "burn_total": 0.0,
                    "progress": 0.0,
                }
        return self.containers.get(key)

    def remove_container(self, x, y, z):
        self.containers.pop(pos_key(x, y, z), None)
