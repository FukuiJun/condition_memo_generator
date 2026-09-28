"""状態ファイル（%APPDATA%\\EvalMemo\\state.json）（仕様書 5.2, F-02, F-09）

形式:
    {
      "values":  {id: 前回値, ...},        # remember が true の項目
      "history": {id: [新しい順, ...], ...},  # history が true の combo の入力履歴
      "last_folder": "前回の保存先フォルダ"
    }

設定から消えた id のデータは読み込み時に無視するが、書き込み時に削除はしない。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .settings import FieldDef, Settings
from .values import coerce_raw

HISTORY_LIMIT = 10


def update_history(history: list[str], value: str, limit: int = HISTORY_LIMIT) -> list[str]:
    """value を先頭に追加した履歴（重複なし・新しい順・最大 limit 件）"""
    value = value.strip()
    if not value:
        return list(history)[:limit]
    return ([value] + [h for h in history if h != value])[:limit]


def combo_candidates(field: FieldDef, history: list[str]) -> list[str]:
    """combo の候補。history が true なら入力履歴（最新10件）を options の前に置く。"""
    head = list(history)[:HISTORY_LIMIT] if field.history else []
    return head + [o for o in field.options if o not in head]


class StateStore:
    def __init__(self, path: Path):
        self.path = path
        self.data: dict = {}

    def load(self) -> str | None:
        """読み込む。無い・壊れている場合は空の状態にして理由を返す（エラーにはしない）。"""
        self.data = {}
        try:
            text = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except (OSError, UnicodeDecodeError) as e:
            return f"state.json を読み込めません: {e}"
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            return f"state.json が壊れています: {e}"
        if not isinstance(data, dict):
            return "state.json が壊れています: オブジェクトではありません"
        self.data = data
        return None

    def _section(self, key: str) -> dict:
        section = self.data.get(key)
        return section if isinstance(section, dict) else {}

    def remembered(self, field: FieldDef) -> object | None:
        """remember の項目の前回値（現在の項目定義に合わせたもの）。無ければ None。"""
        if not field.remember or field.type == "datetime":
            return None
        values = self._section("values")
        if field.id not in values:
            return None
        return coerce_raw(field, values[field.id])

    def history(self, field_id: str) -> list[str]:
        items = self._section("history").get(field_id)
        if not isinstance(items, list):
            return []
        return [h for h in items if isinstance(h, str)][:HISTORY_LIMIT]

    @property
    def last_folder(self) -> str:
        v = self.data.get("last_folder")
        return v if isinstance(v, str) else ""

    def update_after_save(
        self,
        settings: Settings,
        raw_values: dict[str, object],
        out_values: dict[str, str],
        folder: str,
    ) -> None:
        values = dict(self._section("values"))
        history = dict(self._section("history"))
        for f in settings.fields:
            if f.remember and f.type != "datetime":
                values[f.id] = raw_values.get(f.id)
            if f.type == "combo" and f.history:
                history[f.id] = update_history(self.history(f.id), out_values.get(f.id, ""))
        self.data["values"] = values
        self.data["history"] = history
        self.data["last_folder"] = folder

    def save(self) -> None:
        """書き込む。失敗時は OSError。"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        with open(tmp, "w", encoding="utf-8", newline="\n") as fp:
            json.dump(self.data, fp, ensure_ascii=False, indent=2)
            fp.write("\n")
        os.replace(tmp, self.path)
