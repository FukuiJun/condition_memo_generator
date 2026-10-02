"""画面デザイン「ペンスタンド」：色・フォント・ttk スタイルの定義

明るいグレーの台に白いメモ帳（入力欄のカード）。上部はペン立てのようなチャコールの帯に白いタイトルと
水色の丸ラベル。メニュー下とステータス欄の上に水色の細い線、保存ボタンは薄い水色。
色やフォントを変えるときはこのファイルだけを編集する。
"""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from dataclasses import dataclass
from tkinter import ttk

PAPER = "#EAE8E8"  # 背景（明るいグレーの台）
CARD = "#FBF9F7"  # 入力欄をまとめる面（白いメモ帳）
FIELD = "#FFFFFF"  # 入力欄の中
BORDER = "#D2CECE"  # 面の枠線・見出しの下線
FIELD_BORDER = "#CFCBCB"  # 入力欄・ボタンの枠線
LINE = "#9ABDD6"  # メニュー下・ステータス欄の上の水色の線
BAND = "#3A3330"  # タイトル帯（チャコール）
BAND_TEXT = "#FFFFFF"
PILL = "#9ABDD6"  # タイトル横の丸ラベル
PILL_TEXT = "#2B2725"
BUTTON = "#EFEDED"  # 通常ボタン
BUTTON_HOVER = "#E4E2E2"
BUTTON_PRESSED = "#D9D6D6"
DISABLED = "#F0EEEE"  # 入力不可の欄
SAVE = "#B3CFE2"  # 保存ボタン（薄い水色）
SAVE_HOVER = "#A6C6DC"
SAVE_PRESSED = "#9ABDD6"
SAVE_TEXT = "#2B2725"
SAVE_BORDER = "#9ABDD6"
ACCENT = "#3A3330"  # チェックの色・選択中の行
FOCUS = "#6F9BBB"  # 入力欄のフォーカス枠
FOCUS_TINT = "#E6EEF4"  # チェック欄にマウスを乗せたとき
TEXT = "#4A4543"
HEADING = "#4A4543"  # 見出し（測定条件・出力・保存先）
MUTED = "#6A6563"
REQUIRED = "#B4553A"  # 必須の *
HIGHLIGHT = "#DCE8F1"  # 保存先が変わったときの強調
STATUS_BG = "#F5F5F5"  # ステータス欄

STATUS_COLORS = {
    "info": "#36607F",
    "ok": "#3E6A50",
    "warn": "#8F6420",
    "error": "#A8432E",
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
        title=tkfont.Font(root=root, family=family, size=15, weight="bold"),
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
                    troughcolor=PAPER, focuscolor=FOCUS,
                    selectbackground=ACCENT, selectforeground="#FFFFFF")

    # 枠
    style.configure("TFrame", background=PAPER)
    style.configure("CardInner.TFrame", background=CARD)
    style.configure("Band.TFrame", background=BAND)
    style.configure("Status.TFrame", background=STATUS_BG)

    # 文字
    style.configure("TLabel", background=PAPER, foreground=TEXT)
    style.configure("Card.TLabel", background=CARD, foreground=TEXT)
    style.configure("CardMuted.TLabel", background=CARD, foreground=MUTED, font=fonts.small)
    style.configure("Required.TLabel", background=CARD, foreground=REQUIRED, font=fonts.bold)
    style.configure("Section.TLabel", background=CARD, foreground=HEADING, font=fonts.bold)
    style.configure("Heading.TLabel", background=PAPER, foreground=HEADING, font=fonts.bold)
    style.configure("Band.TLabel", background=BAND, foreground=BAND_TEXT, font=fonts.title)
    style.configure("Folder.TLabel", background=PAPER, foreground=TEXT)
    style.configure("FolderHighlight.TLabel", background=HIGHLIGHT, foreground=TEXT)
    for kind, color in STATUS_COLORS.items():
        style.configure(f"Status{kind}.TLabel", background=STATUS_BG, foreground=color)

    # 入力欄
    field_opts = dict(fieldbackground=FIELD, foreground=TEXT, bordercolor=FIELD_BORDER,
                      lightcolor=FIELD, darkcolor=FIELD, insertcolor=TEXT, padding=(4, 3))
    style.configure("TEntry", **field_opts)
    style.map("TEntry",
              fieldbackground=[("disabled", DISABLED)],
              foreground=[("disabled", MUTED)],
              bordercolor=[("focus", FOCUS)],
              lightcolor=[("focus", FOCUS)])
    style.configure("TCombobox", **field_opts, background=BUTTON, arrowcolor=TEXT)
    style.map("TCombobox",
              fieldbackground=[("readonly", FIELD), ("disabled", DISABLED)],
              selectbackground=[("readonly", FIELD)],
              selectforeground=[("readonly", TEXT)],
              background=[("active", BUTTON_HOVER)],
              bordercolor=[("focus", FOCUS)],
              lightcolor=[("focus", FOCUS)])
    # プルダウンの一覧
    root.option_add("*TCombobox*Listbox.background", FIELD)
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
    style.configure("TButton", background=BUTTON, foreground=TEXT, bordercolor=FIELD_BORDER,
                    lightcolor=BUTTON, darkcolor=BUTTON, padding=(10, 3))
    style.map("TButton",
              background=[("pressed", BUTTON_PRESSED), ("active", BUTTON_HOVER)],
              lightcolor=[("pressed", BUTTON_PRESSED), ("active", BUTTON_HOVER)],
              darkcolor=[("pressed", BUTTON_PRESSED), ("active", BUTTON_HOVER)])
    style.configure("Accent.TButton", background=SAVE, foreground=SAVE_TEXT, bordercolor=SAVE_BORDER,
                    lightcolor=SAVE, darkcolor=SAVE, font=fonts.button, padding=(28, 8))
    style.map("Accent.TButton",
              background=[("pressed", SAVE_PRESSED), ("active", SAVE_HOVER)],
              lightcolor=[("pressed", SAVE_PRESSED), ("active", SAVE_HOVER)],
              darkcolor=[("pressed", SAVE_PRESSED), ("active", SAVE_HOVER)],
              bordercolor=[("focus", FOCUS)])

    # スクロールバー
    style.configure("Vertical.TScrollbar", background=BUTTON, troughcolor=CARD, bordercolor=FIELD_BORDER,
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
        "off": box(MUTED, FIELD),
        "hover": box(FOCUS, FOCUS_TINT),
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
    text.configure(background=FIELD, foreground=TEXT, insertbackground=TEXT, font=fonts.base,
                   relief="flat", borderwidth=0, highlightthickness=1,
                   highlightbackground=FIELD_BORDER, highlightcolor=FOCUS,
                   selectbackground=ACCENT, selectforeground="#FFFFFF", padx=4, pady=3)


def make_pill(parent: tk.Misc, text: str, font: tkfont.Font, background: str) -> tk.Canvas:
    """角の丸いラベル（タイトル横の「評価条件メモ」）。background は置く場所の背景色"""
    scale = max(1.0, parent.winfo_fpixels("1i") / 96.0)
    pad_x, pad_y = round(12 * scale), round(3 * scale)
    w = font.measure(text) + pad_x * 2
    h = font.metrics("linespace") + pad_y * 2
    canvas = tk.Canvas(parent, width=w, height=h, background=background, highlightthickness=0, borderwidth=0)
    r = h / 2
    canvas.create_oval(0, 0, h, h, fill=PILL, outline=PILL)
    canvas.create_oval(w - h, 0, w, h, fill=PILL, outline=PILL)
    canvas.create_rectangle(r, 0, w - r, h, fill=PILL, outline=PILL)
    canvas.create_text(w / 2, h / 2, text=text, fill=PILL_TEXT, font=font)
    return canvas
