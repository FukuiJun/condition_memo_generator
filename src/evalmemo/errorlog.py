"""エラーログ（%APPDATA%\\EvalMemo\\error.log）"""

from __future__ import annotations

import traceback
from datetime import datetime
from pathlib import Path

from . import paths


def log_error(message: str, exc: BaseException | None = None, path: Path | None = None) -> None:
    """日時と内容を追記する（UTF-8 / CRLF）。ログ自体の失敗は無視する。"""
    try:
        path = path or paths.error_log_path()
        text = f"{datetime.now():%Y-%m-%d %H:%M:%S} {message}"
        if exc is not None:
            detail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)).rstrip()
            text += "\n" + detail
        text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n") + "\r\n"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "ab") as fp:
            fp.write(text.encode("utf-8"))
    except Exception:  # noqa: BLE001 - ログの失敗で本処理を止めない
        pass
