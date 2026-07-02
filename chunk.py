"""
chunk.py - 청크 데이터와 메시 생성.

- 청크 크기: 16 x 128 x 16 (config 로 조절 가능)
- 모든 블록을 개별 Entity 로 만들지 않는다.
- 보이는 면(이웃이 불투명하지 않은 면)만 모아 청크당 1~2개의 메시로 렌더링:
  * 불투명 메시 (돌, 흙, 나무 등 + 잎)
  * 반투명 메시 (물, 유리, 얼음)
- 블록 변경 시 dirty 플래그를 세우고 world 가 재빌드한다.
"""

import numpy as np
from ursina import Entity, Mesh, Color, destroy, load_texture
from panda3d.core import TransparencyAttrib

import blocks as B
import config
import lighting
import textures

CHUNK = config.CHUNK_SIZE
HEIGHT = config.WORLD_HEIGHT

# ---------------------------------------------------------------------------
# 룩업 테이블 (블록 id -> 성질)
# ---------------------------------------------------------------------------
_OPAQUE_LUT = np.zeros(256, dtype=bool)
_LIQUID_LUT = np.zeros(256, dtype=bool)
_CUBE_LUT = np.zeros(256, dtype=bool)       # 일반 큐브 렌더링 대상
_ALPHA_LUT = np.zeros(256, dtype=bool)      # 반투명 메시로 렌더링
for _b in B.BLOCKS.values():
    if _b.id in B.OPAQUE_IDS:
        _OPAQUE_LUT[_b.id] = True
    if _b.is_liquid:
        _LIQUID_LUT[_b.id] = True
    if _b.shape == "cube" and _b.id != B.AIR:
        _CUBE_LUT[_b.id] = True
    if _b.name in ("water", "glass", "ice"):
        _ALPHA_LUT[_b.id] = True

# 반투명 큐브는 일반 큐브 목록에서 제외 (별도 메시)
for _name in ("glass", "ice"):
    _CUBE_LUT[B.block_id_by_name(_name)] = False

# 면 정의: (dx, dy, dz), 4개 코너 오프셋, 음영
FACES = [
    ((0, 1, 0),  [(0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0)], 1.00),   # top
    ((0, -1, 0), [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)], 0.45),   # bottom
    ((1, 0, 0),  [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)], 0.80),   # +x
    ((-1, 0, 0), [(0, 0, 1), (0, 1, 1), (0, 1, 0), (0, 0, 0)], 0.80),   # -x
    ((0, 0, 1),  [(1, 0, 1), (1, 1, 1), (0, 1, 1), (0, 0, 1)], 0.65),   # +z
    ((0, 0, -1), [(0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)], 0.65),   # -z
]


class Chunk:
    """블록 데이터 + 렌더링 엔티티를 갖는 청크."""

    def __init__(self, cx, cz, block_array, biome_map, height_map):
        self.cx = cx
        self.cz = cz
        self.blocks = block_array           # np.uint8 (16, H, 16)
        self.biome_map = biome_map          # (16,16) str
        self.height_map = height_map        # (16,16) int
        self.dirty = True
        self.light = None                   # (16,H,16) uint8
        self.solid_entity = None
        self.alpha_entity = None
        self.modified = False               # 저장 필요 여부

    # ------------------------------------------------------------------
    def get_block(self, lx, ly, lz):
        if 0 <= lx < CHUNK and 0 <= ly < HEIGHT and 0 <= lz < CHUNK:
            return int(self.blocks[lx, ly, lz])
        return B.AIR

    def set_block(self, lx, ly, lz, block_id):
        if 0 <= lx < CHUNK and 0 <= ly < HEIGHT and 0 <= lz < CHUNK:
            self.blocks[lx, ly, lz] = block_id
            self.dirty = True
            self.modified = True

    # ------------------------------------------------------------------
    def destroy_entities(self):
        if self.solid_entity:
            destroy(self.solid_entity)
            self.solid_entity = None
        if self.alpha_entity:
            destroy(self.alpha_entity)
            self.alpha_entity = None

    def set_ambient(self, brightness):
        """낮/밤 밝기를 엔티티 틴트로 적용 (메시를 다시 굽지 않음)."""
        c = Color(brightness, brightness, brightness, 1)
        if self.solid_entity:
            self.solid_entity.color = c
        if self.alpha_entity:
            self.alpha_entity.color = c


# ---------------------------------------------------------------------------
# 메시 생성
# ---------------------------------------------------------------------------
def _padded_blocks(chunk, world):
    """이웃 청크 경계를 포함한 (18, H+2, 18) 블록 배열."""
    p = np.zeros((CHUNK + 2, HEIGHT + 2, CHUNK + 2), dtype=np.uint8)
    p[1:-1, 1:-1, 1:-1] = chunk.blocks
    for (dx, dz), sl_src, sl_dst in (
        ((1, 0), np.s_[0, :, :], np.s_[-1, 1:-1, 1:-1]),
        ((-1, 0), np.s_[-1, :, :], np.s_[0, 1:-1, 1:-1]),
        ((0, 1), np.s_[:, :, 0], np.s_[1:-1, 1:-1, -1]),
        ((0, -1), np.s_[:, :, -1], np.s_[1:-1, 1:-1, 0]),
    ):
        nb = world.chunks.get((chunk.cx + dx, chunk.cz + dz))
        if nb is not None:
            p[sl_dst] = nb.blocks[sl_src]
    return p


def build_chunk_mesh(chunk, world):
    """
    청크의 보이는 면만 모아 정점 데이터를 만든다.
    반환: (solid_data, alpha_data)  각각 (verts, tris, cols) 또는 None
    """
    chunk.light = lighting.compute_chunk_light(chunk.blocks)
    padded = _padded_blocks(chunk, world)
    opaque_p = _OPAQUE_LUT[padded]
    liquid_p = _LIQUID_LUT[padded]

    ids = chunk.blocks
    cube_mask = _CUBE_LUT[ids]
    alpha_mask = _ALPHA_LUT[ids]

    solid = _MeshData()
    alpha = _MeshData()

    light = chunk.light
    # 면 밝기를 구할 때 이웃 셀 광량 사용 (청크 밖은 자기 셀 광량)
    for f_idx, ((dx, dy, dz), corners, shade) in enumerate(FACES):
        # 이웃이 불투명하지 않으면 면이 보인다
        nb = np.s_[1 + dx:CHUNK + 1 + dx, 1 + dy:HEIGHT + 1 + dy,
                   1 + dz:CHUNK + 1 + dz]
        neighbor_open = ~opaque_p[nb]

        # --- 불투명(및 잎 등) 큐브 ---
        visible = cube_mask & neighbor_open
        for (x, y, z) in np.argwhere(visible):
            bid = int(ids[x, y, z])
            _emit_face(solid, B.BLOCKS[bid], int(x), int(y), int(z),
                       f_idx, corners, shade,
                       _face_light(light, x, y, z, dx, dy, dz))

        # --- 반투명 큐브 (물/유리/얼음) ---
        visible_a = alpha_mask & neighbor_open
        # 물끼리 맞닿은 면은 그리지 않는다
        same_liquid = _LIQUID_LUT[ids] & liquid_p[nb]
        visible_a &= ~same_liquid
        for (x, y, z) in np.argwhere(visible_a):
            bid = int(ids[x, y, z])
            bdef = B.BLOCKS[bid]
            a = 0.62 if bdef.is_liquid else 1.0
            _emit_face(alpha, bdef, int(x), int(y), int(z), f_idx, corners,
                       shade, _face_light(light, x, y, z, dx, dy, dz),
                       alpha=a, liquid=bdef.is_liquid)

    # --- 특수 형태 (십자 식물, 횃불, 반블록, 울타리, 문) ---
    for (x, y, z) in np.argwhere((ids != B.AIR) & ~cube_mask & ~alpha_mask):
        bdef = B.BLOCKS[int(ids[x, y, z])]
        lv = lighting.light_to_brightness(int(light[x, y, z]))
        if bdef.shape in ("cross",):
            _emit_cross(solid, bdef, int(x), int(y), int(z), lv)
        elif bdef.shape == "torch":
            _emit_box(solid, bdef, int(x), int(y), int(z), lv,
                      0.4, 0.0, 0.4, 0.6, 0.65, 0.6)
        elif bdef.shape == "slab":
            _emit_box(solid, bdef, int(x), int(y), int(z), lv,
                      0.0, 0.0, 0.0, 1.0, 0.5, 1.0)
        elif bdef.shape == "fence":
            _emit_box(solid, bdef, int(x), int(y), int(z), lv,
                      0.35, 0.0, 0.35, 0.65, 1.0, 0.65)
        elif bdef.shape == "door":
            if bdef.name == "door_open":
                _emit_box(solid, bdef, int(x), int(y), int(z), lv,
                          0.0, 0.0, 0.0, 0.15, 1.0, 1.0)
            else:
                _emit_box(solid, bdef, int(x), int(y), int(z), lv,
                          0.0, 0.0, 0.0, 1.0, 1.0, 0.15)

    return solid.result(), alpha.result()


def _face_light(light, x, y, z, dx, dy, dz):
    nx, ny, nz = x + dx, y + dy, z + dz
    if 0 <= nx < CHUNK and 0 <= ny < HEIGHT and 0 <= nz < CHUNK:
        lv = int(light[nx, ny, nz])
    else:
        lv = int(light[x, y, z])
    return lighting.light_to_brightness(lv)


class _MeshData:
    def __init__(self):
        self.verts = []
        self.tris = []
        self.cols = []
        self.uvs = []

    def quad(self, v0, v1, v2, v3, col, uv4):
        i = len(self.verts)
        self.verts.extend((v0, v1, v2, v3))
        self.tris.extend((i, i + 1, i + 2, i, i + 2, i + 3))
        self.cols.extend((col, col, col, col))
        self.uvs.extend(uv4)

    def result(self):
        if not self.verts:
            return None
        return self.verts, self.tris, self.cols, self.uvs


def _face_uvs(tile_idx, f_idx, corners):
    """면 코너 순서에 맞는 아틀라스 UV 4개."""
    u0, v0, du, dv = textures.tile_uv(tile_idx)
    uvs = []
    for (cx_, cy_, cz_) in corners:
        if f_idx in (0, 1):          # 윗면/아랫면: xz 평면
            u, w = cx_, cz_
        elif f_idx in (2, 3):        # +x/-x: z 가 가로, y 가 세로
            u, w = cz_, cy_
        else:                        # +z/-z: x 가 가로, y 가 세로
            u, w = cx_, cy_
        uvs.append((u0 + u * du, v0 + w * dv))
    return uvs


def _emit_face(md, bdef, x, y, z, f_idx, corners, shade, brightness,
               alpha=1.0, liquid=False):
    tiles = textures.tiles_for(bdef.id)
    tile_idx = tiles[0] if f_idx == 0 else tiles[2] if f_idx == 1 \
        else tiles[1]
    s = shade * brightness
    col = Color(s, s, s, alpha)
    pts = []
    for (cx_, cy_, cz_) in corners:
        vy = cy_
        # 물 윗면은 살짝 낮춘다
        if liquid and cy_ == 1:
            vy = 0.85
        pts.append((x + cx_, y + vy, z + cz_))
    md.quad(pts[0], pts[1], pts[2], pts[3], col,
            _face_uvs(tile_idx, f_idx, corners))


def _emit_cross(md, bdef, x, y, z, brightness):
    """식물류: X자 형태의 두 쿼드 (알파 컷아웃 타일)."""
    col = Color(brightness, brightness, brightness, 1)
    u0, v0, du, dv = textures.tile_uv(textures.tiles_for(bdef.id)[1])
    uv4 = ((u0, v0), (u0, v0 + dv), (u0 + du, v0 + dv), (u0 + du, v0))
    md.quad((x + 0.15, y, z + 0.15), (x + 0.15, y + 1.0, z + 0.15),
            (x + 0.85, y + 1.0, z + 0.85), (x + 0.85, y, z + 0.85),
            col, uv4)
    md.quad((x + 0.85, y, z + 0.15), (x + 0.85, y + 1.0, z + 0.15),
            (x + 0.15, y + 1.0, z + 0.85), (x + 0.15, y, z + 0.85),
            col, uv4)


def _emit_box(md, bdef, x, y, z, brightness,
              x0, y0, z0, x1, y1, z1):
    """부분 크기 박스 (반블록/울타리/문/횃불)."""
    tiles = textures.tiles_for(bdef.id)
    for f_idx, ((dx, dy, dz), corners, shade) in enumerate(FACES):
        tile_idx = tiles[0] if f_idx == 0 else tiles[2] if f_idx == 1 \
            else tiles[1]
        s = shade * brightness
        col = Color(s, s, s, 1)
        pts = []
        for (cx_, cy_, cz_) in corners:
            px = x + (x1 if cx_ else x0)
            py = y + (y1 if cy_ else y0)
            pz = z + (z1 if cz_ else z0)
            pts.append((px, py, pz))
        md.quad(pts[0], pts[1], pts[2], pts[3], col,
                _face_uvs(tile_idx, f_idx, corners))


# ---------------------------------------------------------------------------
# 엔티티 적용
# ---------------------------------------------------------------------------
_ATLAS_TEX = None


def _atlas_texture():
    """아틀라스 텍스처 로드 (1회, 최근접 필터로 픽셀 아트 유지)."""
    global _ATLAS_TEX
    if _ATLAS_TEX is None:
        textures.build()
        _ATLAS_TEX = load_texture(textures.ATLAS_PATH)
        if _ATLAS_TEX is not None:
            _ATLAS_TEX.filtering = None
    return _ATLAS_TEX


def apply_chunk_mesh(chunk, solid_data, alpha_data, ambient=1.0):
    """정점 데이터를 ursina 엔티티로 만든다 (기존 엔티티 교체)."""
    chunk.destroy_entities()
    origin = (chunk.cx * CHUNK, 0, chunk.cz * CHUNK)
    atlas = _atlas_texture()

    if solid_data:
        verts, tris, cols, uvs = solid_data
        chunk.solid_entity = Entity(
            model=Mesh(vertices=verts, triangles=tris, colors=cols,
                       uvs=uvs, mode='triangle', static=True),
            position=origin, double_sided=True, texture=atlas,
        )
        # 잎/식물 구멍용 알파 컷아웃
        chunk.solid_entity.setTransparency(TransparencyAttrib.M_binary)
    if alpha_data:
        verts, tris, cols, uvs = alpha_data
        chunk.alpha_entity = Entity(
            model=Mesh(vertices=verts, triangles=tris, colors=cols,
                       uvs=uvs, mode='triangle', static=True),
            position=origin, double_sided=True, texture=atlas,
        )
        chunk.alpha_entity.setTransparency(TransparencyAttrib.M_alpha)
    chunk.set_ambient(ambient)
    chunk.dirty = False
