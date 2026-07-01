"""
crafting.py - 레시피 데이터 기반 제작 시스템.

- 기본 2x2 제작 / 작업대 3x3 제작
- shaped 레시피: pattern + keys 로 모양 매칭 (바운딩 박스 정규화)
- shapeless 레시피: 재료 멀티셋 매칭
- 그리드의 각 칸에서 1개씩 소모한다.
"""

import items as I

# ---------------------------------------------------------------------------
# 레시피 데이터
# ---------------------------------------------------------------------------
RECIPES = []


def _shaped(rid, pattern, keys, result, count=1, workbench=False):
    RECIPES.append({
        "id": rid, "type": "shaped", "pattern": pattern, "keys": keys,
        "result_item_id": result, "result_count": count,
        "requires_workbench": workbench,
    })


def _shapeless(rid, ingredients, result, count=1, workbench=False):
    """ingredients: item_id 리스트 (칸 하나당 1개)."""
    RECIPES.append({
        "id": rid, "type": "shapeless", "ingredients": sorted(ingredients),
        "result_item_id": result, "result_count": count,
        "requires_workbench": workbench,
    })


# --- 기초 재료 ---
for _log in ("oak_log", "birch_log", "spruce_log"):
    _shapeless(f"planks_from_{_log}", [_log], "planks", 4)
_shaped("stick", ["P", "P"], {"P": "planks"}, "stick", 4)

# --- 제작 설비 ---
_shaped("workbench", ["PP", "PP"], {"P": "planks"}, "workbench", 1)
_shaped("furnace", ["CCC", "C C", "CCC"], {"C": "cobblestone"},
        "furnace", 1, workbench=True)
_shaped("chest", ["PPP", "P P", "PPP"], {"P": "planks"},
        "chest", 1, workbench=True)
_shaped("torch", ["C", "S"], {"C": "coal", "S": "stick"}, "torch", 4)

# --- 도구 (곡괭이/도끼/삽) ---
_TOOL_MATS = {
    "wooden": "planks", "stone": "cobblestone",
    "iron": "iron_ingot", "crystal": "crystal",
}
for _tier, _mat in _TOOL_MATS.items():
    _shaped(f"{_tier}_pickaxe", ["MMM", " S ", " S "],
            {"M": _mat, "S": "stick"}, f"{_tier}_pickaxe", 1, workbench=True)
    if _tier != "crystal":
        _shaped(f"{_tier}_axe", ["MM", "MS", " S"],
                {"M": _mat, "S": "stick"}, f"{_tier}_axe", 1, workbench=True)
        _shaped(f"{_tier}_shovel", ["M", "S", "S"],
                {"M": _mat, "S": "stick"}, f"{_tier}_shovel", 1,
                workbench=True)
    _shaped(f"{_tier}_sword", ["M", "M", "S"],
            {"M": _mat, "S": "stick"}, f"{_tier}_sword", 1, workbench=True)

# --- 원거리 무기 ---
_shapeless("bow", ["stick", "stick", "stick", "string", "string", "string"],
           "bow", 1, workbench=True)
_shaped("arrow", ["F", "S", "E"],
        {"F": "flint", "S": "stick", "E": "feather"}, "arrow", 4,
        workbench=True)

# --- 음식 ---
_shaped("bread", ["WWW"], {"W": "wheat"}, "bread", 1, workbench=True)
_shapeless("mushroom_stew", ["mushroom", "mushroom", "bread"],
           "mushroom_stew", 1)

# --- 건축 블록 ---
_shaped("glass_from_shards", ["GG", "GG"], {"G": "glass_shard"}, "glass", 1)
_shaped("stone_bricks", ["SS", "SS"], {"S": "stone"}, "stone_bricks", 4)
_shaped("bricks", ["BB", "BB"], {"B": "brick_item"}, "bricks", 1)
_shaped("sandstone", ["SS", "SS"], {"S": "sand"}, "sandstone", 1)
_shaped("glowstone", ["GG", "GG"], {"G": "glow_dust"}, "glowstone", 1)
_shaped("crystal_block", ["CC", "CC"], {"C": "crystal"}, "crystal_block", 1,
        workbench=True)
_shaped("stone_slab", ["CCC"], {"C": "cobblestone"}, "stone_slab", 6,
        workbench=True)
_shaped("wood_stairs", ["P  ", "PP ", "PPP"], {"P": "planks"},
        "wood_stairs", 4, workbench=True)
_shaped("fence", ["PSP", "PSP"], {"P": "planks", "S": "stick"},
        "fence", 3, workbench=True)
_shaped("door", ["PP", "PP", "PP"], {"P": "planks"}, "door", 1,
        workbench=True)
_shapeless("boom_block", ["gunpowder", "gunpowder", "gunpowder",
                          "gunpowder", "sand"], "boom_block", 1,
           workbench=True)

# --- 장비 ---
_ARMOR_MATS = {"leather": "leather", "iron": "iron_ingot",
               "crystal": "crystal"}
for _tier, _mat in _ARMOR_MATS.items():
    _shaped(f"{_tier}_helmet", ["MMM", "M M"], {"M": _mat},
            f"{_tier}_helmet", 1, workbench=True)
    _shaped(f"{_tier}_chestplate", ["M M", "MMM", "MMM"], {"M": _mat},
            f"{_tier}_chestplate", 1, workbench=True)


# ---------------------------------------------------------------------------
# 매칭
# ---------------------------------------------------------------------------
def _grid_to_2d(grid, width):
    """스택 리스트 -> item_id 2D 리스트."""
    return [[grid[r * width + c]["id"] if grid[r * width + c] else None
             for c in range(width)] for r in range(width)]


def _bounding_box(cells):
    rows = [r for r in range(len(cells)) if any(cells[r])]
    cols = [c for c in range(len(cells[0]))
            if any(cells[r][c] for r in range(len(cells)))]
    if not rows or not cols:
        return None
    return [[cells[r][c] for c in range(cols[0], cols[-1] + 1)]
            for r in range(rows[0], rows[-1] + 1)]


def _pattern_to_2d(recipe):
    return [[recipe["keys"].get(ch) for ch in row]
            for row in recipe["pattern"]]


def match_recipe(grid, width=3, workbench=None):
    """
    grid  : 스택 리스트 (width*width)
    width : 2 또는 3
    반환  : 일치하는 레시피 dict 또는 None
    """
    if workbench is None:
        workbench = width >= 3
    cells = _grid_to_2d(grid, width)
    box = _bounding_box(cells)
    if box is None:
        return None
    item_list = sorted(s["id"] for s in grid if s)

    for recipe in RECIPES:
        if recipe["requires_workbench"] and not workbench:
            continue
        if recipe["type"] == "shaped":
            pat = _pattern_to_2d(recipe)
            if len(pat) == len(box) and len(pat[0]) == len(box[0]):
                if all(pat[r][c] == box[r][c]
                       for r in range(len(pat))
                       for c in range(len(pat[0]))):
                    return recipe
        else:
            if recipe["ingredients"] == item_list:
                return recipe
    return None


def consume_ingredients(grid, recipe=None):
    """그리드의 각 점유 칸에서 1개씩 소모한다."""
    for i, stack in enumerate(grid):
        if stack:
            stack["count"] -= 1
            if stack["count"] <= 0:
                grid[i] = None


def craft_result_stack(recipe):
    """레시피 결과 스택 생성."""
    return I.make_stack(recipe["result_item_id"], recipe["result_count"])


def craft_item(inventory, grid, width=3, workbench=None):
    """
    그리드에서 매칭되는 레시피를 제작해 인벤토리에 넣는다.
    반환: 제작된 스택 또는 None
    """
    recipe = match_recipe(grid, width, workbench)
    if recipe is None:
        return None
    result = craft_result_stack(recipe)
    if result is None:
        return None
    consume_ingredients(grid, recipe)
    give_craft_result(inventory, result["id"], result["count"])
    return result


def give_craft_result(inventory, item_id, count):
    """결과 아이템 지급 (가득 차면 남는 수량 반환)."""
    item = I.get_item(item_id)
    if item and item.max_durability > 0:
        # 도구류는 개별 스택으로
        left = 0
        for _ in range(count):
            left += inventory.add_stack(I.make_stack(item_id, 1))
        return left
    return inventory.add_item(item_id, count)
