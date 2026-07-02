"""
textures.py - 절차적 텍스처 아틀라스 생성.

외부 이미지 에셋 없이 코드로 16x16 픽셀 타일을 그려 256x256 아틀라스
(assets/atlas.png) 를 만든다. 해시 기반 난수라 실행할 때마다 동일하다.

TILE_MAP[block_id] = (top_tile, side_tile, bottom_tile)
tile_uv(idx)       = (u0, v0, du, dv)   # 블리딩 방지 인셋 포함
"""

import os
import zlib

from PIL import Image

import blocks as B

TILE = 16                 # 타일 한 변 픽셀
GRID = 16                 # 아틀라스 한 변 타일 수 (16x16 = 256 타일)
ATLAS_PX = TILE * GRID
ATLAS_PATH = os.path.join("assets", "atlas.png")

TILE_MAP = {}             # block_id -> (top, side, bottom)
_alloc = {}               # 캐시 키 -> 타일 인덱스
_img = None
_next = 0
_built = False


# ---------------------------------------------------------------------------
# 유틸
# ---------------------------------------------------------------------------
def _rand(key, x, y=0):
    """결정론적 [0,1) 난수."""
    h = zlib.crc32(f"{key}|{x}|{y}".encode())
    return (h & 0xFFFFFF) / 0x1000000


def _c255(c):
    return (int(c[0] * 255), int(c[1] * 255), int(c[2] * 255))


def _sh(c, f, a=255):
    """색 밝기 조절 + 알파."""
    return (max(0, min(255, int(c[0] * f))),
            max(0, min(255, int(c[1] * f))),
            max(0, min(255, int(c[2] * f))), a)


def _tile_origin(idx):
    return (idx % GRID) * TILE, (idx // GRID) * TILE


def _draw(idx, fn):
    ox, oy = _tile_origin(idx)
    px = _img.load()

    def put(x, y, rgba):
        px[ox + x, oy + y] = rgba
    fn(put)


def _alloc_tile(key, fn):
    """같은 key 는 같은 타일 재사용."""
    global _next
    if key in _alloc:
        return _alloc[key]
    idx = _next
    _next += 1
    _alloc[key] = idx
    _draw(idx, fn)
    return idx


# ---------------------------------------------------------------------------
# 패턴 함수 (put(x,y,rgba) 를 받아 16x16 을 채운다)
# ---------------------------------------------------------------------------
def p_speckle(key, base, var=0.10, alpha=255):
    def fn(put):
        for y in range(TILE):
            for x in range(TILE):
                f = 1.0 + (_rand(key, x, y) - 0.5) * 2 * var
                put(x, y, _sh(base, f, alpha))
    return fn


def p_grass_top(key, green):
    def fn(put):
        for y in range(TILE):
            for x in range(TILE):
                f = 0.88 + _rand(key, x, y) * 0.28
                put(x, y, _sh(green, f))
        # 밝은 풀잎 몇 가닥
        for i in range(10):
            x = int(_rand(key + "b", i) * TILE)
            y = int(_rand(key + "c", i) * TILE)
            put(x, y, _sh(green, 1.35))
    return fn


def p_grass_side(key, dirt, green):
    def fn(put):
        for y in range(TILE):
            for x in range(TILE):
                f = 0.9 + _rand(key, x, y) * 0.2
                put(x, y, _sh(dirt, f))
        for x in range(TILE):
            depth = 3 + int(_rand(key + "e", x) * 3)   # 들쭉날쭉한 경계
            for y in range(depth):
                f = 0.9 + _rand(key + "g", x, y) * 0.3
                put(x, y, _sh(green, f))
    return fn


def p_bark(key, base):
    def fn(put):
        for x in range(TILE):
            stripe = 0.75 + _rand(key + "s", x) * 0.45
            for y in range(TILE):
                f = stripe * (0.9 + _rand(key, x, y) * 0.2)
                put(x, y, _sh(base, f))
    return fn


def p_rings(key, base):
    def fn(put):
        cx = cy = TILE / 2 - 0.5
        for y in range(TILE):
            for x in range(TILE):
                d = max(abs(x - cx), abs(y - cy))
                ring = 1.15 if int(d) % 2 == 0 else 0.8
                f = ring * (0.92 + _rand(key, x, y) * 0.16)
                put(x, y, _sh(base, f))
    return fn


def p_leaves(key, base):
    def fn(put):
        for y in range(TILE):
            for x in range(TILE):
                r = _rand(key, x, y)
                if r < 0.10:
                    put(x, y, (0, 0, 0, 0))            # 구멍
                elif r < 0.30:
                    put(x, y, _sh(base, 0.65))
                else:
                    put(x, y, _sh(base, 0.85 + r * 0.45))
    return fn


def p_planks(key, base):
    def fn(put):
        for y in range(TILE):
            board = y // 4
            for x in range(TILE):
                f = 0.9 + _rand(key, x + board * 31, y) * 0.22
                if y % 4 == 3:
                    f *= 0.6                            # 판자 사이 홈
                if (x + board * 5) % 8 == 0:
                    f *= 0.8                            # 세로 이음매
                put(x, y, _sh(base, f))
    return fn


def p_cobble(key, base):
    def fn(put):
        for y in range(TILE):
            for x in range(TILE):
                cx, cy = x // 5, y // 5
                cell = 0.8 + _rand(key + "c", cx, cy) * 0.4
                ex, ey = x % 5, y % 5
                edge = 0.55 if ex == 0 or ey == 0 else 1.0
                f = cell * edge * (0.92 + _rand(key, x, y) * 0.16)
                put(x, y, _sh(base, f))
    return fn


def p_bricks(key, base, mortar=(150, 148, 145)):
    def fn(put):
        for y in range(TILE):
            row = y // 4
            for x in range(TILE):
                off = (row % 2) * 4
                if y % 4 == 3 or (x + off) % 8 == 7:
                    put(x, y, (mortar[0], mortar[1], mortar[2], 255))
                else:
                    f = 0.88 + _rand(key, x + row * 17, y) * 0.24
                    put(x, y, _sh(base, f))
    return fn


def p_stone_bricks(key, base):
    def fn(put):
        for y in range(TILE):
            for x in range(TILE):
                bx, by = x // 8, y // 8
                f = 0.85 + _rand(key + "b", bx, by) * 0.3
                if x % 8 == 0 or y % 8 == 0:
                    f = 0.5
                f *= 0.94 + _rand(key, x, y) * 0.12
                put(x, y, _sh(base, f))
    return fn


def p_ore(key, stone, ore, glow=False):
    def fn(put):
        for y in range(TILE):
            for x in range(TILE):
                f = 0.9 + _rand(key, x, y) * 0.2
                put(x, y, _sh(stone, f))
        for i in range(5):                              # 광맥 덩어리
            bx = 1 + int(_rand(key + "x", i) * (TILE - 4))
            by = 1 + int(_rand(key + "y", i) * (TILE - 4))
            size = 2 + int(_rand(key + "s", i) * 2)
            for dy in range(size):
                for dx in range(size):
                    if _rand(key + "d", bx + dx, by + dy) < 0.8:
                        put(bx + dx, by + dy, _sh(ore, 1.0))
            put(bx, by, _sh(ore, 1.5 if glow else 1.3))  # 하이라이트
    return fn


def p_glass(key, base):
    def fn(put):
        for y in range(TILE):
            for x in range(TILE):
                if x in (0, TILE - 1) or y in (0, TILE - 1):
                    put(x, y, _sh(base, 1.1, 220))       # 테두리
                elif (x + y) % 7 == 0 and x < 8:
                    put(x, y, _sh(base, 1.3, 150))       # 광택 사선
                else:
                    put(x, y, _sh(base, 1.0, 70))
    return fn


def p_water(key, base):
    def fn(put):
        for y in range(TILE):
            wave = 1.15 if y % 4 == 0 else 1.0
            for x in range(TILE):
                f = wave * (0.85 + _rand(key, x, y // 2) * 0.3)
                put(x, y, _sh(base, f))
    return fn


def p_glow(key, base):
    def fn(put):
        for y in range(TILE):
            for x in range(TILE):
                r = _rand(key, x, y)
                f = 1.25 if r > 0.72 else 0.85 + r * 0.4
                put(x, y, _sh(base, f))
    return fn


def p_cactus(key, base):
    def fn(put):
        for y in range(TILE):
            for x in range(TILE):
                rib = 0.75 if x % 4 == 0 else 1.0
                f = rib * (0.9 + _rand(key, x, y) * 0.2)
                put(x, y, _sh(base, f))
        for i in range(6):                              # 가시
            x = int(_rand(key + "t", i) * TILE)
            y = int(_rand(key + "u", i) * TILE)
            put(x, y, (235, 240, 210, 255))
    return fn


def p_furnace_side(key, stone):
    cob = p_cobble(key, stone)
    def fn(put):
        cob(put)
        for y in range(9, 14):                          # 아궁이
            for x in range(4, 12):
                put(x, y, (25, 22, 20, 255))
        for x in range(5, 11, 2):                       # 불씨
            put(x, 12, (250, 140, 30, 255))
            put(x + 1, 11, (255, 200, 60, 255))
    return fn


def p_chest_side(key, base):
    pl = p_planks(key, base)
    def fn(put):
        pl(put)
        for i in range(TILE):                           # 테두리
            put(i, 0, _sh(base, 0.5))
            put(i, TILE - 1, _sh(base, 0.5))
            put(0, i, _sh(base, 0.5))
            put(TILE - 1, i, _sh(base, 0.5))
        for y in range(6, 10):                          # 잠금쇠
            for x in range(6, 10):
                put(x, y, (200, 200, 205, 255))
        put(7, 8, (90, 90, 95, 255))
        put(8, 8, (90, 90, 95, 255))
    return fn


def p_workbench_top(key, base):
    pl = p_planks(key, base)
    def fn(put):
        pl(put)
        for i in range(TILE):                           # 작업 그리드
            put(i, 5, _sh(base, 0.5))
            put(i, 10, _sh(base, 0.5))
            put(5, i, _sh(base, 0.5))
            put(10, i, _sh(base, 0.5))
    return fn


def p_torch(key):
    def fn(put):
        for y in range(TILE):
            for x in range(TILE):
                put(x, y, (0, 0, 0, 0))
        for y in range(6, 14):                          # 자루
            put(7, y, (110, 85, 50, 255))
            put(8, y, (95, 70, 40, 255))
        for y in range(3, 6):                           # 불꽃
            for x in range(6, 10):
                put(x, y, (255, 210, 90, 255))
        put(7, 2, (255, 245, 200, 255))
        put(8, 2, (255, 245, 200, 255))
        put(7, 4, (250, 150, 40, 255))
    return fn


def p_plant(key, kind, color):
    def fn(put):
        for y in range(TILE):
            for x in range(TILE):
                put(x, y, (0, 0, 0, 0))
        if kind == "grass":
            for i in range(6):                          # 풀잎 다발
                x = 2 + int(_rand(key, i) * 12)
                h = 5 + int(_rand(key + "h", i) * 9)
                for y in range(TILE - h, TILE):
                    xx = x + (1 if y < TILE - h + 2 and i % 2 else 0)
                    if 0 <= xx < TILE:
                        put(xx, y, _sh(color, 0.8 + _rand(key, xx, y) * 0.5))
        elif kind == "flower":
            for y in range(8, TILE):                    # 줄기
                put(7, y, (60, 120, 45, 255))
            for dy in range(-2, 3):                     # 꽃송이
                for dx in range(-2, 3):
                    if abs(dx) + abs(dy) <= 2:
                        put(7 + dx, 6 + dy, _sh(color, 1.0))
            put(7, 6, _sh(color, 1.5))
        elif kind == "mushroom":
            for y in range(9, TILE):
                put(7, y, (225, 215, 190, 255))
                put(8, y, (205, 195, 170, 255))
            for x in range(4, 12):                      # 갓
                for y in range(5, 9):
                    if 4 + abs(x - 7) // 2 <= y:
                        put(x, y, _sh(color, 0.9 + _rand(key, x, y) * 0.3))
        else:                                           # deadbush
            for i in range(5):
                x = 3 + int(_rand(key, i) * 10)
                for y in range(6 + i, TILE):
                    xx = x + (y % 3) - 1
                    if 0 <= xx < TILE:
                        put(xx, y, _sh(color, 0.75 + _rand(key, xx, y) * 0.4))
    return fn


def p_danger(key, base):
    def fn(put):
        for y in range(TILE):
            for x in range(TILE):
                f = 0.9 + _rand(key, x, y) * 0.2
                put(x, y, _sh(base, f))
        for y in range(TILE):                           # 대각 경고 줄
            for x in range(TILE):
                if (x + y) % 8 < 2:
                    put(x, y, (240, 205, 60, 255))
    return fn


def p_bedrock(key):
    def fn(put):
        for y in range(TILE):
            for x in range(TILE):
                r = _rand(key, x, y)
                v = int(35 + r * 65)
                put(x, y, (v, v, v + 4, 255))
    return fn


def p_sandstone(key, base):
    def fn(put):
        for y in range(TILE):
            band = 1.06 if (y // 4) % 2 == 0 else 0.92
            for x in range(TILE):
                f = band * (0.94 + _rand(key, x, y) * 0.12)
                put(x, y, _sh(base, f))
    return fn


def p_pumpkin(key, base):
    def fn(put):
        for y in range(TILE):
            for x in range(TILE):
                rib = 0.8 if x % 5 == 0 else 1.0
                f = rib * (0.9 + _rand(key, x, y) * 0.2)
                put(x, y, _sh(base, f))
    return fn


def p_door(key, base):
    pl = p_planks(key, base)
    def fn(put):
        pl(put)
        for x in range(4, 12):                          # 창
            for y in range(3, 7):
                put(x, y, (185, 215, 230, 255))
        for i in range(TILE):
            put(0, i, _sh(base, 0.5))
            put(TILE - 1, i, _sh(base, 0.5))
    return fn


def p_ice(key, base):
    def fn(put):
        for y in range(TILE):
            for x in range(TILE):
                f = 0.95 + _rand(key, x, y) * 0.15
                put(x, y, _sh(base, f, 235))
        for i in range(8):                              # 균열
            x = int(_rand(key + "k", i) * TILE)
            y = int(_rand(key + "l", i) * TILE)
            put(x, y, (240, 250, 255, 235))
    return fn


def p_white():
    def fn(put):
        for y in range(TILE):
            for x in range(TILE):
                put(x, y, (255, 255, 255, 255))
    return fn


# ---------------------------------------------------------------------------
# 블록 -> 타일 매핑
# ---------------------------------------------------------------------------
def _assign(block):
    """블록 정의로부터 (top, side, bottom) 타일 인덱스."""
    n = block.name
    top = _c255(block.top_color)
    side = _c255(block.color)
    bot = _c255(block.bottom_color)
    STONE = (133, 133, 138)

    def spk(key, c, var=0.10):
        return _alloc_tile(key, p_speckle(key, c, var))

    if n == "grass_block":
        return (_alloc_tile("grass_top", p_grass_top("gt", top)),
                _alloc_tile("grass_side", p_grass_side("gs", side, top)),
                spk("dirt", _c255(B.BLOCKS[B.DIRT].color)))
    if n.endswith("_log"):
        return (_alloc_tile(n + "_top", p_rings(n + "t", top)),
                _alloc_tile(n + "_side", p_bark(n + "s", side)),
                _alloc_tile(n + "_top", p_rings(n + "t", top)))
    if n.endswith("leaves"):
        t = _alloc_tile(n, p_leaves(n, side))
        return (t, t, t)
    if n in ("planks", "fence", "wood_stairs"):
        t = _alloc_tile("planks", p_planks("pl", _c255(
            B.BLOCKS[B.PLANKS].color)))
        return (t, t, t)
    if n in ("cobblestone", "mossy_cobblestone"):
        t = _alloc_tile(n, p_cobble(n, side))
        return (t, t, t)
    if n == "stone_bricks":
        t = _alloc_tile(n, p_stone_bricks(n, side))
        return (t, t, t)
    if n == "bricks":
        t = _alloc_tile(n, p_bricks(n, side))
        return (t, t, t)
    if n.endswith("_ore"):
        t = _alloc_tile(n, p_ore(n, STONE, side, glow=block.emits_light))
        return (t, t, t)
    if n == "glass":
        t = _alloc_tile(n, p_glass(n, side))
        return (t, t, t)
    if n == "ice" or n == "slick_block":
        t = _alloc_tile(n, p_ice(n, side))
        return (t, t, t)
    if n == "water":
        t = _alloc_tile(n, p_water(n, side))
        return (t, t, t)
    if n in ("glowstone", "crystal_block", "energy_ore"):
        t = _alloc_tile(n, p_glow(n, side))
        return (t, t, t)
    if n == "cactus":
        t = _alloc_tile(n, p_cactus(n, side))
        return (spk(n + "t", top, 0.08), t, t)
    if n == "furnace":
        return (spk("furn_top", top, 0.08),
                _alloc_tile("furn_side", p_furnace_side("fs", side)),
                spk("furn_top", top, 0.08))
    if n == "chest":
        return (_alloc_tile("chest_top", p_planks("ct", top)),
                _alloc_tile("chest_side", p_chest_side("cs", side)),
                _alloc_tile("chest_top", p_planks("ct", top)))
    if n == "workbench":
        return (_alloc_tile("wb_top", p_workbench_top("wt", top)),
                _alloc_tile("wb_side", p_chest_side("ws", side)),
                _alloc_tile("planks", p_planks("pl", side)))
    if n == "torch":
        t = _alloc_tile(n, p_torch(n))
        return (t, t, t)
    if n == "tall_grass":
        t = _alloc_tile(n, p_plant(n, "grass", side))
        return (t, t, t)
    if n in ("flower_red", "flower_yellow"):
        t = _alloc_tile(n, p_plant(n, "flower", side))
        return (t, t, t)
    if n == "mushroom":
        t = _alloc_tile(n, p_plant(n, "mushroom", side))
        return (t, t, t)
    if n == "dead_bush":
        t = _alloc_tile(n, p_plant(n, "bush", side))
        return (t, t, t)
    if n == "boom_block":
        return (_alloc_tile("boom_top", p_speckle("bt", top, 0.15)),
                _alloc_tile("boom_side", p_danger("bs", side)),
                _alloc_tile("boom_top", p_speckle("bt", top, 0.15)))
    if n == "bedrock" or n == "darkrock":
        t = _alloc_tile(n, p_bedrock(n))
        return (t, t, t)
    if n == "sandstone":
        t = _alloc_tile(n, p_sandstone(n, side))
        return (t, t, t)
    if n == "pumpkin":
        return (spk("pk_top", top, 0.1),
                _alloc_tile("pk_side", p_pumpkin("pk", side)),
                spk("pk_top", top, 0.1))
    if n in ("door", "door_open"):
        t = _alloc_tile("door", p_door("door", side))
        return (t, t, t)
    if n in ("gravel",):
        t = _alloc_tile(n, p_speckle(n, side, 0.28))
        return (t, t, t)
    # 기본: 스펙클
    return (spk(n + "_t", top, 0.09), spk(n + "_s", side, 0.09),
            spk(n + "_b", bot, 0.09))


def build():
    """아틀라스 생성 + 저장. 여러 번 불러도 1회만 수행."""
    global _img, _built, _next
    if _built:
        return
    _img = Image.new("RGBA", (ATLAS_PX, ATLAS_PX), (255, 0, 255, 255))
    _next = 0
    _alloc.clear()
    _alloc_tile("white", p_white())          # 0번: 흰색 (엔티티/기본)

    for block in B.BLOCKS.values():
        if block.name == "air":
            continue
        TILE_MAP[block.id] = _assign(block)

    os.makedirs(os.path.dirname(ATLAS_PATH), exist_ok=True)
    _img.save(ATLAS_PATH)
    _built = True


def tile_uv(idx):
    """타일 인덱스 -> (u0, v0, du, dv). 블리딩 방지 0.35px 인셋."""
    col = idx % GRID
    row = idx // GRID
    inset = 0.35
    u0 = (col * TILE + inset) / ATLAS_PX
    v0 = ((GRID - 1 - row) * TILE + inset) / ATLAS_PX
    span = (TILE - 2 * inset) / ATLAS_PX
    return u0, v0, span, span


def tiles_for(block_id):
    return TILE_MAP.get(block_id, (0, 0, 0))
