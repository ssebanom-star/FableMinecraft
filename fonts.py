"""
fonts.py - 한글 폰트 자동 적용.

ursina 기본 폰트(OpenSans)에는 한글 글리프가 없어 한글 UI 가 □ 로 깨진다.
운영체제별 기본 한글 폰트를 찾아 Text.default_font 로 지정한다.

안전 원칙:
- 후보 폰트는 실제로 loadFont 로 열어본 뒤에만 적용한다
  (경로가 존재해도 로드에 실패하는 폰트가 있으면 게임이 죽지 않고
   다음 후보 -> 기본 폰트 순으로 넘어간다).
- 경로는 panda3d 가 기대하는 슬래시(/) 형식으로 변환한다 (윈도우 대응).

우선순위:
1. assets/font.ttf (사용자가 직접 넣은 폰트 - 아무 한글 TTF 나 가능)
2. OS 기본 한글 폰트 (맑은 고딕 / Apple SD Gothic / Noto·나눔 등)
"""

import os


def _windows_fonts():
    windir = os.environ.get("WINDIR", "C:/Windows")
    fonts = os.path.join(windir, "Fonts")
    return [
        os.path.join(fonts, "malgun.ttf"),       # 맑은 고딕
        os.path.join(fonts, "malgunbd.ttf"),
        os.path.join(fonts, "NanumGothic.ttf"),
        os.path.join(fonts, "gulim.ttc"),        # 굴림
        os.path.join(fonts, "batang.ttc"),
    ]


FONT_CANDIDATES = [
    os.path.join("assets", "font.ttf"),          # 사용자 지정
    *_windows_fonts(),
    # macOS
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
    "/Library/Fonts/AppleGothic.ttf",
    # Linux
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-KR-Regular.otf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc",
]


def _try_load(path):
    """panda3d 로더로 폰트를 실제로 열어본다. 실패하면 None."""
    import builtins
    posix = os.path.abspath(path).replace("\\", "/")
    loader = getattr(builtins, "loader", None)
    if loader is None:
        return None
    try:
        font = loader.loadFont(posix, okMissing=True)
    except Exception:
        return None
    if font is None:
        return None
    try:
        if hasattr(font, "isValid") and not font.isValid():
            return None
    except Exception:
        pass
    return posix


def find_korean_font():
    """로드 가능한 첫 번째 한글 폰트 경로. 없으면 None."""
    for path in FONT_CANDIDATES:
        if not os.path.exists(path):
            continue
        posix = _try_load(path)
        if posix:
            return posix
    return None


def apply_korean_font():
    """
    Text.default_font 를 한글 폰트로 교체한다.
    Ursina() 생성 이후, UI 생성 이전에 호출해야 한다.
    실패해도 절대 예외를 밖으로 던지지 않는다 (기본 폰트로 계속 진행).
    반환: 적용된 폰트 경로 또는 None
    """
    try:
        from ursina import Text

        path = find_korean_font()
        if path:
            # 실제 Text 생성까지 검증 (여기서 실패하면 기본 폰트 유지)
            old = Text.default_font
            try:
                Text.default_font = path
                probe = Text(text="가")
                from ursina import destroy
                destroy(probe)
                print(f"[fonts] 한글 폰트 적용: {path}")
                return path
            except Exception as e:
                Text.default_font = old
                print(f"[fonts] 폰트 적용 실패({path}): {e} - 기본 폰트 사용")
                return None
    except Exception as e:
        print(f"[fonts] 폰트 설정 중 오류 (무시하고 계속): {e}")
        return None

    print("[fonts] 한글 폰트를 찾지 못했습니다. 한글이 깨져 보이면 "
          "assets/font.ttf 위치에 한글 TTF 폰트를 넣어 주세요. "
          "(예: 나눔고딕 NanumGothic.ttf)")
    return None
