"""画面デザイン「ラボノート」：色・フォント・ttk スタイルの定義

生成り色の紙の上に白い入力カード、濃紺のヘッダ帯と保存ボタン。
色やフォントを変えるときはこのファイルだけを編集する。
"""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from dataclasses import dataclass
from tkinter import ttk

PAPER = "#F5F3EE"  # 背景（紙）
PAPER_DARK = "#ECE8DF"  # ステータスバー
CARD = "#FFFFFF"  # 入力カード
BORDER = "#D9D4C7"  # 枠線
BUTTON = "#EDEAE2"  # 通常ボタン
BUTTON_HOVER = "#E2DED3"
DISABLED = "#F0EEE8"  # 入力不可の欄
ACCENT = "#1F3A5F"  # 濃紺（ヘッダ帯・保存ボタン・フォーカス枠）
ACCENT_HOVER = "#2B4F7E"
ACCENT_PRESSED = "#162B47"
ACCENT_SUB = "#C9D3E0"  # ヘッダ帯の補助文字
TEXT = "#2B2B2B"
MUTED = "#6B6B6B"
REQUIRED = "#C0392B"  # 必須の *
HIGHLIGHT = "#FFF4CC"  # 保存先が変わったときの強調

STATUS_COLORS = {
    "info": ACCENT,
    "ok": "#2E7D32",
    "warn": "#B26A00",
    "error": "#C0392B",
}
STATUS_ICONS = {"info": "ℹ", "ok": "✓", "warn": "⚠", "error": "✕"}

FONT_CANDIDATES = ("Yu Gothic UI", "Meiryo UI", "Meiryo")


@dataclass
class Fonts:
    base: tkfont.Font
    bold: tkfont.Font
    title: tkfont.Font
    small: tkfont.Font
    button: tkfont.Font


def _font_exists(root: tk.Misc, family: str) -> bool:
    # 全フォント一覧（tkfont.families）の取得はフォントが多い PC で遅いので、候補ごとに確かめる
    return tkfont.Font(root=root, family=family).actual("family") == family


def _setup_fonts(root: tk.Misc) -> Fonts:
    default = tkfont.nametofont("TkDefaultFont", root=root)
    family = next((f for f in FONT_CANDIDATES if _font_exists(root, f)), default.actual("family"))
    size = 10
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        try:
            tkfont.nametofont(name, root=root).configure(family=family, size=size)
        except tk.TclError:
            pass
    return Fonts(
        base=tkfont.nametofont("TkDefaultFont", root=root),
        bold=tkfont.Font(root=root, family=family, size=size, weight="bold"),
        title=tkfont.Font(root=root, family=family, size=13, weight="bold"),
        small=tkfont.Font(root=root, family=family, size=9),
        button=tkfont.Font(root=root, family=family, size=11, weight="bold"),
    )


def apply_theme(root: tk.Tk) -> Fonts:
    fonts = _setup_fonts(root)
    style = ttk.Style(root)
    style.theme_use("clam")
    root.configure(background=PAPER)

    style.configure(".", background=PAPER, foreground=TEXT, font=fonts.base,
                    bordercolor=BORDER, lightcolor=PAPER, darkcolor=PAPER,
                    troughcolor=PAPER, focuscolor=ACCENT,
                    selectbackground=ACCENT, selectforeground="#FFFFFF")

    # 枠
    style.configure("TFrame", background=PAPER)
    style.configure("CardInner.TFrame", background=CARD)
    style.configure("Header.TFrame", background=ACCENT)
    style.configure("Status.TFrame", background=PAPER_DARK)

    # 文字
    style.configure("TLabel", background=PAPER, foreground=TEXT)
    style.configure("Card.TLabel", background=CARD, foreground=TEXT)
    style.configure("CardMuted.TLabel", background=CARD, foreground=MUTED, font=fonts.small)
    style.configure("Required.TLabel", background=CARD, foreground=REQUIRED, font=fonts.bold)
    style.configure("Section.TLabel", background=CARD, foreground=ACCENT, font=fonts.bold)
    style.configure("Heading.TLabel", background=PAPER, foreground=MUTED, font=fonts.bold)
    style.configure("Header.TLabel", background=ACCENT, foreground="#FFFFFF", font=fonts.title)
    style.configure("HeaderSub.TLabel", background=ACCENT, foreground=ACCENT_SUB, font=fonts.small)
    style.configure("Folder.TLabel", background=PAPER, foreground=TEXT)
    style.configure("FolderHighlight.TLabel", background=HIGHLIGHT, foreground=TEXT)
    for kind, color in STATUS_COLORS.items():
        style.configure(f"Status{kind}.TLabel", background=PAPER_DARK, foreground=color)

    # 入力欄
    field_opts = dict(fieldbackground=CARD, foreground=TEXT, bordercolor=BORDER,
                      lightcolor=CARD, darkcolor=CARD, insertcolor=TEXT, padding=(4, 3))
    style.configure("TEntry", **field_opts)
    style.map("TEntry",
              fieldbackground=[("disabled", DISABLED)],
              foreground=[("disabled", MUTED)],
              bordercolor=[("focus", ACCENT)],
              lightcolor=[("focus", ACCENT)])
    style.configure("TCombobox", **field_opts, background=BUTTON, arrowcolor=TEXT)
    style.map("TCombobox",
              fieldbackground=[("readonly", CARD), ("disabled", DISABLED)],
              selectbackground=[("readonly", CARD)],
              selectforeground=[("readonly", TEXT)],
              background=[("active", BUTTON_HOVER)],
              bordercolor=[("focus", ACCENT)],
              lightcolor=[("focus", ACCENT)])
    # プルダウンの一覧
    root.option_add("*TCombobox*Listbox.background", CARD)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", "#FFFFFF")
    root.option_add("*TCombobox*Listbox.font", fonts.base)

    # チェックボックス：clam 標準の印は色を変えられないため、画像で描いた印に差し替える
    scale = max(1.0, root.winfo_fpixels("1i") / 96.0)
    images = _check_images(root, round(14 * scale), gap=round(6 * scale))
    root._memogenerator_check_images = images  # 画像が破棄されないよう保持
    style.element_create("Lab.Checkbutton.indicator", "image", images["off"],
                         ("disabled", images["disabled"]),
                         ("selected", images["on"]),
                         ("active", images["hover"]),
                         sticky="")
    style.layout("TCheckbutton", [
        ("Checkbutton.padding", {"sticky": "nswe", "children": [
            ("Lab.Checkbutton.indicator", {"side": "left", "sticky": ""}),
            ("Checkbutton.focus", {"side": "left", "sticky": "w", "children": [
                ("Checkbutton.label", {"sticky": "nswe"})]})]})])
    for name, bg in (("TCheckbutton", PAPER), ("Card.TCheckbutton", CARD)):
        style.configure(name, background=bg, foreground=TEXT, padding=(0, 2))
        style.map(name, background=[("active", bg)])

    # ボタン
    style.configure("TButton", background=BUTTON, foreground=TEXT, bordercolor=BORDER,
                    lightcolor=BUTTON, darkcolor=BUTTON, padding=(10, 3))
    style.map("TButton",
              background=[("pressed", BORDER), ("active", BUTTON_HOVER)],
              lightcolor=[("pressed", BORDER), ("active", BUTTON_HOVER)],
              darkcolor=[("pressed", BORDER), ("active", BUTTON_HOVER)])
    style.configure("Accent.TButton", background=ACCENT, foreground="#FFFFFF", bordercolor=ACCENT,
                    lightcolor=ACCENT, darkcolor=ACCENT, font=fonts.button, padding=(26, 8))
    style.map("Accent.TButton",
              background=[("pressed", ACCENT_PRESSED), ("active", ACCENT_HOVER)],
              lightcolor=[("pressed", ACCENT_PRESSED), ("active", ACCENT_HOVER)],
              darkcolor=[("pressed", ACCENT_PRESSED), ("active", ACCENT_HOVER)],
              bordercolor=[("focus", ACCENT_PRESSED)])

    # スクロールバー
    style.configure("Vertical.TScrollbar", background=BUTTON, troughcolor=CARD, bordercolor=BORDER,
                    lightcolor=BUTTON, darkcolor=BUTTON, arrowcolor=MUTED)
    style.map("Vertical.TScrollbar", background=[("active", BUTTON_HOVER)])

    style.configure("TSeparator", background=BORDER)
    return fonts


def _check_images(root: tk.Misc, size: int, gap: int) -> dict[str, tk.PhotoImage]:
    """チェックボックスの印（未選択・ホバー・選択・無効）。右側の gap ピクセルは透明（文字との間隔）"""

    def box(border: str, fill: str) -> tk.PhotoImage:
        img = tk.PhotoImage(master=root, width=size + gap, height=size)
        img.put(border, to=(0, 0, size, size))
        img.put(fill, to=(1, 1, size - 1, size - 1))
        return img

    on = box(ACCENT, ACCENT)
    # 白いチェック印（左下がりの短い線＋右上がりの長い線）
    thick = max(2, size // 7)
    points = [(0.22, 0.52), (0.42, 0.72), (0.80, 0.30)]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        steps = size * 2
        for i in range(steps + 1):
            t = i / steps
            x = round((x0 + (x1 - x0) * t) * size - thick / 2)
            y = round((y0 + (y1 - y0) * t) * size - thick / 2)
            on.put("#FFFFFF", to=(max(1, x), max(1, y), min(size - 1, x + thick), min(size - 1, y + thick)))
    return {
        "off": box(MUTED, CARD),
        "hover": box(ACCENT, "#E8EDF3"),
        "on": on,
        "disabled": box(BORDER, DISABLED),
    }


def fit_text(font: tkfont.Font, text: str, width: int, keep: str = "tail") -> str:
    """width（ピクセル）に収まるよう「…」で省略する。keep="tail" は末尾を残す（フォルダ向け）、
    "both" は先頭と末尾を残す（ファイル名向け、拡張子が見えるように）。"""
    if width <= 0 or font.measure(text) <= width:
        return text
    if keep == "tail":
        for i in range(1, len(text)):
            candidate = "…" + text[i:]
            if font.measure(candidate) <= width:
                return candidate
        return "…"
    head, tail = len(text) // 2, len(text) - len(text) // 2
    while head > 0 or tail > 0:
        if tail >= head and tail > 0:
            tail -= 1
        else:
            head -= 1
        candidate = text[:head] + "…" + text[len(text) - tail:]
        if font.measure(candidate) <= width:
            return candidate
    return "…"


def style_text_widget(text: tk.Text, fonts: Fonts) -> None:
    """複数行テキスト（tk.Text）を ttk の入力欄と同じ見た目にする"""
    text.configure(background=CARD, foreground=TEXT, insertbackground=TEXT, font=fonts.base,
                   relief="flat", borderwidth=0, highlightthickness=1,
                   highlightbackground=BORDER, highlightcolor=ACCENT,
                   selectbackground=ACCENT, selectforeground="#FFFFFF", padx=4, pady=3)
