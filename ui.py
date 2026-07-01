"""
ui.py - HUD / 인벤토리 UI / 메뉴.

- HUD: 조준점, 핫바, 체력/허기/스태미나/산소 바, 시간/바이옴/모드, 디버그(F3)
- 화면: 인벤토리(2x2 제작), 작업대(3x3), 화로, 상자, 일시정지, 사망, 메인 메뉴
- 슬롯 클릭 규칙은 inventory.Inventory.click_slot() 을 그대로 사용한다.
"""

import os

from ursina import (Entity, Button, Text, Color, camera, mouse, window,
                    destroy, application, InputField)

import blocks as B
import config
import crafting
import furnace as F
import items as I
import save_system
from utils import set_mouse_locked

SLOT = 0.05
PANEL_BG = Color(0.08, 0.08, 0.10, 0.92)
SLOT_BG = Color(0.22, 0.22, 0.26, 1)
SLOT_HOVER = Color(0.35, 0.35, 0.40, 1)

RARITY_COLORS = {
    "common": Color(1, 1, 1, 1),
    "uncommon": Color(0.5, 0.9, 0.5, 1),
    "rare": Color(0.7, 0.6, 1.0, 1),
}


def _icon_color(item_id):
    item = I.get_item(item_id)
    if item is None:
        return Color(1, 0, 1, 1)
    c = item.color
    return Color(c[0], c[1], c[2], 1)


# ---------------------------------------------------------------------------
# 슬롯 위젯
# ---------------------------------------------------------------------------
class SlotButton(Button):
    """
    container[index] 의 스택을 표시/조작하는 슬롯.
    container 는 리스트 또는 DictSlot(화로 슬롯용) 이다.
    """

    def __init__(self, ui, container, index, armor_slot=None,
                 take_only=False, **kwargs):
        super().__init__(model='quad', color=SLOT_BG,
                         highlight_color=SLOT_HOVER,
                         scale=(SLOT, SLOT), **kwargs)
        self.ui = ui
        self.container = container
        self.index = index
        self.armor_slot = armor_slot
        self.take_only = take_only
        self.icon_ent = Entity(parent=self, model='quad', scale=0.62,
                           z=-0.05, enabled=False)
        self.refresh()

    def stack(self):
        return self.container[self.index]

    def refresh(self):
        stack = self.stack()
        if stack:
            self.icon_ent.enabled = True
            self.icon_ent.color = _icon_color(stack["id"])
            self.text = str(stack["count"]) if stack["count"] > 1 else ''
        else:
            self.icon_ent.enabled = False
            self.text = ''

    def _click(self, right):
        inv = self.ui.game.player.inventory
        if self.take_only:
            # 결과 전용 슬롯 (화로 결과): 커서로 꺼내기만 가능
            stack = self.stack()
            if stack is None:
                return
            if inv.cursor is None:
                inv.cursor = stack
                self.container[self.index] = None
            elif I.can_merge(inv.cursor, stack):
                space = I.stack_max(inv.cursor) - inv.cursor["count"]
                take = min(space, stack["count"])
                inv.cursor["count"] += take
                stack["count"] -= take
                if stack["count"] <= 0:
                    self.container[self.index] = None
        else:
            inv.click_slot(self.container, self.index, right_click=right,
                           armor_slot=self.armor_slot)
        self.ui.refresh_screen()

    def on_click(self):
        self._click(False)

    def input(self, key):
        super().input(key)
        if key == 'right mouse down' and self.hovered:
            self._click(True)

    def update(self):
        if self.hovered:
            stack = self.stack()
            if stack:
                item = I.get_item(stack["id"])
                if item:
                    extra = ""
                    if "durability" in stack:
                        extra = f"  내구도 {stack['durability']}" \
                                f"/{item.max_durability}"
                    self.ui.set_hover_text(
                        f"{item.name}{extra}  |  {item.description}")


class DictSlot:
    """dict 의 특정 키를 1칸 컨테이너처럼 다루는 어댑터 (화로 슬롯)."""

    def __init__(self, d, key):
        self.d = d
        self.key = key

    def __getitem__(self, i):
        return self.d.get(self.key)

    def __setitem__(self, i, value):
        self.d[self.key] = value


class CraftResultSlot(Button):
    """제작 결과 슬롯: 매칭된 레시피 결과를 표시, 클릭 시 제작."""

    def __init__(self, ui, grid_indices, width, **kwargs):
        super().__init__(model='quad', color=SLOT_BG,
                         highlight_color=SLOT_HOVER,
                         scale=(SLOT * 1.2, SLOT * 1.2), **kwargs)
        self.ui = ui
        self.grid_indices = grid_indices
        self.grid_width = width
        self.icon_ent = Entity(parent=self, model='quad', scale=0.62,
                           z=-0.05, enabled=False)
        self.recipe = None
        self.refresh()

    def _grid(self):
        g = self.ui.game.player.inventory.craft_grid
        return [g[i] for i in self.grid_indices]

    def refresh(self):
        self.recipe = crafting.match_recipe(
            self._grid(), self.grid_width,
            workbench=self.grid_width >= 3)
        if self.recipe:
            self.icon_ent.enabled = True
            self.icon_ent.color = _icon_color(self.recipe["result_item_id"])
            cnt = self.recipe["result_count"]
            self.text = str(cnt) if cnt > 1 else ''
        else:
            self.icon_ent.enabled = False
            self.text = ''

    def on_click(self):
        if self.recipe is None:
            return
        inv = self.ui.game.player.inventory
        result = crafting.craft_result_stack(self.recipe)
        if result is None:
            return
        # 커서로 받기 (커서가 차 있으면 합칠 수 있어야 함)
        if inv.cursor is None:
            inv.cursor = result
        elif I.can_merge(inv.cursor, result) and \
                inv.cursor["count"] + result["count"] <= \
                I.stack_max(inv.cursor):
            inv.cursor["count"] += result["count"]
        else:
            return
        # 재료 소모 (활성 그리드 칸에서 1개씩)
        grid = inv.craft_grid
        for i in self.grid_indices:
            stack = grid[i]
            if stack:
                stack["count"] -= 1
                if stack["count"] <= 0:
                    grid[i] = None
        self.ui.refresh_screen()

    def update(self):
        if self.hovered and self.recipe:
            self.ui.set_hover_text(
                I.item_display_name(self.recipe["result_item_id"]))


# ---------------------------------------------------------------------------
# 화면 (인벤토리 계열)
# ---------------------------------------------------------------------------
class BaseScreen(Entity):
    """플레이어 인벤토리 36칸 + 커서를 포함하는 화면의 공통부."""

    def __init__(self, ui, title):
        super().__init__(parent=camera.ui)
        self.ui = ui
        self.slots = []
        self.bg = Entity(parent=self, model='quad', color=PANEL_BG,
                         scale=(0.85, 0.85), z=0.1)
        self.title = Text(parent=self, text=title, position=(-0.4, 0.4),
                          scale=1.1)
        self._build_player_slots()

    def _build_player_slots(self):
        inv = self.ui.game.player.inventory
        # 메인 인벤토리 27칸 (3행)
        for row in range(3):
            for col in range(9):
                idx = 9 + row * 9 + col
                self.slots.append(SlotButton(
                    self.ui, inv.slots, idx, parent=self,
                    position=(-0.22 + col * (SLOT + 0.006),
                              -0.16 - row * (SLOT + 0.006))))
        # 핫바 9칸
        for col in range(9):
            self.slots.append(SlotButton(
                self.ui, inv.slots, col, parent=self,
                position=(-0.22 + col * (SLOT + 0.006), -0.36)))

    def refresh(self):
        for slot in self.slots:
            slot.refresh()

    def on_close(self):
        pass


class InventoryScreen(BaseScreen):
    """E 키 인벤토리: 장비 슬롯 + 2x2 제작."""

    GRID_IDX = (0, 1, 3, 4)   # craft_grid(3x3) 중 2x2 로 쓰는 칸

    def __init__(self, ui):
        super().__init__(ui, "인벤토리")
        inv = ui.game.player.inventory

        # 장비 슬롯
        Text(parent=self, text="장비", position=(-0.40, 0.30), scale=0.8)
        armor_list = _ArmorContainer(inv)
        for i, slot_name in enumerate(("helmet", "chestplate")):
            self.slots.append(SlotButton(
                self.ui, armor_list, i, armor_slot=slot_name, parent=self,
                position=(-0.38, 0.22 - i * (SLOT + 0.01))))

        # 2x2 제작
        Text(parent=self, text="제작 (2x2)", position=(-0.12, 0.30),
             scale=0.8)
        for n, gi in enumerate(self.GRID_IDX):
            r, c = divmod(n, 2)
            self.slots.append(SlotButton(
                self.ui, inv.craft_grid, gi, parent=self,
                position=(-0.10 + c * (SLOT + 0.006),
                          0.22 - r * (SLOT + 0.006))))
        self.result = CraftResultSlot(
            self.ui, self.GRID_IDX, 2, parent=self, position=(0.06, 0.19))
        Text(parent=self, text="→", position=(0.005, 0.19), scale=1)

    def refresh(self):
        super().refresh()
        self.result.refresh()

    def on_close(self):
        self.ui.game.player.inventory.return_craft_grid()


class _ArmorContainer:
    """armor dict 를 리스트 인터페이스로 감싼다 (helmet=0, chestplate=1)."""

    KEYS = ("helmet", "chestplate")

    def __init__(self, inv):
        self.inv = inv

    def __getitem__(self, i):
        return self.inv.armor[self.KEYS[i]]

    def __setitem__(self, i, value):
        self.inv.armor[self.KEYS[i]] = value


class WorkbenchScreen(BaseScreen):
    """작업대: 3x3 제작."""

    GRID_IDX = tuple(range(9))

    def __init__(self, ui):
        super().__init__(ui, "작업대")
        inv = ui.game.player.inventory
        for n in range(9):
            r, c = divmod(n, 3)
            self.slots.append(SlotButton(
                self.ui, inv.craft_grid, n, parent=self,
                position=(-0.16 + c * (SLOT + 0.006),
                          0.26 - r * (SLOT + 0.006))))
        self.result = CraftResultSlot(
            self.ui, self.GRID_IDX, 3, parent=self, position=(0.08, 0.20))
        Text(parent=self, text="→", position=(0.015, 0.20), scale=1)

    def refresh(self):
        super().refresh()
        self.result.refresh()

    def on_close(self):
        self.ui.game.player.inventory.return_craft_grid()


class FurnaceScreen(BaseScreen):
    def __init__(self, ui, state):
        super().__init__(ui, "화로")
        self.state = state
        self.slots.append(SlotButton(
            self.ui, DictSlot(state, "input"), 0, parent=self,
            position=(-0.12, 0.28)))
        self.slots.append(SlotButton(
            self.ui, DictSlot(state, "fuel"), 0, parent=self,
            position=(-0.12, 0.12)))
        self.slots.append(SlotButton(
            self.ui, DictSlot(state, "output"), 0, take_only=True,
            parent=self, position=(0.06, 0.20)))
        Text(parent=self, text="재료", position=(-0.19, 0.28), scale=0.7)
        Text(parent=self, text="연료", position=(-0.19, 0.12), scale=0.7)
        Text(parent=self, text="결과", position=(0.10, 0.20), scale=0.7)

        # 진행/연소 바
        self.progress_bg = Entity(parent=self, model='quad',
                                  color=Color(0.15, 0.15, 0.15, 1),
                                  scale=(0.12, 0.015), position=(-0.02, 0.22))
        self.progress_fg = Entity(parent=self, model='quad',
                                  color=Color(0.9, 0.75, 0.2, 1),
                                  origin=(-0.5, 0), scale=(0.0, 0.012),
                                  position=(-0.08, 0.22), z=-0.01)
        self.burn_fg = Entity(parent=self, model='quad',
                              color=Color(0.95, 0.4, 0.1, 1),
                              origin=(-0.5, 0), scale=(0.0, 0.012),
                              position=(-0.145, 0.20), z=-0.01)

    def update(self):
        # 제련 진행 상황 실시간 반영
        self.progress_fg.scale_x = 0.12 * F.progress_ratio(self.state)
        self.burn_fg.scale_x = 0.07 * F.burn_ratio(self.state)
        for slot in self.slots[-3:]:
            slot.refresh()


class ChestScreen(BaseScreen):
    def __init__(self, ui, state):
        super().__init__(ui, "상자")
        self.state = state
        for n in range(27):
            r, c = divmod(n, 9)
            self.slots.append(SlotButton(
                self.ui, state["slots"], n, parent=self,
                position=(-0.22 + c * (SLOT + 0.006),
                          0.30 - r * (SLOT + 0.006))))


# ---------------------------------------------------------------------------
# HUD
# ---------------------------------------------------------------------------
class HUD(Entity):
    def __init__(self, game):
        super().__init__(parent=camera.ui)
        self.game = game

        self.crosshair = Text(parent=self, text='+', origin=(0, 0),
                              scale=1.4, color=Color(1, 1, 1, 0.85))
        self.break_bar = Entity(parent=self, model='quad',
                                color=Color(1, 1, 1, 0.9),
                                origin=(-0.5, 0), position=(-0.03, -0.05),
                                scale=(0.0, 0.008))

        # 핫바
        self.hotbar_bg = []
        self.hotbar_icons = []
        self.hotbar_counts = []
        for i in range(9):
            x = -0.22 + i * (SLOT + 0.006)
            bg = Entity(parent=self, model='quad', color=SLOT_BG,
                        scale=(SLOT, SLOT), position=(x, -0.45))
            icon = Entity(parent=self, model='quad', scale=SLOT * 0.62,
                          position=(x, -0.45), z=-0.05, enabled=False)
            cnt = Text(parent=self, text='', position=(x + 0.008, -0.435),
                       scale=0.6, z=-0.1)
            self.hotbar_bg.append(bg)
            self.hotbar_icons.append(icon)
            self.hotbar_counts.append(cnt)
        self.select_frame = Entity(parent=self, model='quad',
                                   color=Color(1, 1, 1, 0.25),
                                   scale=(SLOT * 1.18, SLOT * 1.18),
                                   position=(-0.22, -0.45), z=0.05)
        self.item_name = Text(parent=self, text='', origin=(0, 0),
                              position=(0, -0.39), scale=0.8)

        # 상태 바 (체력/허기/스태미나/산소)
        self.bars = {}
        bar_defs = (("health", "체력", Color(0.85, 0.2, 0.2, 1), 0),
                    ("hunger", "허기", Color(0.85, 0.55, 0.15, 1), 1),
                    ("stamina", "스태미나", Color(0.3, 0.8, 0.3, 1), 2),
                    ("oxygen", "산소", Color(0.25, 0.55, 0.95, 1), 3))
        for key, label, col, row in bar_defs:
            y = -0.30 - row * 0.028
            Text(parent=self, text=label, position=(-0.62, y + 0.008),
                 scale=0.6)
            Entity(parent=self, model='quad', color=Color(0, 0, 0, 0.5),
                   origin=(-0.5, 0), scale=(0.14, 0.018),
                   position=(-0.56, y))
            fg = Entity(parent=self, model='quad', color=col,
                        origin=(-0.5, 0), scale=(0.14, 0.014),
                        position=(-0.56, y), z=-0.01)
            self.bars[key] = fg

        # 정보 텍스트
        self.info = Text(parent=self, text='', position=(-0.62, 0.47),
                         scale=0.7, line_height=1.1)
        self.target_label = Text(parent=self, text='', origin=(0, 0),
                                 position=(0, 0.06), scale=0.7,
                                 color=Color(1, 1, 1, 0.8))
        self.debug = Text(parent=self, text='', position=(0.18, 0.47),
                          scale=0.6, line_height=1.1, enabled=False)
        self.fps_timer = 0.0
        self.fps_value = 0

    # ------------------------------------------------------------------
    def refresh_hotbar(self):
        inv = self.game.player.inventory
        for i in range(9):
            stack = inv.slots[i]
            if stack:
                self.hotbar_icons[i].enabled = True
                self.hotbar_icons[i].color = _icon_color(stack["id"])
                self.hotbar_counts[i].text = \
                    str(stack["count"]) if stack["count"] > 1 else ''
            else:
                self.hotbar_icons[i].enabled = False
                self.hotbar_counts[i].text = ''
        x = -0.22 + inv.selected_index * (SLOT + 0.006)
        self.select_frame.x = x
        stack = inv.get_selected_item()
        self.item_name.text = I.item_display_name(stack["id"]) \
            if stack else ''

    def tick(self, dt):
        game = self.game
        p = game.player
        self.refresh_hotbar()

        self.bars["health"].scale_x = 0.14 * p.health / p.max_health
        self.bars["hunger"].scale_x = 0.14 * p.hunger / p.max_hunger
        self.bars["stamina"].scale_x = 0.14 * p.stamina / p.max_stamina
        self.bars["oxygen"].scale_x = 0.14 * p.oxygen / p.max_oxygen

        # FPS (0.5초 간격 계산)
        self.fps_timer += dt
        if self.fps_timer > 0.5:
            self.fps_value = int(1.0 / max(dt, 1e-5))
            self.fps_timer = 0.0

        px, py, pz = p.position
        self.info.text = (
            f"{game.time_system.clock_string()}   "
            f"{game.weather.display_for_biome(game.world.biome_at(px, pz))}\n"
            f"바이옴: {game.current_biome()}   모드: "
            f"{'크리에이티브' if p.mode == 'creative' else '서바이벌'}\n"
            f"XYZ: {px:.0f} / {py:.0f} / {pz:.0f}   FPS: {self.fps_value}")

        # 바라보는 블록
        if p.target_block:
            bid = game.world.get_block(*p.target_block)
            self.target_label.text = B.BLOCKS[bid].display_name \
                if bid != B.AIR else ''
        else:
            self.target_label.text = ''

        # 파괴 진행 바
        self.break_bar.scale_x = 0.06 * min(1.0, p.break_progress)

        # 디버그 (F3)
        self.debug.enabled = game.debug_visible
        if game.debug_visible:
            cx, cz = game.world.to_chunk_coords(px, pz)
            mem = ""
            try:
                import resource
                mem = f"메모리: " \
                    f"{resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024} MB"
            except ImportError:
                pass
            stack = p.inventory.get_selected_item()
            self.debug.text = (
                f"FPS: {self.fps_value}\n"
                f"좌표: {px:.2f} {py:.2f} {pz:.2f}\n"
                f"청크: {cx}, {cz} (로드 {len(game.world.chunks)})\n"
                f"바이옴: {game.current_biome()}\n"
                f"시간: {game.time_system.time_of_day:.3f} "
                f"({game.time_system.clock_string()})\n"
                f"날씨: {game.weather.kind}\n"
                f"선택: {stack['id'] if stack else '-'}\n"
                f"몹: {len(game.mobs.mobs)}  드롭: {len(game.drops.drops)}\n"
                f"시드: {game.world.seed}\n{mem}")


# ---------------------------------------------------------------------------
# 게임 UI 총괄
# ---------------------------------------------------------------------------
class GameUI(Entity):
    def __init__(self, game, on_exit_to_menu):
        super().__init__(parent=camera.ui)
        self.game = game
        self.on_exit_to_menu = on_exit_to_menu
        self.hud = HUD(game)
        self.screen = None
        self.pause_panel = None
        self.death_panel = None

        # 커서 스택 표시
        self.cursor_icon = Entity(parent=camera.ui, model='quad',
                                  scale=SLOT * 0.62, z=-0.5, enabled=False)
        self.cursor_text = Text(parent=camera.ui, text='', z=-0.6, scale=0.7)
        self.hover_text = Text(parent=camera.ui, text='', origin=(0, 0),
                               position=(0, -0.47), scale=0.75, z=-0.6)
        self._hover_frame = False

    # ------------------------------------------------------------------
    def screen_open(self):
        return self.screen is not None

    def _open(self, screen):
        self.close_screen()
        self.screen = screen
        set_mouse_locked(False)

    def open_inventory(self):
        self._open(InventoryScreen(self))

    def open_workbench(self):
        self._open(WorkbenchScreen(self))

    def open_furnace(self, state):
        self._open(FurnaceScreen(self, state))

    def open_chest(self, state):
        self._open(ChestScreen(self, state))

    def close_screen(self):
        if self.screen:
            self.screen.on_close()
            # 커서에 남은 아이템 반환
            inv = self.game.player.inventory
            if inv.cursor:
                left = inv.add_stack(inv.cursor)
                if left == 0:
                    inv.cursor = None
                else:
                    inv.cursor["count"] = left
            destroy(self.screen)
            self.screen = None
        if not self.game.paused and not self.game.player.dead:
            set_mouse_locked(True)

    def refresh_screen(self):
        if self.screen:
            self.screen.refresh()

    def set_hover_text(self, text):
        self.hover_text.text = text
        self._hover_frame = True

    # ------------------------------------------------------------------
    # 일시정지
    # ------------------------------------------------------------------
    def toggle_pause(self):
        if self.pause_panel:
            self.resume()
        else:
            self.game.paused = True
            set_mouse_locked(False)
            self.pause_panel = self._build_pause_panel()

    def resume(self):
        if self.pause_panel:
            destroy(self.pause_panel)
            self.pause_panel = None
        self.game.paused = False
        if not self.screen:
            set_mouse_locked(True)

    def _build_pause_panel(self):
        panel = Entity(parent=camera.ui)
        Entity(parent=panel, model='quad', color=PANEL_BG,
               scale=(0.5, 0.72), z=0.1)
        Text(parent=panel, text="일시정지", origin=(0, 0),
             position=(0, 0.28), scale=1.4)

        def _btn(text, y, action):
            return Button(parent=panel, text=text, scale=(0.34, 0.055),
                          position=(0, y), color=SLOT_BG,
                          highlight_color=SLOT_HOVER, on_click=action)

        _btn("계속하기", 0.18, self.resume)
        _btn("저장", 0.10, self.game.save)

        # 간단 설정 (렌더 거리 / 감도 / FOV)
        y0 = 0.01
        self._setting_labels = {}

        def _setting(row, key, label, step, lo, hi, apply_fn=None):
            y = y0 - row * 0.07
            lbl = Text(parent=panel, text='', origin=(0, 0),
                       position=(0, y), scale=0.8)
            self._setting_labels[key] = (lbl, label)

            def _change(delta):
                val = config.get(key) + delta
                val = max(lo, min(hi, val))
                config.set_value(key, val)
                config.save_settings()
                if apply_fn:
                    apply_fn(val)
                _update_label()

            def _update_label():
                lbl.text = f"{label}: {config.get(key)}"

            Button(parent=panel, text='-', scale=(0.05, 0.05),
                   position=(-0.17, y), color=SLOT_BG,
                   on_click=lambda: _change(-step))
            Button(parent=panel, text='+', scale=(0.05, 0.05),
                   position=(0.17, y), color=SLOT_BG,
                   on_click=lambda: _change(step))
            _update_label()

        def _apply_rd(val):
            self.game.world.render_distance = int(val)

        def _apply_fov(val):
            camera.fov = val

        _setting(0, "render_distance", "렌더 거리", 1, 1, 8, _apply_rd)
        _setting(1, "mouse_sensitivity", "마우스 감도", 5, 5, 120)
        _setting(2, "fov", "FOV", 5, 50, 120, _apply_fov)

        def _exit_to_menu():
            self.resume()
            self.on_exit_to_menu()

        _btn("저장하고 메뉴로", -0.24, _exit_to_menu)
        _btn("저장하고 종료", -0.31, self._save_and_quit)
        return panel

    def _save_and_quit(self):
        self.game.save()
        config.save_settings()
        application.quit()

    # ------------------------------------------------------------------
    # 사망 화면
    # ------------------------------------------------------------------
    def show_death_screen(self):
        set_mouse_locked(False)
        if self.death_panel:
            return
        panel = Entity(parent=camera.ui)
        Entity(parent=panel, model='quad', color=Color(0.35, 0.02, 0.02, 0.85),
               scale=(2, 1.2), z=0.1)
        Text(parent=panel, text="사망했습니다", origin=(0, 0),
             position=(0, 0.1), scale=2, color=Color(1, 0.85, 0.85, 1))
        Button(parent=panel, text="리스폰", scale=(0.25, 0.06),
               position=(0, -0.05), color=SLOT_BG,
               highlight_color=SLOT_HOVER,
               on_click=self.game.respawn_player)
        Button(parent=panel, text="메뉴로", scale=(0.25, 0.06),
               position=(0, -0.14), color=SLOT_BG,
               highlight_color=SLOT_HOVER,
               on_click=lambda: (self.hide_death_screen(),
                                 self.on_exit_to_menu()))
        self.death_panel = panel

    def hide_death_screen(self):
        if self.death_panel:
            destroy(self.death_panel)
            self.death_panel = None

    # ------------------------------------------------------------------
    def update_hud(self, dt):
        self.hud.tick(dt)

        # 커서 스택 아이콘
        inv = self.game.player.inventory
        if inv.cursor:
            self.cursor_icon.enabled = True
            self.cursor_icon.color = _icon_color(inv.cursor["id"])
            self.cursor_icon.position = (mouse.x, mouse.y, -0.5)
            self.cursor_text.text = str(inv.cursor["count"]) \
                if inv.cursor["count"] > 1 else ''
            self.cursor_text.position = (mouse.x + 0.01, mouse.y - 0.01, -0.6)
        else:
            self.cursor_icon.enabled = False
            self.cursor_text.text = ''

        # 호버 텍스트는 매 프레임 슬롯이 갱신하지 않으면 지운다
        if not self._hover_frame:
            self.hover_text.text = ''
        self._hover_frame = False

    def cleanup(self):
        self.close_screen()
        self.hide_death_screen()
        if self.pause_panel:
            destroy(self.pause_panel)
        destroy(self.hud)
        destroy(self.cursor_icon)
        destroy(self.cursor_text)
        destroy(self.hover_text)
        destroy(self)


# ---------------------------------------------------------------------------
# 메인 메뉴
# ---------------------------------------------------------------------------
class MainMenu(Entity):
    """시작 메뉴: 새 월드 / 불러오기 / 설정 / 종료."""

    def __init__(self, on_new_world, on_load_world):
        super().__init__(parent=camera.ui)
        self.on_new_world = on_new_world
        self.on_load_world = on_load_world
        self.sub_panel = None

        Entity(parent=self, model='quad', color=Color(0.07, 0.09, 0.13, 1),
               scale=(3, 2), z=0.5)
        Text(parent=self, text="BLOCKWORLD", origin=(0, 0),
             position=(0, 0.32), scale=3, color=Color(0.6, 0.85, 0.5, 1))
        Text(parent=self, text="파이썬 복셀 샌드박스 생존 게임",
             origin=(0, 0), position=(0, 0.24), scale=0.9)

        def _btn(text, y, action):
            return Button(parent=self, text=text, scale=(0.3, 0.06),
                          position=(0, y), color=SLOT_BG,
                          highlight_color=SLOT_HOVER, on_click=action)

        _btn("새 월드", 0.10, self.show_new_world)
        _btn("월드 불러오기", 0.01, self.show_load_world)
        _btn("설정", -0.08, self.show_settings)
        _btn("종료", -0.17, application.quit)

    # ------------------------------------------------------------------
    def _clear_sub(self):
        if self.sub_panel:
            destroy(self.sub_panel)
            self.sub_panel = None

    def show_new_world(self):
        self._clear_sub()
        panel = Entity(parent=self, z=-0.1)
        self.sub_panel = panel
        Entity(parent=panel, model='quad', color=PANEL_BG,
               scale=(0.55, 0.6), position=(0.45, 0), z=0.1)
        Text(parent=panel, text="새 월드", origin=(0, 0),
             position=(0.45, 0.24), scale=1.2)

        Text(parent=panel, text="이름:", position=(0.24, 0.16), scale=0.8)
        name_field = InputField(parent=panel, default_value="world_1",
                                scale=(0.3, 0.05), position=(0.5, 0.15))
        Text(parent=panel, text="시드 (0=랜덤):", position=(0.24, 0.07),
             scale=0.8)
        seed_field = InputField(parent=panel, default_value="0",
                                scale=(0.3, 0.05), position=(0.5, 0.02))

        mode = ["survival"]
        mode_btn = Button(parent=panel, text="모드: 서바이벌",
                          scale=(0.3, 0.05), position=(0.45, -0.08),
                          color=SLOT_BG, highlight_color=SLOT_HOVER)

        def _toggle_mode():
            mode[0] = "creative" if mode[0] == "survival" else "survival"
            mode_btn.text = "모드: " + (
                "크리에이티브" if mode[0] == "creative" else "서바이벌")
        mode_btn.on_click = _toggle_mode

        def _start():
            name = (name_field.text or "world_1").strip() or "world_1"
            try:
                seed = int(seed_field.text or "0")
            except ValueError:
                seed = abs(hash(seed_field.text)) % (2 ** 31)
            self.on_new_world(name, seed, mode[0])

        Button(parent=panel, text="월드 생성", scale=(0.3, 0.06),
               position=(0.45, -0.18), color=Color(0.2, 0.45, 0.2, 1),
               highlight_color=Color(0.3, 0.6, 0.3, 1), on_click=_start)

    def show_load_world(self):
        self._clear_sub()
        panel = Entity(parent=self, z=-0.1)
        self.sub_panel = panel
        Entity(parent=panel, model='quad', color=PANEL_BG,
               scale=(0.55, 0.6), position=(0.45, 0), z=0.1)
        Text(parent=panel, text="월드 불러오기", origin=(0, 0),
             position=(0.45, 0.24), scale=1.2)
        worlds = save_system.list_worlds()
        if not worlds:
            Text(parent=panel, text="저장된 월드가 없습니다",
                 origin=(0, 0), position=(0.45, 0.05), scale=0.8)
        for i, name in enumerate(worlds[:7]):
            Button(parent=panel, text=name, scale=(0.4, 0.05),
                   position=(0.45, 0.16 - i * 0.06), color=SLOT_BG,
                   highlight_color=SLOT_HOVER,
                   on_click=lambda n=name: self.on_load_world(n))

    def show_settings(self):
        self._clear_sub()
        panel = Entity(parent=self, z=-0.1)
        self.sub_panel = panel
        Entity(parent=panel, model='quad', color=PANEL_BG,
               scale=(0.55, 0.6), position=(0.45, 0), z=0.1)
        Text(parent=panel, text="설정", origin=(0, 0),
             position=(0.45, 0.24), scale=1.2)

        rows = (("render_distance", "렌더 거리", 1, 1, 8),
                ("mouse_sensitivity", "마우스 감도", 5, 5, 120),
                ("fov", "FOV", 5, 50, 120),
                ("day_length", "하루 길이(초)", 60, 120, 3600),
                ("max_fps", "최대 FPS", 10, 30, 240),
                ("sound_volume", "볼륨", 0.1, 0.0, 1.0))
        for row, (key, label, step, lo, hi) in enumerate(rows):
            y = 0.15 - row * 0.07
            lbl = Text(parent=panel, text='', origin=(0, 0),
                       position=(0.45, y), scale=0.8)

            def _update(lbl=lbl, key=key, label=label):
                val = config.get(key)
                if isinstance(val, float):
                    val = round(val, 2)
                lbl.text = f"{label}: {val}"

            def _change(delta, key=key, lo=lo, hi=hi, upd=None):
                val = config.get(key) + delta
                val = max(lo, min(hi, val))
                config.set_value(key, val)
                config.save_settings()
                upd()

            Button(parent=panel, text='-', scale=(0.05, 0.05),
                   position=(0.24, y), color=SLOT_BG,
                   on_click=lambda s=step, k=key, l=lo, h=hi, u=_update:
                   _change(-s, k, l, h, u))
            Button(parent=panel, text='+', scale=(0.05, 0.05),
                   position=(0.66, y), color=SLOT_BG,
                   on_click=lambda s=step, k=key, l=lo, h=hi, u=_update:
                   _change(s, k, l, h, u))
            _update()

    def show_loading(self, text="월드 생성 중..."):
        self._clear_sub()
        panel = Entity(parent=self, z=-0.2)
        self.sub_panel = panel
        Entity(parent=panel, model='quad', color=Color(0, 0, 0, 0.8),
               scale=(3, 2), z=-0.1)
        Text(parent=panel, text=text, origin=(0, 0), position=(0, 0),
             scale=1.5, z=-0.2)
