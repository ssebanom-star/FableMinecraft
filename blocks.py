"""
blocks.py - 블록 데이터 정의 (데이터 중심).

모든 블록은 Block 인스턴스로 BLOCKS[id] 에 등록된다.
색상은 (r, g, b) 0~1 float. 텍스처 대신 면별 음영 + 정점 색으로 렌더링한다.
"""


class Block:
    __slots__ = (
        "id", "name", "display_name", "color", "top_color", "bottom_color",
        "hardness", "is_solid", "is_transparent", "is_liquid",
        "emits_light", "light_level", "drops", "required_tool",
        "required_tool_level", "break_time", "can_place", "collision_box",
        "item_id", "stack_size", "shape", "damage", "bounciness", "slipperiness",
    )

    def __init__(self, id, name, display_name, color,
                 top_color=None, bottom_color=None,
                 hardness=1.0, is_solid=True, is_transparent=False,
                 is_liquid=False, emits_light=False, light_level=0,
                 drops=None, required_tool=None, required_tool_level=0,
                 can_place=True, collision_box=True, item_id=None,
                 stack_size=64, shape="cube", damage=0,
                 bounciness=0.0, slipperiness=0.0):
        self.id = id
        self.name = name
        self.display_name = display_name
        self.color = color
        self.top_color = top_color or color
        self.bottom_color = bottom_color or color
        self.hardness = hardness                      # 0 = 즉시, <0 = 파괴 불가
        self.is_solid = is_solid
        self.is_transparent = is_transparent
        self.is_liquid = is_liquid
        self.emits_light = emits_light
        self.light_level = light_level
        # drops: [(item_id, count, probability)], None 이면 자기 자신 드롭
        self.drops = drops if drops is not None else [(name, 1, 1.0)]
        self.required_tool = required_tool            # "pickaxe"/"axe"/"shovel"/None
        self.required_tool_level = required_tool_level
        self.break_time = max(0.05, hardness * 1.2)   # 맨손 기준 기본 파괴 시간
        self.can_place = can_place
        self.collision_box = collision_box
        self.item_id = item_id or name
        self.stack_size = stack_size
        self.shape = shape                            # cube/cross/torch/slab/fence/door/liquid
        self.damage = damage                          # 접촉 피해
        self.bounciness = bounciness                  # 착지 반발 계수
        self.slipperiness = slipperiness              # 마찰 감소 (0~1)


BLOCKS = {}
BLOCK_BY_NAME = {}


def _reg(block):
    BLOCKS[block.id] = block
    BLOCK_BY_NAME[block.name] = block
    return block.id


def get_block_def(block_id):
    return BLOCKS.get(block_id, BLOCKS[0])


def block_id_by_name(name):
    b = BLOCK_BY_NAME.get(name)
    return b.id if b else 0


# ---------------------------------------------------------------------------
# 블록 ID 상수 + 등록 (총 56종)
# ---------------------------------------------------------------------------
# --- 자연 블록 ---
AIR = _reg(Block(0, "air", "공기", (0, 0, 0), hardness=0, is_solid=False,
                 is_transparent=True, drops=[], can_place=False,
                 collision_box=False, shape="none"))
GRASS = _reg(Block(1, "grass_block", "잔디 흙", (0.42, 0.32, 0.20),
                   top_color=(0.36, 0.62, 0.26), bottom_color=(0.40, 0.29, 0.18),
                   hardness=0.6, required_tool="shovel",
                   drops=[("dirt", 1, 1.0)]))
DIRT = _reg(Block(2, "dirt", "흙", (0.42, 0.30, 0.19), hardness=0.5,
                  required_tool="shovel"))
STONE = _reg(Block(3, "stone", "돌", (0.52, 0.52, 0.54), hardness=1.5,
                   required_tool="pickaxe", required_tool_level=0,
                   drops=[("cobblestone", 1, 1.0)]))
SAND = _reg(Block(4, "sand", "모래", (0.86, 0.80, 0.58), hardness=0.5,
                  required_tool="shovel"))
GRAVEL = _reg(Block(5, "gravel", "자갈", (0.55, 0.52, 0.50), hardness=0.6,
                    required_tool="shovel",
                    drops=[("gravel", 1, 0.85), ("flint", 1, 0.15)]))
CLAY = _reg(Block(6, "clay", "점토", (0.63, 0.66, 0.72), hardness=0.6,
                  required_tool="shovel", drops=[("clay_ball", 4, 1.0)]))
SNOW_BLOCK = _reg(Block(7, "snow_block", "눈", (0.94, 0.95, 0.97), hardness=0.3,
                        required_tool="shovel", drops=[("snowball", 4, 1.0)]))
ICE = _reg(Block(8, "ice", "얼음", (0.62, 0.78, 0.95), hardness=0.5,
                 is_transparent=True, required_tool="pickaxe",
                 drops=[], slipperiness=0.85))
WATER = _reg(Block(9, "water", "물", (0.18, 0.38, 0.75), hardness=-1,
                   is_solid=False, is_transparent=True, is_liquid=True,
                   drops=[], collision_box=False, shape="liquid"))
OAK_LOG = _reg(Block(10, "oak_log", "참나무 원목", (0.42, 0.31, 0.17),
                     top_color=(0.62, 0.50, 0.31), hardness=2.0,
                     required_tool="axe"))
OAK_LEAVES = _reg(Block(11, "oak_leaves", "참나무 잎", (0.22, 0.48, 0.16),
                        hardness=0.2, is_transparent=True,
                        drops=[("apple", 1, 0.06), ("stick", 1, 0.10),
                               ("oak_sapling", 1, 0.08)]))
CACTUS = _reg(Block(12, "cactus", "선인장", (0.20, 0.52, 0.22), hardness=0.4,
                    damage=1, drops=[("cactus", 1, 1.0)]))
TALL_GRASS = _reg(Block(13, "tall_grass", "풀", (0.32, 0.60, 0.22), hardness=0,
                        is_solid=False, is_transparent=True,
                        collision_box=False, shape="cross",
                        drops=[("seeds", 1, 0.3)]))
FLOWER_RED = _reg(Block(14, "flower_red", "붉은 꽃", (0.85, 0.20, 0.22),
                        hardness=0, is_solid=False, is_transparent=True,
                        collision_box=False, shape="cross"))
FLOWER_YELLOW = _reg(Block(15, "flower_yellow", "노란 꽃", (0.92, 0.83, 0.20),
                           hardness=0, is_solid=False, is_transparent=True,
                           collision_box=False, shape="cross"))
MUSHROOM = _reg(Block(16, "mushroom", "버섯", (0.72, 0.45, 0.35), hardness=0,
                      is_solid=False, is_transparent=True,
                      collision_box=False, shape="cross"))

# --- 광물 블록 ---
COAL_ORE = _reg(Block(17, "coal_ore", "석탄 광석", (0.45, 0.45, 0.46),
                      top_color=(0.30, 0.30, 0.31),
                      hardness=3.0, required_tool="pickaxe",
                      required_tool_level=1, drops=[("coal", 1, 1.0)]))
COPPER_ORE = _reg(Block(18, "copper_ore", "구리 광석", (0.55, 0.44, 0.36),
                        hardness=3.0, required_tool="pickaxe",
                        required_tool_level=1, drops=[("raw_copper", 1, 1.0)]))
IRON_ORE = _reg(Block(19, "iron_ore", "철 광석", (0.58, 0.50, 0.45),
                      hardness=3.5, required_tool="pickaxe",
                      required_tool_level=1, drops=[("raw_iron", 1, 1.0)]))
GOLD_ORE = _reg(Block(20, "gold_ore", "금 광석", (0.62, 0.56, 0.32),
                      hardness=3.5, required_tool="pickaxe",
                      required_tool_level=2, drops=[("raw_gold", 1, 1.0)]))
CRYSTAL_ORE = _reg(Block(21, "crystal_ore", "수정 광석", (0.48, 0.40, 0.62),
                         hardness=4.0, required_tool="pickaxe",
                         required_tool_level=2, drops=[("crystal", 1, 1.0)],
                         emits_light=True, light_level=5))
ENERGY_ORE = _reg(Block(22, "energy_ore", "에너지 광석", (0.72, 0.30, 0.25),
                        hardness=3.5, required_tool="pickaxe",
                        required_tool_level=2,
                        drops=[("energy_dust", 2, 1.0)],
                        emits_light=True, light_level=7))
DARKROCK = _reg(Block(23, "darkrock", "흑암", (0.16, 0.13, 0.22), hardness=12.0,
                      required_tool="pickaxe", required_tool_level=3))

# --- 건축 블록 ---
PLANKS = _reg(Block(24, "planks", "나무 판자", (0.66, 0.53, 0.33), hardness=1.5,
                    required_tool="axe"))
COBBLESTONE = _reg(Block(25, "cobblestone", "조약돌", (0.44, 0.44, 0.46),
                         hardness=2.0, required_tool="pickaxe"))
STONE_BRICKS = _reg(Block(26, "stone_bricks", "돌벽돌", (0.48, 0.48, 0.51),
                          hardness=2.0, required_tool="pickaxe"))
BRICKS = _reg(Block(27, "bricks", "벽돌", (0.62, 0.34, 0.28), hardness=2.0,
                    required_tool="pickaxe"))
GLASS = _reg(Block(28, "glass", "유리", (0.75, 0.85, 0.90), hardness=0.3,
                   is_transparent=True, drops=[("glass_shard", 1, 0.6)]))
SMOOTH_STONE = _reg(Block(29, "smooth_stone", "매끄러운 돌", (0.62, 0.62, 0.64),
                          hardness=2.0, required_tool="pickaxe"))
WOOD_STAIRS = _reg(Block(30, "wood_stairs", "나무 계단", (0.60, 0.48, 0.30),
                         hardness=1.5, required_tool="axe", shape="slab"))
STONE_SLAB = _reg(Block(31, "stone_slab", "돌 반블록", (0.58, 0.58, 0.60),
                        hardness=2.0, required_tool="pickaxe", shape="slab"))
FENCE = _reg(Block(32, "fence", "울타리", (0.55, 0.43, 0.26), hardness=1.5,
                   required_tool="axe", is_transparent=True, shape="fence"))
DOOR = _reg(Block(33, "door", "문", (0.58, 0.44, 0.26), hardness=1.5,
                  required_tool="axe", is_transparent=True, shape="door"))
DOOR_OPEN = _reg(Block(34, "door_open", "문(열림)", (0.58, 0.44, 0.26),
                       hardness=1.5, required_tool="axe", is_solid=False,
                       is_transparent=True, collision_box=False, shape="door",
                       drops=[("door", 1, 1.0)], can_place=False))
TORCH = _reg(Block(35, "torch", "횃불", (0.95, 0.75, 0.30), hardness=0,
                   is_solid=False, is_transparent=True, collision_box=False,
                   shape="torch", emits_light=True, light_level=14))
WORKBENCH = _reg(Block(36, "workbench", "작업대", (0.55, 0.40, 0.22),
                       top_color=(0.68, 0.55, 0.34), hardness=1.5,
                       required_tool="axe"))
FURNACE = _reg(Block(37, "furnace", "화로", (0.40, 0.40, 0.42),
                     top_color=(0.35, 0.35, 0.37), hardness=2.5,
                     required_tool="pickaxe"))
CHEST = _reg(Block(38, "chest", "상자", (0.60, 0.45, 0.22),
                   top_color=(0.70, 0.55, 0.30), hardness=1.5,
                   required_tool="axe"))

# --- 특수 블록 ---
GLOWSTONE = _reg(Block(39, "glowstone", "발광 블록", (0.95, 0.85, 0.45),
                       hardness=0.5, emits_light=True, light_level=15,
                       drops=[("glow_dust", 3, 1.0)]))
THORN_BLOCK = _reg(Block(40, "thorn_block", "가시 블록", (0.35, 0.28, 0.20),
                         hardness=0.8, damage=2))
SLIME_BLOCK = _reg(Block(41, "slime_block", "탄성 블록", (0.45, 0.78, 0.40),
                         hardness=0.3, is_transparent=True, bounciness=0.8))
SLICK_BLOCK = _reg(Block(42, "slick_block", "미끄럼 블록", (0.55, 0.72, 0.88),
                         hardness=0.6, required_tool="pickaxe",
                         slipperiness=0.92))
BOOM_BLOCK = _reg(Block(43, "boom_block", "폭발 블록", (0.75, 0.25, 0.20),
                        top_color=(0.85, 0.70, 0.30), hardness=0.2))
BEDROCK = _reg(Block(44, "bedrock", "기반암", (0.20, 0.20, 0.22), hardness=-1,
                     drops=[], can_place=False))

# --- 추가 자연/건축 블록 (50종 이상 충족) ---
BIRCH_LOG = _reg(Block(45, "birch_log", "자작나무 원목", (0.82, 0.80, 0.72),
                       top_color=(0.75, 0.70, 0.55), hardness=2.0,
                       required_tool="axe"))
BIRCH_LEAVES = _reg(Block(46, "birch_leaves", "자작나무 잎", (0.42, 0.62, 0.28),
                          hardness=0.2, is_transparent=True,
                          drops=[("stick", 1, 0.1)]))
SPRUCE_LOG = _reg(Block(47, "spruce_log", "가문비 원목", (0.30, 0.22, 0.12),
                        hardness=2.0, required_tool="axe"))
SPRUCE_LEAVES = _reg(Block(48, "spruce_leaves", "가문비 잎", (0.16, 0.36, 0.20),
                           hardness=0.2, is_transparent=True,
                           drops=[("stick", 1, 0.1)]))
MUD = _reg(Block(49, "mud", "진흙", (0.30, 0.24, 0.18), hardness=0.5,
                 required_tool="shovel"))
SANDSTONE = _reg(Block(50, "sandstone", "사암", (0.80, 0.74, 0.52),
                       hardness=1.8, required_tool="pickaxe"))
MOSSY_COBBLE = _reg(Block(51, "mossy_cobblestone", "이끼 조약돌",
                          (0.38, 0.46, 0.36), hardness=2.0,
                          required_tool="pickaxe"))
CRYSTAL_BLOCK = _reg(Block(52, "crystal_block", "수정 블록", (0.60, 0.50, 0.80),
                           hardness=4.0, required_tool="pickaxe",
                           required_tool_level=2, emits_light=True,
                           light_level=10))
PUMPKIN = _reg(Block(53, "pumpkin", "호박", (0.85, 0.50, 0.15),
                     top_color=(0.60, 0.40, 0.15), hardness=1.0,
                     required_tool="axe"))
DEAD_BUSH = _reg(Block(54, "dead_bush", "마른 덤불", (0.55, 0.42, 0.25),
                       hardness=0, is_solid=False, is_transparent=True,
                       collision_box=False, shape="cross",
                       drops=[("stick", 2, 0.7)]))
SNOW_LAYER = _reg(Block(55, "snow_layer", "눈 덮개", (0.96, 0.97, 1.0),
                        hardness=0.1, is_solid=False, is_transparent=True,
                        collision_box=False, shape="slab",
                        drops=[("snowball", 1, 1.0)],
                        required_tool="shovel"))

# ---------------------------------------------------------------------------
# 렌더링/판정용 헬퍼 집합
# ---------------------------------------------------------------------------
OPAQUE_IDS = frozenset(
    b.id for b in BLOCKS.values()
    if b.is_solid and not b.is_transparent and b.shape == "cube"
)
SOLID_IDS = frozenset(b.id for b in BLOCKS.values() if b.collision_box)
LIGHT_SOURCE_IDS = frozenset(b.id for b in BLOCKS.values() if b.emits_light)
CROSS_SHAPE_IDS = frozenset(
    b.id for b in BLOCKS.values() if b.shape in ("cross", "torch")
)
INTERACTABLE_IDS = frozenset({WORKBENCH, FURNACE, CHEST, DOOR, DOOR_OPEN})


def is_opaque(block_id):
    return block_id in OPAQUE_IDS


def is_solid(block_id):
    return block_id in SOLID_IDS
