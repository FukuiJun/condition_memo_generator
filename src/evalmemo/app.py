"""起動処理"""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import messagebox

from . import paths
from .errorlog import log_error
from .settings import load_settings
from .state import StateStore


def _enable_dpi_awareness() -> None:
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 - 古い Windows では無視
        pass


def main() -> None:
    from .gui import EvalMemoApp, show_settings_errors

    _enable_dpi_awareness()
    root = tk.Tk()

    def report_exception(exc_type, exc, tb):
        log_error("予期しないエラーが発生しました", exc.with_traceback(tb))
        messagebox.showerror("エラー", f"予期しないエラーが発生しました。\n\n{exc}\n\n"
                             f"詳細は {paths.error_log_path()} を確認してください。", parent=root)

    root.report_callback_exception = report_exception

    settings_file = paths.settings_path()
    loaded = load_settings(settings_file)
    if loaded.create_error is not None:
        log_error(f"既定の settings.json を作成できませんでした: {settings_file}", loaded.create_error)
    if loaded.errors:
        log_error("settings.json の検証エラー（既定値で起動）:\n" + "\n".join(loaded.errors))

    state = StateStore(paths.state_path())
    state_error = state.load()
    if state_error:
        log_error(state_error)

    EvalMemoApp(root, loaded.settings, settings_file, state)
    if loaded.errors:
        root.after(200, lambda: show_settings_errors(root, loaded.errors, reload=False))
    root.mainloop()
