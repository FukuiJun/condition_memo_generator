"""入力画面（仕様書 6章 F-01〜F-10, 7章）"""

from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import APP_NAME, __version__
from .errorlog import log_error
from .output import SaveCancelled, SaveError, save_outputs
from .settings import FieldDef, Settings, SettingsError, read_settings_file, write_default_settings
from .state import StateStore, combo_candidates
from .values import coerce_raw, datafile_name, empty_raw, now_text, output_values, validate_input

WINDOW_WIDTH = 600  # 論理ピクセル（96 dpi 換算）
PAD = 4


# ======================================================================== 項目ごとの部品

class FieldWidget:
    """1項目分の入力部品。raw 値の形式は values.py を参照。"""

    def __init__(self, app: "EvalMemoApp", parent: ttk.Frame, field: FieldDef, row: int):
        self.app = app
        self.field = field
        text = field.label + (" *" if field.required else "")
        self.label = ttk.Label(parent, text=text)
        self.label.grid(row=row, column=0, sticky="nw", padx=(PAD, 8), pady=(PAD + 2, PAD))
        self.frame = ttk.Frame(parent)
        self.frame.grid(row=row, column=1, sticky="ew", padx=(0, PAD), pady=PAD)
        self.build(self.frame)

    def build(self, frame: ttk.Frame) -> None:
        raise NotImplementedError

    def get_raw(self) -> object:
        raise NotImplementedError

    def set_raw(self, raw: object) -> None:
        raise NotImplementedError

    def clear(self) -> None:
        self.set_raw(empty_raw(self.field))

    def refresh_candidates(self) -> None:
        pass


class TextWidget(FieldWidget):
    def build(self, frame):
        self.var = tk.StringVar()
        self.entry = ttk.Entry(frame, textvariable=self.var)
        self.entry.pack(fill="x", expand=True)

    def get_raw(self):
        return self.var.get()

    def set_raw(self, raw):
        self.var.set(raw if isinstance(raw, str) else "")


class MultilineWidget(FieldWidget):
    def build(self, frame):
        # width=1: 幅は枠に合わせて広げる（既定の80文字幅だとスクロールバーが押し出される）
        self.text = tk.Text(frame, width=1, height=self.field.rows, wrap="char", undo=True,
                            font="TkTextFont", relief="solid", borderwidth=1)
        bar = ttk.Scrollbar(frame, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        # Tab はタブ文字の入力ではなく次の欄への移動にする
        self.text.bind("<Tab>", self._focus_next)
        self.text.bind("<Shift-Tab>", self._focus_prev)
        self.text.bind("<ISO_Left_Tab>", self._focus_prev)

    def _focus_next(self, _event):
        self.text.tk_focusNext().focus_set()
        return "break"

    def _focus_prev(self, _event):
        self.text.tk_focusPrev().focus_set()
        return "break"

    def get_raw(self):
        return self.text.get("1.0", "end-1c")

    def set_raw(self, raw):
        self.text.delete("1.0", "end")
        if isinstance(raw, str):
            self.text.insert("1.0", raw)
        self.text.edit_reset()


class ComboWidget(FieldWidget):
    def build(self, frame):
        self.var = tk.StringVar()
        self.combo = ttk.Combobox(frame, textvariable=self.var)
        self.combo.pack(fill="x", expand=True)
        self.refresh_candidates()

    def refresh_candidates(self):
        history = self.app.state.history(self.field.id) if self.field.history else []
        self.combo.configure(values=combo_candidates(self.field, history))

    def get_raw(self):
        return self.var.get()

    def set_raw(self, raw):
        self.var.set(raw if isinstance(raw, str) else "")


class SelectWidget(FieldWidget):
    def build(self, frame):
        f = self.field
        self.choice_var = tk.StringVar()
        self.other_var = tk.StringVar()
        values = list(f.options) + ([f.other_option] if f.other_option is not None else [])
        width = max([len(v) for v in values] + [6]) * 2 + 2  # 全角を考慮したおおよその幅
        self.combo = ttk.Combobox(frame, textvariable=self.choice_var, values=values,
                                  state="readonly", width=min(width, 30))
        self.combo.pack(side="left")
        self.combo.bind("<<ComboboxSelected>>", self._on_selected)
        self.other_entry = None
        if f.other_option is not None:
            self.other_entry = ttk.Entry(frame, textvariable=self.other_var, state="disabled")
            self.other_entry.pack(side="left", fill="x", expand=True, padx=(PAD, 0))

    def _is_other(self) -> bool:
        return self.field.other_option is not None and self.choice_var.get() == self.field.other_option

    def _update_other_state(self, focus: bool) -> None:
        if self.other_entry is None:
            return
        if self._is_other():
            self.other_entry.configure(state="normal")
            if focus:
                self.other_entry.focus_set()
                self.other_entry.icursor("end")
        else:
            # 入力不可にするが内容は保持する
            self.other_entry.configure(state="disabled")

    def _on_selected(self, _event=None):
        self.combo.selection_clear()
        self._update_other_state(focus=True)

    def get_raw(self):
        return {"choice": self.choice_var.get(), "other": self.other_var.get()}

    def set_raw(self, raw):
        raw = coerce_raw(self.field, raw) or empty_raw(self.field)
        self.choice_var.set(raw["choice"])
        self.other_var.set(raw["other"])
        self._update_other_state(focus=False)


class CheckgroupWidget(FieldWidget):
    def build(self, frame):
        self.vars: dict[str, tk.BooleanVar] = {}
        for item in self.field.items:
            var = tk.BooleanVar(value=False)
            ttk.Checkbutton(frame, text=item, variable=var).pack(side="left", padx=(0, 10))
            self.vars[item] = var

    def get_raw(self):
        return {item: var.get() for item, var in self.vars.items()}

    def set_raw(self, raw):
        raw = coerce_raw(self.field, raw) or empty_raw(self.field)
        for item, var in self.vars.items():
            var.set(bool(raw.get(item)))


class DatetimeWidget(FieldWidget):
    def build(self, frame):
        self.var = tk.StringVar()
        self.entry = ttk.Entry(frame, textvariable=self.var, width=20)
        self.entry.pack(side="left")
        ttk.Button(frame, text="現在時刻", command=self.set_now).pack(side="left", padx=(PAD, 0))

    def set_now(self):
        self.var.set(now_text())

    def get_raw(self):
        return self.var.get()

    def set_raw(self, raw):
        self.var.set(raw if isinstance(raw, str) else "")

    def clear(self):
        self.set_now()


class DatafileWidget(FieldWidget):
    EMPTY_TEXT = "（未選択）"

    def build(self, frame):
        self.path = ""
        self.name_var = tk.StringVar(value=self.EMPTY_TEXT)
        ttk.Button(frame, text="クリア", command=self.clear).pack(side="right")
        ttk.Button(frame, text="参照", command=self.browse).pack(side="right", padx=(PAD, PAD))
        self.name_label = ttk.Label(frame, textvariable=self.name_var, anchor="w")
        self.name_label.pack(side="left", fill="x", expand=True)

    def browse(self):
        initial = self.app.folder_var.get() or (str(Path(self.path).parent) if self.path else "")
        path = filedialog.askopenfilename(
            parent=self.app.root,
            title=f"{self.field.label}を選択",
            initialdir=initial if initial and Path(initial).is_dir() else None,
            filetypes=[("すべてのファイル", "*.*")],
        )
        if not path:
            return
        path = os.path.normpath(path)
        self.set_raw(path)
        # 保存先をデータファイルのフォルダに変更する（F-05）
        self.app.set_folder(str(Path(path).parent))

    def get_raw(self):
        return self.path

    def set_raw(self, raw):
        self.path = raw if isinstance(raw, str) else ""
        self.name_var.set(datafile_name(self.path) or self.EMPTY_TEXT)


WIDGET_CLASSES: dict[str, type[FieldWidget]] = {
    "text": TextWidget,
    "multiline": MultilineWidget,
    "combo": ComboWidget,
    "select": SelectWidget,
    "checkgroup": CheckgroupWidget,
    "datetime": DatetimeWidget,
    "datafile": DatafileWidget,
}


# ======================================================================== 画面全体

class EvalMemoApp:
    def __init__(self, root: tk.Tk, settings: Settings, settings_path: Path, state: StateStore):
        self.root = root
        self.settings = settings
        self.settings_path = settings_path
        self.state = state
        self.widgets: dict[str, FieldWidget] = {}

        root.title(f"{APP_NAME} v{__version__}")
        self.scale = max(1.0, root.winfo_fpixels("1i") / 96.0)
        self._build_menu()
        self._build_layout()
        self._build_form()
        self._restore_initial_values()

        root.bind_all("<Control-s>", self._on_ctrl_s)
        root.bind_all("<Control-S>", self._on_ctrl_s)
        root.bind_all("<FocusIn>", self._on_focus_in, add="+")
        root.after_idle(self._fit_window)

    # ------------------------------------------------------------ 画面の組み立て

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="設定ファイルを開く", command=self.open_settings_file)
        file_menu.add_command(label="設定を再読み込み", command=self.reload_settings)
        file_menu.add_separator()
        file_menu.add_command(label="終了", command=self.root.destroy)
        menubar.add_cascade(label="ファイル", menu=file_menu)
        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="バージョン情報", command=self.show_version)
        menubar.add_cascade(label="ヘルプ", menu=help_menu)
        self.root.configure(menu=menubar)

    def _build_layout(self):
        root = self.root
        outer = ttk.Frame(root, padding=(6, 6, 6, 4))
        outer.pack(fill="both", expand=True)

        # 入力欄（縦スクロール可能）
        scroll_area = ttk.Frame(outer)
        scroll_area.pack(side="top", fill="both", expand=True)
        bg = ttk.Style().lookup("TFrame", "background") or root.cget("background")
        self.canvas = tk.Canvas(scroll_area, highlightthickness=0, borderwidth=0, background=bg)
        self.vbar = ttk.Scrollbar(scroll_area, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.form_container = ttk.Frame(self.canvas)
        self._form_window = self.canvas.create_window((0, 0), window=self.form_container, anchor="nw")
        self.form_container.bind("<Configure>", self._on_form_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<Enter>", lambda _e: self._bind_wheel(True))
        self.canvas.bind("<Leave>", lambda _e: self._bind_wheel(False))

        # 下部（出力形式・保存先・保存・ステータス）
        bottom = ttk.Frame(outer)
        bottom.pack(side="bottom", fill="x")
        self.bottom = bottom
        ttk.Separator(bottom, orient="horizontal").grid(row=0, column=0, columnspan=3, sticky="ew",
                                                         pady=(6, 6))

        ttk.Label(bottom, text="出力形式").grid(row=1, column=0, sticky="w", padx=(PAD, 8), pady=PAD)
        fmt = ttk.Frame(bottom)
        fmt.grid(row=1, column=1, columnspan=2, sticky="w", pady=PAD)
        # 起動時は毎回 CSV のみチェック（F-04）
        self.csv_var = tk.BooleanVar(value=True)
        self.txt_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(fmt, text="CSV（条件履歴に追記）", variable=self.csv_var).pack(side="left",
                                                                                   padx=(0, 12))
        ttk.Checkbutton(fmt, text="TXT（条件メモ）", variable=self.txt_var).pack(side="left")

        ttk.Label(bottom, text="保存先").grid(row=2, column=0, sticky="w", padx=(PAD, 8), pady=PAD)
        self.folder_var = tk.StringVar()
        self.folder_label = ttk.Label(bottom, textvariable=self.folder_var, anchor="w")
        self.folder_label.grid(row=2, column=1, sticky="ew", pady=PAD)
        ttk.Button(bottom, text="変更", command=self.choose_folder).grid(row=2, column=2, sticky="e",
                                                                        padx=(PAD, PAD), pady=PAD)

        self.save_button = ttk.Button(bottom, text="保存", command=self.save)
        self.save_button.grid(row=3, column=2, sticky="e", padx=(PAD, PAD), pady=(PAD, PAD))

        self.status_var = tk.StringVar(value="ステータス：")
        self.status_label = ttk.Label(bottom, textvariable=self.status_var, anchor="w")
        self.status_label.grid(row=4, column=0, columnspan=3, sticky="ew", padx=(PAD, PAD), pady=(2, 2))
        bottom.columnconfigure(1, weight=1)
        bottom.bind("<Configure>", self._on_bottom_configure)

    def _build_form(self):
        for child in self.form_container.winfo_children():
            child.destroy()
        self.widgets = {}
        self.form_container.columnconfigure(0, weight=0)
        self.form_container.columnconfigure(1, weight=1)
        for row, f in enumerate(self.settings.fields):
            self.widgets[f.id] = WIDGET_CLASSES[f.type](self, self.form_container, f, row)

    def _initial_raw(self, field: FieldDef) -> object:
        """起動時（または新しく追加された項目）の初期値（F-02）"""
        if field.type == "datetime":
            return now_text()
        remembered = self.state.remembered(field)
        return remembered if remembered is not None else empty_raw(field)

    def _restore_initial_values(self):
        for f in self.settings.fields:
            self.widgets[f.id].set_raw(self._initial_raw(f))
        folder = self.state.last_folder
        self.folder_var.set(folder if folder and Path(folder).is_dir() else "")

    # ------------------------------------------------------------ レイアウト調整

    def _on_form_configure(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self._update_scrollbar()

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self._form_window, width=event.width)
        self._update_scrollbar()

    def _on_bottom_configure(self, event):
        self.status_label.configure(wraplength=max(100, event.width - 10))
        self.folder_label.configure(wraplength=max(100, event.width - 200))

    def _needs_scroll(self) -> bool:
        return self.form_container.winfo_reqheight() > self.canvas.winfo_height() + 1

    def _update_scrollbar(self):
        if self._needs_scroll():
            if not self.vbar.winfo_ismapped():
                self.vbar.pack(side="right", fill="y")
        else:
            if self.vbar.winfo_ismapped():
                self.vbar.pack_forget()
            self.canvas.yview_moveto(0)

    def _fit_window(self):
        """幅 600px、高さは項目数に合わせる。画面に収まらなければ入力欄をスクロールさせる。"""
        self.root.update_idletasks()
        width = int(WINDOW_WIDTH * self.scale)
        form_h = self.form_container.winfo_reqheight()
        other_h = self.bottom.winfo_reqheight() + int(20 * self.scale)
        screen_h = self.root.winfo_screenheight()
        max_form_h = max(150, screen_h - other_h - int(120 * self.scale))
        canvas_h = min(form_h, max_form_h)
        self.canvas.configure(height=canvas_h)
        height = canvas_h + other_h
        self.root.geometry(f"{width}x{height}")
        self.root.minsize(int(400 * self.scale), min(height, int(300 * self.scale)))
        self.root.update_idletasks()
        self._update_scrollbar()

    def _bind_wheel(self, on: bool):
        if on:
            self.root.bind_all("<MouseWheel>", self._on_wheel)
            self.root.bind_all("<Button-4>", self._on_wheel)
            self.root.bind_all("<Button-5>", self._on_wheel)
        else:
            self.root.unbind_all("<MouseWheel>")
            self.root.unbind_all("<Button-4>")
            self.root.unbind_all("<Button-5>")

    def _on_wheel(self, event):
        if not self._needs_scroll():
            return None
        if getattr(event, "num", None) == 4:
            step = -1
        elif getattr(event, "num", None) == 5:
            step = 1
        else:
            step = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(step * 3, "units")
        return "break"

    def _on_focus_in(self, event):
        """Tab で移動した欄が見えるように入力欄をスクロールする"""
        widget = event.widget
        if not isinstance(widget, tk.Misc) or not self._needs_scroll():
            return
        try:
            if not str(widget).startswith(str(self.form_container)):
                return
            top = widget.winfo_rooty() - self.form_container.winfo_rooty()
            bottom = top + widget.winfo_height()
        except tk.TclError:
            return
        total = max(1, self.form_container.winfo_height())
        view_top = self.canvas.canvasy(0)
        view_bottom = view_top + self.canvas.winfo_height()
        if top < view_top:
            self.canvas.yview_moveto(max(0, top - 4) / total)
        elif bottom > view_bottom:
            self.canvas.yview_moveto(max(0, bottom + 4 - self.canvas.winfo_height()) / total)

    # ------------------------------------------------------------ 保存先（F-05）

    def set_folder(self, folder: str):
        self.folder_var.set(folder)

    def choose_folder(self):
        current = self.folder_var.get()
        folder = filedialog.askdirectory(
            parent=self.root, title="保存先フォルダを選択",
            initialdir=current if current and Path(current).is_dir() else None, mustexist=True)
        if folder:
            self.set_folder(os.path.normpath(folder))

    # ------------------------------------------------------------ 保存（F-06〜F-09）

    def collect_raw(self) -> dict[str, object]:
        return {fid: w.get_raw() for fid, w in self.widgets.items()}

    def _on_ctrl_s(self, _event=None):
        self.save()
        return "break"

    def set_status(self, text: str):
        self.status_var.set(f"ステータス：{text}")

    def _confirm_new_csv(self, name: str) -> bool:
        return messagebox.askokcancel(
            "条件履歴", f"項目構成が変わったため、新しいファイル {name} に保存します", parent=self.root)

    def _retry_locked(self, name: str) -> bool:
        return messagebox.askretrycancel(
            "条件履歴", f"{name} が開かれています。閉じてから［再試行］を押してください",
            icon="warning", parent=self.root)

    def save(self):
        settings = self.settings
        raw = self.collect_raw()
        folder = self.folder_var.get().strip()
        want_csv = self.csv_var.get()
        want_txt = self.txt_var.get()

        errors = validate_input(settings, raw, folder, want_csv, want_txt)
        if errors:
            if errors == ["出力形式を1つ以上選んでください"]:
                message = errors[0]
            else:
                message = "入力内容を確認してください。\n\n" + "\n".join(f"・{e}" for e in errors)
            messagebox.showwarning("入力チェック", message, parent=self.root)
            return

        out = output_values(settings, raw)
        try:
            names = save_outputs(settings, out, Path(folder), want_txt=want_txt, want_csv=want_csv,
                                 confirm_new_csv=self._confirm_new_csv,
                                 retry_locked=self._retry_locked)
        except SaveCancelled:
            self.set_status("保存をキャンセルしました（ファイルは保存されていません）")
            return
        except SaveError as e:
            log_error(f"保存に失敗しました: {e.message}", e.cause)
            messagebox.showerror("保存エラー", f"{e.message}\n\nファイルは保存されていません。",
                                 parent=self.root)
            self.set_status("保存に失敗しました（ファイルは保存されていません）")
            return

        status = "保存しました：" + ", ".join(names)
        try:
            self.state.update_after_save(settings, raw, out, folder)
            self.state.save()
        except OSError as e:
            log_error("state.json の書き込みに失敗しました", e)
            status += "　※前回値・入力履歴を保存できませんでした"

        self.set_status(status)
        for f in settings.fields:
            w = self.widgets[f.id]
            w.refresh_candidates()
            if f.type == "datetime":
                w.clear()  # 現在時刻に更新
            elif not f.remember:
                w.clear()

    # ------------------------------------------------------------ メニュー（F-10）

    def open_settings_file(self):
        path = self.settings_path
        try:
            if not path.exists():
                write_default_settings(path)
            if sys.platform.startswith("win"):
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except OSError as e:
            log_error(f"設定ファイルを開けませんでした: {path}", e)
            messagebox.showerror("設定ファイル", f"設定ファイルを開けませんでした。\n{path}\n\n{e}",
                                 parent=self.root)

    def reload_settings(self):
        try:
            new_settings = read_settings_file(self.settings_path)
        except SettingsError as e:
            show_settings_errors(self.root, e.errors, reload=True)
            return
        current = {fid: (w.field.type, w.get_raw()) for fid, w in self.widgets.items()}
        self.settings = new_settings
        self._build_form()
        for f in new_settings.fields:
            value = None
            if f.id in current and current[f.id][0] == f.type:
                value = coerce_raw(f, current[f.id][1])  # 入力中の値を引き継ぐ
            self.widgets[f.id].set_raw(value if value is not None else self._initial_raw(f))
        self._fit_window()
        self.set_status("設定を再読み込みしました")

    def show_version(self):
        messagebox.showinfo("バージョン情報", f"{APP_NAME} v{__version__}\n評価条件メモ出力ソフト",
                            parent=self.root)


def show_settings_errors(root: tk.Misc, errors: list[str], reload: bool) -> None:
    after = "画面は変更前のままです。" if reload else "既定の設定で起動します（settings.json は変更していません）。"
    shown = errors[:30]
    body = "\n".join(f"・{e}" for e in shown)
    if len(errors) > len(shown):
        body += f"\n・ほか {len(errors) - len(shown)} 件"
    messagebox.showerror("設定ファイルのエラー",
                         f"settings.json に誤りがあります。{after}\n\n{body}", parent=root)
