"""ファイルの置き場所"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from . import APP_NAME


def app_dir() -> Path:
    """settings.json を置くフォルダ（exe と同じフォルダ）。

    開発時（python で直接実行）はリポジトリのルート。環境変数 EVALMEMO_APP_DIR で変更可。
    """
    override = os.environ.get("EVALMEMO_APP_DIR")
    if override:
        return Path(override)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    """state.json・error.log を置くフォルダ（%APPDATA%\\EvalMemo）。

    環境変数 EVALMEMO_DATA_DIR で変更可。
    """
    override = os.environ.get("EVALMEMO_DATA_DIR")
    if override:
        return Path(override)
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / APP_NAME
    return Path.home() / f".{APP_NAME.lower()}"


def settings_path() -> Path:
    return app_dir() / "settings.json"


def state_path() -> Path:
    return data_dir() / "state.json"


def error_log_path() -> Path:
    return data_dir() / "error.log"
