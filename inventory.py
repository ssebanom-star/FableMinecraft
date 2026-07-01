"""
inventory.py - 인벤토리 (핫바 9 + 메인 27 + 장비 + 제작 그리드 + 커서).

아이템 스택은 items.make_stack() 이 만드는 dict 로 표현된다.
UI 는 click_slot() 을 통해 커서 스택과 슬롯 간 이동/합치기/분리를 수행한다.
"""

import items as I

HOTBAR_SIZE = 9
MAIN_SIZE = 27
TOTAL_SIZE = HOTBAR_SIZE + MAIN_SIZE
ARMOR_SLOTS = ("helmet", "chestplate")


class Inventory:
    def __init__(self):
        self.slots = [None] * TOTAL_SIZE          # 0~8 핫바, 9~35 메인
        self.armor = {slot: None for slot in ARMOR_SLOTS}
        self.craft_grid = [None] * 9              # 2x2 는 앞 4칸만 사용
        self.cursor = None                        # 마우스 커서 스택
        self.selected_index = 0

    # ------------------------------------------------------------------
    # 추가/제거
    # ------------------------------------------------------------------
    def add_item(self, item_id, count=1):
        """아이템을 넣고 남은 개수를 반환한다 (0 = 전부 수납)."""
        item = I.get_item(item_id)
        if item is None or count <= 0:
            return 0
        remaining = count
        # 1) 기존 스택에 합치기
        if item.max_durability == 0:
            for slot in self.slots:
                if slot and slot["id"] == item_id and I.can_merge(slot, slot):
                    space = item.stack_size - slot["count"]
                    if space > 0:
                        take = min(space, remaining)
                        slot["count"] += take
                        remaining -= take
                        if remaining <= 0:
                            return 0
        # 2) 빈 칸에 새 스택
        for i in range(TOTAL_SIZE):
            if self.slots[i] is None:
                take = min(item.stack_size, remaining)
                stack = I.make_stack(item_id, take)
                self.slots[i] = stack
                remaining -= take
                if remaining <= 0:
                    return 0
        return remaining

    def add_stack(self, stack):
        """스택 자체를 넣는다 (내구도 유지). 남은 개수 반환."""
        if not stack:
            return 0
        if "durability" in stack:
            for i in range(TOTAL_SIZE):
                if self.slots[i] is None:
                    self.slots[i] = dict(stack)
                    return 0
            return stack["count"]
        return self.add_item(stack["id"], stack["count"])

    def remove_item(self, item_id, count=1):
        """아이템을 제거. 부족하면 False (아무것도 제거 안 함)."""
        if self.count_item(item_id) < count:
            return False
        remaining = count
        for i in range(TOTAL_SIZE):
            slot = self.slots[i]
            if slot and slot["id"] == item_id:
                take = min(slot["count"], remaining)
                slot["count"] -= take
                remaining -= take
                if slot["count"] <= 0:
                    self.slots[i] = None
                if remaining <= 0:
                    return True
        return remaining <= 0

    def count_item(self, item_id):
        return sum(s["count"] for s in self.slots
                   if s and s["id"] == item_id)

    def has_items(self, requirements):
        """requirements: {item_id: count} 전부 보유 여부."""
        return all(self.count_item(iid) >= cnt
                   for iid, cnt in requirements.items())

    def consume_items(self, requirements):
        if not self.has_items(requirements):
            return False
        for iid, cnt in requirements.items():
            self.remove_item(iid, cnt)
        return True

    def is_full(self):
        return all(s is not None for s in self.slots)

    # ------------------------------------------------------------------
    # 슬롯 조작 (UI 용)
    # ------------------------------------------------------------------
    def move_stack(self, from_slot, to_slot):
        """슬롯 인덱스 간 이동/합치기."""
        a, b = self.slots[from_slot], self.slots[to_slot]
        if a is None:
            return
        if b is None:
            self.slots[to_slot] = a
            self.slots[from_slot] = None
        elif I.can_merge(a, b):
            space = I.stack_max(b) - b["count"]
            take = min(space, a["count"])
            b["count"] += take
            a["count"] -= take
            if a["count"] <= 0:
                self.slots[from_slot] = None
        else:
            self.slots[from_slot], self.slots[to_slot] = b, a

    def split_stack(self, slot_index):
        """슬롯의 절반을 커서로 분리."""
        slot = self.slots[slot_index]
        if slot is None or self.cursor is not None:
            return
        half = (slot["count"] + 1) // 2
        self.cursor = I.make_stack(slot["id"], half)
        if "durability" in slot:
            self.cursor["durability"] = slot["durability"]
        slot["count"] -= half
        if slot["count"] <= 0:
            self.slots[slot_index] = None

    def click_slot(self, container, index, right_click=False,
                   armor_slot=None):
        """
        커서 스택과 컨테이너 슬롯 간 상호작용.
        container: 슬롯 dict 리스트 (self.slots, craft_grid, 상자 슬롯 등)
        - 좌클릭: 전체 집기/놓기/합치기/교체
        - 우클릭: 하나만 놓기 / 절반 집기
        """
        slot = container[index]
        cur = self.cursor

        # 장비 슬롯 제약: 맞는 부위만 장착
        if armor_slot and cur:
            item = I.get_item(cur["id"])
            if item is None or item.slot_type != armor_slot:
                return

        if cur is None:
            if slot is None:
                return
            if right_click:
                half = (slot["count"] + 1) // 2
                self.cursor = dict(slot)
                self.cursor["count"] = half
                slot["count"] -= half
                if slot["count"] <= 0:
                    container[index] = None
            else:
                self.cursor = slot
                container[index] = None
            return

        # 커서에 아이템이 있는 경우
        if slot is None:
            if right_click:
                one = dict(cur)
                one["count"] = 1
                container[index] = one
                cur["count"] -= 1
                if cur["count"] <= 0:
                    self.cursor = None
            else:
                container[index] = cur
                self.cursor = None
            return

        if I.can_merge(cur, slot):
            space = I.stack_max(slot) - slot["count"]
            amount = 1 if right_click else cur["count"]
            take = min(space, amount)
            slot["count"] += take
            cur["count"] -= take
            if cur["count"] <= 0:
                self.cursor = None
        else:
            container[index], self.cursor = cur, slot

    # ------------------------------------------------------------------
    # 핫바
    # ------------------------------------------------------------------
    def get_selected_item(self):
        return self.slots[self.selected_index]

    def get_selected_def(self):
        stack = self.get_selected_item()
        return I.get_item(stack["id"]) if stack else None

    def consume_selected(self, count=1):
        """선택 슬롯에서 count 개 소모."""
        slot = self.slots[self.selected_index]
        if slot is None:
            return False
        slot["count"] -= count
        if slot["count"] <= 0:
            self.slots[self.selected_index] = None
        return True

    def drop_selected_item(self):
        """선택 아이템 1개를 꺼내 반환 (드롭 생성용)."""
        slot = self.slots[self.selected_index]
        if slot is None:
            return None
        dropped = dict(slot)
        dropped["count"] = 1
        slot["count"] -= 1
        if slot["count"] <= 0:
            self.slots[self.selected_index] = None
        return dropped

    def damage_selected(self, amount=1):
        """선택 도구 내구도 감소. 파괴되면 True."""
        slot = self.slots[self.selected_index]
        if slot is None or "durability" not in slot:
            return False
        slot["durability"] -= amount
        if slot["durability"] <= 0:
            self.slots[self.selected_index] = None
            return True
        return False

    # ------------------------------------------------------------------
    # 장비
    # ------------------------------------------------------------------
    def total_armor(self):
        total = 0
        for stack in self.armor.values():
            if stack:
                item = I.get_item(stack["id"])
                if item:
                    total += item.armor_value
        return total

    def damage_armor(self, amount=1):
        """피격 시 장비 내구도 감소."""
        for key, stack in list(self.armor.items()):
            if stack and "durability" in stack:
                stack["durability"] -= amount
                if stack["durability"] <= 0:
                    self.armor[key] = None

    # ------------------------------------------------------------------
    # 저장/불러오기
    # ------------------------------------------------------------------
    def serialize(self):
        return {
            "slots": self.slots,
            "armor": self.armor,
            "selected_index": self.selected_index,
        }

    def deserialize(self, data):
        slots = data.get("slots", [])
        self.slots = [None] * TOTAL_SIZE
        for i, s in enumerate(slots[:TOTAL_SIZE]):
            self.slots[i] = s
        armor = data.get("armor", {})
        for key in ARMOR_SLOTS:
            self.armor[key] = armor.get(key)
        self.selected_index = int(data.get("selected_index", 0))

    def return_craft_grid(self):
        """제작 그리드에 남은 아이템을 인벤토리로 되돌린다."""
        for i, stack in enumerate(self.craft_grid):
            if stack:
                left = self.add_stack(stack)
                self.craft_grid[i] = None if left == 0 else stack
