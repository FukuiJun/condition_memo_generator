"""assets/icon.svg（24px 以下は icon-small.svg）からアプリアイコンを作る（開発用ツール）

作るもの:
- assets/MemoGenerator.ico      … exe のアイコン（16〜256px を1ファイルに収めたもの）
- src/memogenerator/icon_data.py … ウィンドウのアイコン用 PNG（base64 で埋め込み）

使い方（cairosvg と Pillow が必要。アプリ本体の実行には不要）:
    pip install cairosvg pillow
    python tools/make_icon.py
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

import cairosvg
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SVG = ROOT / "assets" / "icon.svg"
SVG_SMALL = ROOT / "assets" / "icon-small.svg"  # 小さいサイズ用（細部を省いて線を太くした版）
SMALL_MAX = 24
ICO = ROOT / "assets" / "MemoGenerator.ico"
MODULE = ROOT / "src" / "memogenerator" / "icon_data.py"

ICO_SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]
WINDOW_SIZES = [256, 48, 32, 16]  # 大きい順（tkinter の iconphoto は先頭を既定として使う）


def render(size: int) -> Image.Image:
    svg = SVG_SMALL if size <= SMALL_MAX else SVG
    png = cairosvg.svg2png(url=str(svg), output_width=size, output_height=size)
    return Image.open(io.BytesIO(png)).convert("RGBA")


def png_bytes(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def main() -> None:
    images = {size: render(size) for size in sorted(set(ICO_SIZES + WINDOW_SIZES))}

    # 各サイズを SVG から直接描いたものを使う（大きい画像の縮小より小さいサイズがくっきりする）
    largest = images[max(ICO_SIZES)]
    largest.save(ICO, format="ICO", sizes=[(s, s) for s in ICO_SIZES],
                 append_images=[images[s] for s in ICO_SIZES if s != max(ICO_SIZES)])

    lines = [
        '"""ウィンドウのアイコン（PNG を base64 で埋め込み）。tools/make_icon.py が生成する。直接編集しない。"""',
        "",
        "PNG_BASE64 = {",
    ]
    for size in WINDOW_SIZES:
        data = base64.b64encode(png_bytes(images[size])).decode("ascii")
        chunks = [data[i:i + 96] for i in range(0, len(data), 96)]
        lines.append(f"    {size}: (")
        lines.extend(f'        "{c}"' for c in chunks)
        lines.append("    ),")
    lines.append("}")
    MODULE.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    print(f"作成: {ICO.relative_to(ROOT)}（{', '.join(map(str, ICO_SIZES))}px）")
    print(f"作成: {MODULE.relative_to(ROOT)}（{', '.join(map(str, WINDOW_SIZES))}px）")


if __name__ == "__main__":
    main()
