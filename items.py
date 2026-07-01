"""
items.py - 아이템 데이터 정의 (데이터 중심).

- 블록 아이템은 blocks.py 의 등록 정보로부터 자동 생성된다.
- 도구/무기/음식/장비/자원 아이템은 아래에서 직접 정의한다.
- 아이템 스택은 dict {"id", "count", ["durability"]} 로 표현해 JSON 저장이 쉽다.
"""

import blocks


class Item:
    __slots__ = (
        "id", "name", "category", "color", "stack_size",
        "max_durability", "attack_damage", "attack_speed", "mining_speed",
        "tool_type", "tool_level", "food_value", "heal_value", "eat_time",
        "placeable_block_id", "fuel_time", "smelt_result", "rarity",
        "description", "armor_value", "slot_type", "range",
        "projectile_type", "movement_modifier", "can_eat_when_full",
    )

    def __init__(self, id, name, category="misc", color=(0.8, 0.8, 0.8),
                 stack_size=64, max_durability=0, attack_damage=1,
                 attack_speed=2.5, mining_speed=1.0, tool_type=None,
                 tool_level=0, food_value=0, heal_value=0, eat_time=1.2,
                 placeable_block_id=None, fuel_time=0, smelt_result=None,
                 rarity="common", description="", armor_value=0,
                 slot_type=None, range=3.2, projectile_type=None,
                 movement_modifier=1.0, can_eat_when_full=False):
        self.id = id
        self.name = name
        self.category = category
        self.color = color
        self.stack_size = stack_size
        self.max_durability = max_durability
        self.attack_damage = attack_damage
        self.attack_speed = attack_speed
        self.mining_speed = mining_speed
        self.tool_type = tool_type
        self.tool_level = tool_level
        self.food_value = food_value
        self.heal_value = heal_value
        self.eat_time = eat_time
        self.placeable_block_id = placeable_block_id
        self.fuel_time = fuel_time
        self.smelt_result = smelt_result
        self.rarity = rarity
        self.description = description
        self.armor_value = armor_value
        self.slot_type = slot_type          # "helmet"/"chestplate" 등
        self.range = range
        self.projectile_type = projectile_type
        self.movement_modifier = movement_modifier
        self.can_eat_when_full = can_eat_when_full


ITEMS = {}


def _reg(item):
    ITEMS[item.id] = item
    return item


def get_item(item_id):
    return ITEMS.get(item_id)


# ---------------------------------------------------------------------------
# 1) 블록 아이템 자동 등록
# ---------------------------------------------------------------------------
_BLOCK_ITEM_OVERRIDES = {
    "torch": dict(fuel_time=4),
    "planks": dict(fuel_time=8),
    "oak_log": dict(fuel_time=15),
    "birch_log": dict(fuel_time=15),
    "spruce_log": dict(fuel_time=15),
    "workbench": dict(fuel_time=10),
    "chest": dict(fuel_time=10),
    "fence": dict(fuel_time=6),
    "sand": dict(smelt_result=("glass", 1)),
    "cobblestone": dict(smelt_result=("stone", 1)),
    "stone": dict(smelt_result=("smooth_stone", 1)),
    "cactus": dict(food_value=1, category="food", eat_time=1.0),
    "glowstone": dict(rarity="uncommon"),
    "crystal_block": dict(rarity="rare"),
}

for _b in blocks.BLOCKS.values():
    if _b.name == "air" or not _b.can_place:
        continue
    extra = _BLOCK_ITEM_OVERRIDES.get(_b.name, {})
    _reg(Item(
        _b.name, _b.display_name, category=extra.get("category", "block"),
        color=_b.top_color, stack_size=_b.stack_size,
        placeable_block_id=_b.id,
        fuel_time=extra.get("fuel_time", 0),
        smelt_result=extra.get("smelt_result"),
        food_value=extra.get("food_value", 0),
        eat_time=extra.get("eat_time", 1.2),
        rarity=extra.get("rarity", "common"),
        description=f"{_b.display_name} 블록을 설치할 수 있다.",
    ))

# ---------------------------------------------------------------------------
# 2) 자원 아이템
# ---------------------------------------------------------------------------
_reg(Item("stick", "막대기", "resource", (0.55, 0.42, 0.24), fuel_time=3,
          description="도구와 무기의 손잡이 재료."))
_reg(Item("coal", "석탄", "resource", (0.15, 0.15, 0.15), fuel_time=60,
          description="가장 기본적인 연료."))
_reg(Item("raw_copper", "구리 원석", "resource", (0.72, 0.48, 0.35),
          smelt_result=("copper_ingot", 1)))
_reg(Item("raw_iron", "철 원석", "resource", (0.78, 0.68, 0.60),
          smelt_result=("iron_ingot", 1)))
_reg(Item("raw_gold", "금 원석", "resource", (0.88, 0.75, 0.35),
          smelt_result=("gold_ingot", 1)))
_reg(Item("copper_ingot", "구리괴", "resource", (0.80, 0.50, 0.32)))
_reg(Item("iron_ingot", "철괴", "resource", (0.85, 0.85, 0.88)))
_reg(Item("gold_ingot", "금괴", "resource", (0.95, 0.82, 0.30),
          rarity="uncommon"))
_reg(Item("crystal", "수정", "resource", (0.70, 0.58, 0.92), rarity="rare",
          description="가장 단단한 도구/장비의 재료."))
_reg(Item("energy_dust", "에너지 가루", "resource", (0.95, 0.40, 0.30),
          rarity="rare", fuel_time=120))
_reg(Item("glass_shard", "유리 조각", "resource", (0.80, 0.90, 0.95)))
_reg(Item("leather", "가죽", "resource", (0.60, 0.40, 0.22)))
_reg(Item("string", "실", "resource", (0.90, 0.90, 0.90)))
_reg(Item("bone", "뼈", "resource", (0.92, 0.90, 0.82)))
_reg(Item("gunpowder", "화약", "resource", (0.45, 0.45, 0.45)))
_reg(Item("seeds", "씨앗", "resource", (0.50, 0.70, 0.30)))
_reg(Item("wheat", "밀", "resource", (0.85, 0.75, 0.35)))
_reg(Item("clay_ball", "점토 덩이", "resource", (0.66, 0.70, 0.76),
          smelt_result=("brick_item", 1)))
_reg(Item("brick_item", "벽돌 조각", "resource", (0.68, 0.36, 0.28)))
_reg(Item("snowball", "눈덩이", "resource", (0.95, 0.96, 1.0), stack_size=16))
_reg(Item("flint", "부싯돌", "resource", (0.30, 0.30, 0.32)))
_reg(Item("glow_dust", "발광 가루", "resource", (0.95, 0.88, 0.50),
          rarity="uncommon"))
_reg(Item("feather", "깃털", "resource", (0.95, 0.95, 0.95)))
_reg(Item("oak_sapling", "묘목", "resource", (0.35, 0.60, 0.25)))
_reg(Item("spider_eye", "거미 눈", "resource", (0.60, 0.15, 0.20)))

# ---------------------------------------------------------------------------
# 3) 도구 아이템
# ---------------------------------------------------------------------------
_TOOL_TIERS = {
    # tier: (레벨, 채굴속도, 내구도, 공격력 보정, 색)
    "wooden": (1, 2.0, 60, 0, (0.62, 0.48, 0.28)),
    "stone": (2, 4.0, 132, 1, (0.55, 0.55, 0.57)),
    "iron": (3, 6.0, 250, 2, (0.85, 0.85, 0.88)),
    "crystal": (4, 9.0, 1024, 3, (0.70, 0.58, 0.92)),
}
_TOOL_KINDS = {
    "pickaxe": ("곡괭이", 2),
    "axe": ("도끼", 4),
    "shovel": ("삽", 1),
}
_TIER_NAMES = {"wooden": "나무", "stone": "돌", "iron": "철", "crystal": "수정"}

for _tier, (_lvl, _speed, _dur, _dmg_bonus, _col) in _TOOL_TIERS.items():
    for _kind, (_kname, _base_dmg) in _TOOL_KINDS.items():
        if _tier == "crystal" and _kind != "pickaxe":
            continue  # 수정 등급은 곡괭이만 (검/갑옷은 별도)
        _reg(Item(
            f"{_tier}_{_kind}", f"{_TIER_NAMES[_tier]} {_kname}",
            category="tool", color=_col, stack_size=1,
            max_durability=_dur, mining_speed=_speed,
            tool_type=_kind, tool_level=_lvl,
            attack_damage=_base_dmg + _dmg_bonus,
            rarity="rare" if _tier == "crystal" else "common",
            description=f"{_kname} - 등급 {_lvl}",
        ))

# ---------------------------------------------------------------------------
# 4) 무기 아이템
# ---------------------------------------------------------------------------
_SWORDS = {
    "wooden_sword": ("나무 검", 4, 60, (0.62, 0.48, 0.28), "common"),
    "stone_sword": ("돌 검", 5, 132, (0.55, 0.55, 0.57), "common"),
    "iron_sword": ("철 검", 7, 250, (0.85, 0.85, 0.88), "uncommon"),
    "crystal_sword": ("수정 검", 9, 1024, (0.70, 0.58, 0.92), "rare"),
}
for _sid, (_nm, _dmg, _dur, _col, _rar) in _SWORDS.items():
    _reg(Item(_sid, _nm, "weapon", _col, stack_size=1, max_durability=_dur,
              attack_damage=_dmg, attack_speed=1.6, rarity=_rar,
              description="근접 무기."))

_reg(Item("bow", "활", "weapon", (0.50, 0.38, 0.20), stack_size=1,
          max_durability=200, attack_damage=1, attack_speed=1.0,
          projectile_type="arrow", range=32,
          description="화살을 소모해 발사한다."))
_reg(Item("arrow", "화살", "weapon", (0.75, 0.72, 0.68), stack_size=64,
          attack_damage=5, description="활의 탄약."))

# ---------------------------------------------------------------------------
# 5) 음식 아이템
# ---------------------------------------------------------------------------
_FOODS = {
    # id: (이름, 허기, 체력회복, 색, 섭취시간)
    "apple": ("사과", 4, 0, (0.85, 0.20, 0.20), 1.2),
    "bread": ("빵", 5, 0, (0.80, 0.62, 0.35), 1.2),
    "raw_meat": ("생고기", 3, 0, (0.80, 0.35, 0.35), 1.4),
    "cooked_meat": ("익힌 고기", 8, 2, (0.60, 0.35, 0.20), 1.4),
    "raw_chicken": ("생 닭고기", 2, 0, (0.90, 0.75, 0.70), 1.4),
    "cooked_chicken": ("익힌 닭고기", 6, 1, (0.75, 0.55, 0.35), 1.4),
    "mushroom_stew": ("버섯 스튜", 6, 3, (0.75, 0.55, 0.45), 1.6),
    "carrot": ("당근", 3, 0, (0.90, 0.50, 0.15), 1.0),
    "potato": ("감자", 1, 0, (0.82, 0.70, 0.45), 1.0),
    "baked_potato": ("구운 감자", 5, 1, (0.70, 0.55, 0.30), 1.2),
}
for _fid, (_nm, _fv, _hv, _col, _et) in _FOODS.items():
    _reg(Item(_fid, _nm, "food", _col, food_value=_fv, heal_value=_hv,
              eat_time=_et, description=f"허기 +{_fv}"))

ITEMS["raw_meat"].smelt_result = ("cooked_meat", 1)
ITEMS["raw_chicken"].smelt_result = ("cooked_chicken", 1)
ITEMS["potato"].smelt_result = ("baked_potato", 1)

# ---------------------------------------------------------------------------
# 6) 장비 아이템
# ---------------------------------------------------------------------------
_ARMORS = {
    "leather_helmet": ("가죽 투구", "helmet", 1, 55, (0.60, 0.40, 0.22), 1.0),
    "leather_chestplate": ("가죽 갑옷", "chestplate", 2, 80, (0.60, 0.40, 0.22), 1.0),
    "iron_helmet": ("철 투구", "helmet", 2, 165, (0.85, 0.85, 0.88), 1.0),
    "iron_chestplate": ("철 갑옷", "chestplate", 4, 240, (0.85, 0.85, 0.88), 0.97),
    "crystal_helmet": ("수정 투구", "helmet", 3, 400, (0.70, 0.58, 0.92), 1.0),
    "crystal_chestplate": ("수정 갑옷", "chestplate", 6, 592, (0.70, 0.58, 0.92), 1.0),
}
for _aid, (_nm, _slot, _av, _dur, _col, _mv) in _ARMORS.items():
    _reg(Item(_aid, _nm, "armor", _col, stack_size=1, max_durability=_dur,
              armor_value=_av, slot_type=_slot, movement_modifier=_mv,
              rarity="rare" if _aid.startswith("crystal") else "common",
              description=f"방어력 +{_av}"))


# ---------------------------------------------------------------------------
# 아이템 스택 헬퍼
# ---------------------------------------------------------------------------
def make_stack(item_id, count=1):
    """새 아이템 스택 dict 를 만든다."""
    item = get_item(item_id)
    if item is None:
        return None
    stack = {"id": item_id, "count": count}
    if item.max_durability > 0:
        stack["durability"] = item.max_durability
    return stack


def stack_max(stack):
    item = get_item(stack["id"]) if stack else None
    return item.stack_size if item else 64


def can_merge(a, b):
    """두 스택이 합쳐질 수 있는지. 내구도 있는 아이템은 합치지 않는다."""
    if not a or not b or a["id"] != b["id"]:
        return False
    if "durability" in a or "durability" in b:
        return False
    return True


def item_display_name(item_id):
    item = get_item(item_id)
    return item.name if item else item_id
