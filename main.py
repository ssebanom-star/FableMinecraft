"""
main.py - 진입점.

실행:
    pip install -r requirements.txt
    python main.py
"""

import time

from ursina import Ursina, Entity, window, mouse, invoke, destroy
from panda3d.core import ClockObject

import config
import fonts
from game import Game
from ui import GameUI, MainMenu
from utils import set_mouse_locked


class Controller(Entity):
    """게임 루프/입력을 Game 객체로 위임하는 엔티티."""

    def __init__(self):
        super().__init__()
        self.game = None

    def update(self):
        if self.game:
            self.game.update(time.dt)

    def input(self, key):
        if self.game:
            self.game.input(key)


class App:
    def __init__(self):
        config.load_settings()
        res = config.get("resolution")
        self.app = Ursina(
            title="Blockworld",
            borderless=False,
            fullscreen=bool(config.get("fullscreen")),
            size=(int(res[0]), int(res[1])),
            vsync=True,
        )
        # 에디터용 오버레이 비활성화 (버전에 따라 없을 수 있음)
        for widget in ("editor_ui", "cog_menu", "cog_button", "exit_button",
                       "fps_counter", "entity_counter", "collider_counter"):
            w = getattr(window, widget, None)
            if w is not None:
                w.enabled = False

        # 한글 폰트 적용 (UI 생성 전, 실패해도 게임 실행은 계속)
        try:
            fonts.apply_korean_font()
        except Exception as e:
            print(f"[fonts] 폰트 적용 건너뜀: {e}")

        # 최대 FPS 제한
        max_fps = int(config.get("max_fps"))
        clock = ClockObject.getGlobalClock()
        clock.setMode(ClockObject.MLimited)
        clock.setFrameRate(max_fps)

        self.controller = Controller()
        self.menu = MainMenu(on_new_world=self.start_new_world,
                             on_load_world=self.load_world)
        self.game = None
        self.game_ui = None
        set_mouse_locked(False)

    # ------------------------------------------------------------------
    def start_new_world(self, name, seed, mode):
        self.menu.show_loading("월드 생성 중... (잠시 기다려 주세요)")
        invoke(lambda: self._create_game(name, seed, mode, False), delay=0.1)

    def load_world(self, name):
        self.menu.show_loading("월드 불러오는 중...")
        invoke(lambda: self._create_game(name, 0, None, True), delay=0.1)

    def _create_game(self, name, seed, mode, load_existing):
        self.game = Game(name, seed=seed, mode=mode,
                         load_existing=load_existing)
        self.game_ui = GameUI(self.game, on_exit_to_menu=self.exit_to_menu)
        self.game.ui = self.game_ui
        self.controller.game = self.game
        self.menu.enabled = False

    def exit_to_menu(self):
        """저장 후 메인 메뉴로 복귀."""
        if self.game:
            self.controller.game = None
            self.game.shutdown()
            self.game_ui.cleanup()
            self.game = None
            self.game_ui = None
        # 메뉴 재생성 (월드 목록 갱신)
        destroy(self.menu)
        self.menu = MainMenu(on_new_world=self.start_new_world,
                             on_load_world=self.load_world)
        set_mouse_locked(False)

    def run(self):
        self.app.run()


def _run_with_crash_log():
    """예외 발생 시 전체 트레이스백을 crash_log.txt 에 남기고
    콘솔이 바로 닫히지 않게 한다 (윈도우 더블클릭 실행 대비)."""
    import sys
    import traceback
    try:
        App().run()
    except Exception:
        text = traceback.format_exc()
        print(text)
        try:
            with open("crash_log.txt", "w", encoding="utf-8") as f:
                f.write(text)
            print("\n[!] 오류 내용이 crash_log.txt 에 저장되었습니다.")
        except OSError:
            pass
        if sys.stdin is not None and sys.stdin.isatty():
            try:
                input("종료하려면 Enter 를 누르세요...")
            except (EOFError, KeyboardInterrupt):
                pass
        raise SystemExit(1)


if __name__ == "__main__":
    _run_with_crash_log()
