"""設定ファイル（settings.json）の定義・読み込み・検証（仕様書 5.2, F-01）"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

DEFAULT_HISTORY_CSV_NAME = "条件履歴"

# 仕様書 5.2 の既定値。settings.json が無いときはこの内容をそのまま書き出す。
DEFAULT_SETTINGS_TEXT = """\
{
  "history_csv_name": "条件履歴",
  "fields": [
    {"id": "date", "label": "日付", "type": "datetime", "required": true},
    {"id": "time", "label": "測定時刻", "type": "time"},
    {"id": "program", "label": "プログラム", "type": "combo",
     "options": [], "history": true, "remember": true},
    {"id": "board", "label": "基板", "type": "combo", "required": true,
     "options": ["Rev.A", "Rev.B"], "history": true, "remember": true},
    {"id": "board_state", "label": "基板状態", "type": "checkgroup",
     "items": ["筐体", "線出し", "シャント抵抗"],
     "on_text": "有", "off_text": "無", "separator": "、", "remember": true},
    {"id": "battery", "label": "バッテリ", "type": "combo",
     "options": [], "history": true, "remember": true},
    {"id": "test_summary", "label": "試験概要", "type": "combo", "required": true,
     "options": [], "history": true, "remember": true},
    {"id": "datafile", "label": "データファイル", "type": "datafile"},
    {"id": "note", "label": "備考", "type": "multiline", "rows": 5},
    {"id": "measurer", "label": "測定者", "type": "combo", "required": true,
     "options": [], "history": true, "remember": true, "blank_lines_before": 2}
  ]
}
"""

# CSV の最終列の見出し。項目の label には使えない。
MEMO_COLUMN_LABEL = "メモファイル"

FIELD_TYPES = ("text", "multiline", "combo", "select", "checkgroup", "datetime", "time", "datafile")

COMMON_ATTRS = ("id", "label", "type", "required", "remember", "blank_lines_before")

TYPE_ATTRS: dict[str, tuple[str, ...]] = {
    "text": (),
    "multiline": ("rows",),
    "combo": ("options", "history"),
    "select": ("options", "other_option"),
    "checkgroup": ("items", "on_text", "off_text", "separator"),
    "datetime": ("with_time",),
    "time": (),
    "datafile": (),
}

TOP_LEVEL_ATTRS = ("history_csv_name", "fields")

_ID_RE = re.compile(r"^[A-Za-z0-9_]+$")
_INVALID_FILENAME_CHARS = set('<>:"/\\|?*')
_RESERVED_FILENAMES = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {
    f"LPT{i}" for i in range(1, 10)
}


@dataclass(frozen=True)
class FieldDef:
    """settings.json の fields の1要素"""

    id: str
    label: str
    type: str
    required: bool = False
    remember: bool = False
    blank_lines_before: int = 0
    # multiline
    rows: int = 5
    # combo / select
    options: tuple[str, ...] = ()
    history: bool = False
    other_option: str | None = None
    # datetime（false: YYYY-MM-DD の日付のみ / true: YYYY-MM-DD HH:MM）
    with_time: bool = False
    # checkgroup
    items: tuple[str, ...] = ()
    on_text: str = "有"
    off_text: str = "無"
    separator: str = "、"


@dataclass(frozen=True)
class Settings:
    history_csv_name: str
    fields: tuple[FieldDef, ...]

    def field(self, field_id: str) -> FieldDef:
        for f in self.fields:
            if f.id == field_id:
                return f
        raise KeyError(field_id)

    def fields_of_type(self, field_type: str) -> list[FieldDef]:
        return [f for f in self.fields if f.type == field_type]

    @property
    def datetime_field(self) -> FieldDef:
        return self.fields_of_type("datetime")[0]

    @property
    def datafile_field(self) -> FieldDef | None:
        found = self.fields_of_type("datafile")
        return found[0] if found else None


class SettingsError(Exception):
    """設定の検証エラー。errors に違反内容を列挙する。"""

    def __init__(self, errors: list[str]):
        super().__init__("\n".join(errors))
        self.errors = errors


def _is_bool(v: object) -> bool:
    return isinstance(v, bool)


def _is_int(v: object) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _is_str_list(v: object) -> bool:
    return isinstance(v, list) and all(isinstance(x, str) for x in v)


def filename_problem(name: object) -> str | None:
    """ファイル名（拡張子なし）として使えない理由。使えるなら None。"""
    if not isinstance(name, str):
        return "文字列で指定してください"
    if name.strip() == "":
        return "空にはできません"
    bad = sorted({c for c in name if c in _INVALID_FILENAME_CHARS or ord(c) < 32})
    if bad:
        shown = " ".join(repr(c) if ord(c) < 32 else c for c in bad)
        return f"ファイル名に使えない文字が含まれています（{shown}）"
    if name.endswith((" ", ".")):
        return "末尾を空白やピリオドにはできません"
    if name.split(".")[0].strip().upper() in _RESERVED_FILENAMES:
        return "Windows の予約名はファイル名に使えません"
    if len(name) > 200:
        return "長すぎます（200文字まで）"
    return None


def _field_prefix(index: int, raw: object) -> str:
    if isinstance(raw, dict) and isinstance(raw.get("id"), str) and raw.get("id"):
        return f"{index}番目の項目（id: {raw['id']}）"
    return f"{index}番目の項目"


def _validate_field(index: int, raw: object, errors: list[str]) -> FieldDef | None:
    prefix = _field_prefix(index, raw)

    def err(msg: str) -> None:
        errors.append(f"{prefix}: {msg}")

    if not isinstance(raw, dict):
        err("{ } で囲んだオブジェクトで指定してください")
        return None

    n_before = len(errors)

    for key in ("id", "label", "type"):
        if key not in raw:
            err(f"必須の属性 {key} がありません")

    fid = raw.get("id")
    if "id" in raw:
        if not isinstance(fid, str) or not _ID_RE.match(fid):
            err("id は半角英数字と _ だけの文字列で指定してください")

    label = raw.get("label")
    if "label" in raw:
        if not isinstance(label, str) or label.strip() == "":
            err("label は空でない文字列で指定してください")
        elif "\n" in label or "\r" in label:
            err("label に改行は使えません")
        elif label == MEMO_COLUMN_LABEL:
            err(f"label「{MEMO_COLUMN_LABEL}」は CSV の列名として予約されているため使えません")

    ftype = raw.get("type")
    type_known = isinstance(ftype, str) and ftype in FIELD_TYPES
    if "type" in raw and not type_known:
        err(f"type {json.dumps(ftype, ensure_ascii=False)} は未知の種類です"
            f"（使える種類: {', '.join(FIELD_TYPES)}）")

    if type_known:
        allowed = set(COMMON_ATTRS) | set(TYPE_ATTRS[ftype])
        for key in raw:
            if key not in allowed:
                err(f"未知の属性 {key} があります（type {ftype} では使えません）")

    # 共通属性
    for key in ("required", "remember"):
        if key in raw and not _is_bool(raw[key]):
            err(f"{key} は true または false で指定してください")
    if ftype == "checkgroup" and "required" in raw:
        err("checkgroup には required を指定できません")
    if "blank_lines_before" in raw:
        v = raw["blank_lines_before"]
        if not _is_int(v) or not 0 <= v <= 5:
            err("blank_lines_before は 0〜5 の整数で指定してください")

    # type 固有の属性
    if ftype == "multiline" and "rows" in raw:
        v = raw["rows"]
        if not _is_int(v) or not 1 <= v <= 50:
            err("rows は 1〜50 の整数で指定してください")
    if ftype in ("combo", "select"):
        if ftype == "select" and "options" not in raw:
            err("select には options が必要です")
        if "options" in raw and not _is_str_list(raw["options"]):
            err("options は文字列の配列で指定してください")
    if ftype == "combo" and "history" in raw and not _is_bool(raw["history"]):
        err("history は true または false で指定してください")
    if ftype == "select" and "other_option" in raw:
        v = raw["other_option"]
        if not isinstance(v, str) or v.strip() == "":
            err("other_option は空でない文字列で指定してください")
        elif _is_str_list(raw.get("options")) and v in raw["options"]:
            err(f"other_option「{v}」が options にも含まれています")
    if ftype == "datetime" and "with_time" in raw and not _is_bool(raw["with_time"]):
        err("with_time は true または false で指定してください")
    if ftype == "checkgroup":
        if "items" not in raw:
            err("checkgroup には items が必要です")
        elif not _is_str_list(raw["items"]) or len(raw["items"]) == 0:
            err("items は1件以上の文字列の配列で指定してください")
        for key in ("on_text", "off_text", "separator"):
            if key in raw and not isinstance(raw[key], str):
                err(f"{key} は文字列で指定してください")

    if len(errors) != n_before:
        return None

    kwargs: dict = {"id": fid, "label": label, "type": ftype}
    for key in ("required", "remember", "blank_lines_before", "rows", "history",
                "other_option", "with_time", "on_text", "off_text", "separator"):
        if key in raw:
            kwargs[key] = raw[key]
    for key in ("options", "items"):
        if key in raw:
            kwargs[key] = tuple(raw[key])
    return FieldDef(**kwargs)


def validate_settings_data(data: object) -> Settings:
    """JSON を読み込んだ結果を検証して Settings にする。不正なら SettingsError。"""
    errors: list[str] = []
    if not isinstance(data, dict):
        raise SettingsError(["設定全体を { } で囲んだオブジェクトにしてください"])

    for key in data:
        if key not in TOP_LEVEL_ATTRS:
            errors.append(f"未知の属性 {key} があります（使える属性: {', '.join(TOP_LEVEL_ATTRS)}）")

    csv_name = data.get("history_csv_name", DEFAULT_HISTORY_CSV_NAME)
    problem = filename_problem(csv_name)
    if problem:
        errors.append(f"history_csv_name: {problem}")

    raw_fields = data.get("fields")
    fields: list[FieldDef] = []
    if "fields" not in data:
        errors.append("fields がありません")
    elif not isinstance(raw_fields, list):
        errors.append("fields は配列で指定してください")
    elif len(raw_fields) == 0:
        errors.append("fields に項目が1件もありません")
    else:
        for i, raw in enumerate(raw_fields, start=1):
            f = _validate_field(i, raw, errors)
            if f is not None:
                fields.append(f)

        # 重複と件数のチェックは、読めた項目を対象に行う
        seen_ids: dict[str, int] = {}
        seen_labels: dict[str, int] = {}
        for i, raw in enumerate(raw_fields, start=1):
            if not isinstance(raw, dict):
                continue
            fid, label = raw.get("id"), raw.get("label")
            if isinstance(fid, str):
                if fid in seen_ids:
                    errors.append(f"{i}番目の項目: id「{fid}」が {seen_ids[fid]}番目の項目と重複しています")
                else:
                    seen_ids[fid] = i
            if isinstance(label, str):
                if label in seen_labels:
                    errors.append(
                        f"{i}番目の項目: label「{label}」が {seen_labels[label]}番目の項目と重複しています")
                else:
                    seen_labels[label] = i

        types = [raw.get("type") for raw in raw_fields if isinstance(raw, dict)]
        n_dt = types.count("datetime")
        n_df = types.count("datafile")
        if n_dt != 1:
            errors.append(f"datetime 型の項目はちょうど1件必要です（現在 {n_dt} 件）")
        if n_df > 1:
            errors.append(f"datafile 型の項目は0件または1件にしてください（現在 {n_df} 件）")

    if errors:
        raise SettingsError(errors)
    return Settings(history_csv_name=csv_name, fields=tuple(fields))


def parse_settings(text: str) -> Settings:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise SettingsError([f"JSON として読み込めません（{e.lineno}行 {e.colno}列: {e.msg}）"]) from e
    return validate_settings_data(data)


def default_settings() -> Settings:
    return parse_settings(DEFAULT_SETTINGS_TEXT)


def read_settings_file(path: Path) -> Settings:
    """settings.json を読み込んで検証する。不正・読めない場合は SettingsError。"""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError as e:
        raise SettingsError([f"{path.name} が見つかりません"]) from e
    except UnicodeDecodeError as e:
        raise SettingsError([f"{path.name} を UTF-8 として読み込めません"]) from e
    except OSError as e:
        raise SettingsError([f"{path.name} を読み込めません（{e.strerror or e}）"]) from e
    return parse_settings(text)


def write_default_settings(path: Path) -> None:
    with open(path, "x", encoding="utf-8", newline="\n") as fp:
        fp.write(DEFAULT_SETTINGS_TEXT)


@dataclass
class LoadResult:
    settings: Settings
    errors: list[str]  # 検証エラー（あれば既定値で起動する）
    created: bool  # 既定値の settings.json を新規作成したか
    create_error: OSError | None = None  # 作成しようとして失敗した場合


def load_settings(path: Path) -> LoadResult:
    """起動時の読み込み（F-01）。

    - 無い → 既定値で作成して既定値を使う
    - 検証エラー → 既定値を使う（ファイルは上書きしない）
    """
    if not path.exists():
        try:
            write_default_settings(path)
        except OSError as e:
            return LoadResult(default_settings(), [], created=False, create_error=e)
        return LoadResult(default_settings(), [], created=True)
    try:
        return LoadResult(read_settings_file(path), [], created=False)
    except SettingsError as e:
        return LoadResult(default_settings(), e.errors, created=False)
