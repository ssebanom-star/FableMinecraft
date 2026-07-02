"""
fonts.py - 한글 폰트 자동 적용.

ursina 기본 폰트(OpenSans)에는 한글 글리프가 없어 한글 UI 가 □ 로 깨진다.
운영체제별 기본 한글 폰트를 찾아 Text.default_font 로 지정한다.

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


def find_korean_font():
    """존재하는 첫 번째 한글 폰트 경로. 없으면 None."""
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    return None


def apply_korean_font():
    """
    Text.default_font 를 한글 폰트로 교체한다.
    Ursina() 생성 이후, UI 생성 이전에 호출해야 한다.
    반환: 적용된 폰트 경로 또는 None
    """
    from ursina import Text

    path = find_korean_font()
    if path:
        try:
            Text.default_font = path
            return path
        except Exception:
            pass
    print("[fonts] 한글 폰트를 찾지 못했습니다. 한글이 깨져 보이면 "
          "assets/font.ttf 위치에 한글 TTF 폰트를 넣어 주세요. "
          "(예: 나눔고딕 NanumGothic.ttf)")
    return None
