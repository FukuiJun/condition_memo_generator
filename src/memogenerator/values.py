"""入力値の表現・出力値への変換・入力チェック（仕様書 5.2 type 表, F-03, F-06）

画面から集めた入力値（raw）は項目の id をキーにした辞書で扱う。type ごとの形式:

- text / multiline / combo / datetime / time: 文字列
- datafile: 選択したファイルのフルパス（未選択は ""）
- select: {"choice": 選択中の候補（未選択は ""）, "other": other_option 用テキスト}
- checkgroup: {item 名: チェック状態(bool)}
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path, PureWindowsPath

from .settings import FieldDef, Settings

DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M"
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")
TIME_PATTERN = "HH:MM"


def datetime_pattern(with_time: bool) -> str:
    """画面・エラー表示用の形式（YYYY-MM-DD または YYYY-MM-DD HH:MM）"""
    return "YYYY-MM-DD HH:MM" if with_time else "YYYY-MM-DD"


def now_text(with_time: bool = False, now: datetime | None = None) -> str:
    """今日の日付（with_time なら現在時刻まで）"""
    return (now or datetime.now()).strftime(DATETIME_FORMAT if with_time else DATE_FORMAT)


def parse_datetime_text(text: str, with_time: bool = False) -> datetime | None:
    """形式（`YYYY-MM-DD`、with_time なら `YYYY-MM-DD HH:MM`）に合う実在する日付なら datetime、
    そうでなければ None。"""
    text = text.strip()
    pattern, fmt = (_DATETIME_RE, DATETIME_FORMAT) if with_time else (_DATE_RE, DATE_FORMAT)
    if not pattern.match(text):
        return None
    try:
        return datetime.strptime(text, fmt)
    except ValueError:
        return None


def now_time_text(now: datetime | None = None) -> str:
    """現在時刻（HH:MM）"""
    return (now or datetime.now()).strftime("%H:%M")


def parse_time_text(text: str) -> str | None:
    """時刻（`HH:MM`、時は1桁も可）として正しければ `HH:MM` に整えた文字列、そうでなければ None。"""
    m = _TIME_RE.match(text.strip())
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2))
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def empty_raw(field: FieldDef) -> object:
    if field.type == "select":
        return {"choice": "", "other": ""}
    if field.type == "checkgroup":
        return {item: False for item in field.items}
    return ""


def coerce_raw(field: FieldDef, value: object) -> object | None:
    """保存されていた値（state.json・再読み込み前の画面）を現在の項目定義に合わせる。

    形式が合わず使えない場合は None。
    """
    if field.type == "select":
        if not isinstance(value, dict):
            return None
        choice = value.get("choice")
        other = value.get("other")
        other = other if isinstance(other, str) else ""
        if not isinstance(choice, str):
            choice = ""
        valid = set(field.options)
        if field.other_option is not None:
            valid.add(field.other_option)
        if choice not in valid:
            choice = ""  # 現在の options に無い → 未選択
        return {"choice": choice, "other": other}
    if field.type == "checkgroup":
        if not isinstance(value, dict):
            return None
        # item 名で対応付け、新しい item は未チェック
        return {item: value.get(item) is True for item in field.items}
    if not isinstance(value, str):
        return None
    return value


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def datafile_name(path_text: str) -> str:
    """データファイルのパスからファイル名だけを取り出す。"""
    path_text = path_text.strip()
    if not path_text:
        return ""
    # Windows 形式のパス区切り（\）も扱えるようにする
    return PureWindowsPath(path_text).name if "\\" in path_text else Path(path_text).name


def output_value(field: FieldDef, raw: object) -> str:
    """項目の出力値（.txt / .csv に書く文字列）"""
    coerced = coerce_raw(field, raw)
    if coerced is None:
        coerced = empty_raw(field)
    t = field.type
    if t == "select":
        choice = coerced["choice"]
        if field.other_option is not None and choice == field.other_option:
            return coerced["other"].strip()
        return choice
    if t == "checkgroup":
        return field.separator.join(
            item + (field.on_text if coerced[item] else field.off_text) for item in field.items
        )
    if t == "datafile":
        return datafile_name(coerced)
    if t == "multiline":
        # 末尾の空行・空白は落とす（先頭側や途中はそのまま）
        return _normalize_newlines(coerced).rstrip()
    # text / combo / datetime / time（1行）
    value = " ".join(_normalize_newlines(coerced).split("\n")).strip()
    if t == "time":
        return parse_time_text(value) or value  # 9:05 → 09:05（不正な値は入力チェックで弾く）
    return value


def output_values(settings: Settings, raw_values: dict[str, object]) -> dict[str, str]:
    return {f.id: output_value(f, raw_values.get(f.id)) for f in settings.fields}


def validate_input(
    settings: Settings,
    raw_values: dict[str, object],
    folder: str,
    want_csv: bool,
    want_txt: bool,
) -> list[str]:
    """保存前の入力チェック（F-06）。違反内容のリストを返す（空なら OK）。"""
    errors: list[str] = []
    for f in settings.fields:
        raw = raw_values.get(f.id)
        value = output_value(f, raw)
        if f.type == "datetime":
            if not value:
                errors.append(f"{f.label}：入力されていません")
            elif parse_datetime_text(value, f.with_time) is None:
                what = "日時" if f.with_time else "日付"
                errors.append(f"{f.label}：{datetime_pattern(f.with_time)} 形式で実在する{what}を"
                              f"入力してください（{value}）")
            continue
        if f.type == "time" and value and parse_time_text(value) is None:
            errors.append(f"{f.label}：{TIME_PATTERN} 形式の時刻を入力してください（{value}）")
            continue
        if not f.required or value:
            continue
        if f.type == "select":
            coerced = coerce_raw(f, raw) or empty_raw(f)
            if f.other_option is not None and coerced["choice"] == f.other_option:
                errors.append(f"{f.label}：「{f.other_option}」の内容が入力されていません")
                continue
            errors.append(f"{f.label}：選択されていません")
        elif f.type == "datafile":
            errors.append(f"{f.label}：選択されていません")
        else:
            errors.append(f"{f.label}：入力されていません")

    folder = folder.strip()
    if not folder:
        errors.append("保存先：フォルダが選択されていません")
    elif not Path(folder).is_dir():
        errors.append(f"保存先：フォルダが存在しません（{folder}）")

    if not want_csv and not want_txt:
        errors.append("出力形式を1つ以上選んでください")
    return errors
