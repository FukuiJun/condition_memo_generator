"""条件メモ（.txt）・条件履歴（.csv）の生成と保存（仕様書 5.2, F-07〜F-09）"""

from __future__ import annotations

import codecs
import csv
import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .settings import MEMO_COLUMN_LABEL, Settings
from .values import parse_datetime_text

TXT_SUFFIX = "_条件メモ"
DATAFILE_EMPTY_TEXT = "（なし）"
CRLF = "\r\n"
UTF8_BOM = codecs.BOM_UTF8


# ---------------------------------------------------------------- 条件メモ（.txt）

def build_txt(settings: Settings, values: dict[str, str]) -> bytes:
    """条件メモの内容（UTF-8 BOMなし / CRLF）"""
    lines: list[str] = []
    for f in settings.fields:
        value = values.get(f.id, "")
        if f.type == "datafile" and not value:
            value = DATAFILE_EMPTY_TEXT
        lines.extend([""] * f.blank_lines_before)
        # multiline の2行目以降はインデントせずそのまま続ける
        lines.extend(f"{f.label}：{value}".split("\n"))
    return (CRLF.join(lines) + CRLF).encode("utf-8")


def txt_base_name(settings: Settings, values: dict[str, str]) -> str:
    """条件メモのファイル名（拡張子・連番なし）"""
    df = settings.datafile_field
    datafile = values.get(df.id, "") if df else ""
    if datafile:
        return Path(datafile).stem + TXT_SUFFIX
    dt_field = settings.datetime_field
    dt = parse_datetime_text(values.get(dt_field.id, ""), dt_field.with_time)
    if dt is None:
        raise ValueError("日付が不正なため条件メモのファイル名を決められません")
    return dt.strftime("%Y%m%d_%H%M" if dt_field.with_time else "%Y%m%d") + TXT_SUFFIX


def numbered_name(base: str, n: int, ext: str) -> str:
    return f"{base}{ext}" if n == 1 else f"{base}_{n}{ext}"


def free_txt_path(folder: Path, base: str) -> Path:
    """同名ファイルがあれば _2, _3… を付けた、まだ存在しないパス"""
    n = 1
    while True:
        p = folder / numbered_name(base, n, ".txt")
        if not p.exists():
            return p
        n += 1


# ---------------------------------------------------------------- 条件履歴（.csv）

def csv_header(settings: Settings) -> list[str]:
    return [f.label for f in settings.fields] + [MEMO_COLUMN_LABEL]


def csv_row(settings: Settings, values: dict[str, str], memo_name: str) -> list[str]:
    return [values.get(f.id, "") for f in settings.fields] + [memo_name]


def encode_csv_rows(rows: list[list[str]]) -> str:
    """RFC 4180 形式（CRLF 区切り、必要な値だけダブルクォートで囲む）の文字列。

    値の中の改行も CRLF にそろえる。
    """
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator=CRLF, quoting=csv.QUOTE_MINIMAL)
    for row in rows:
        writer.writerow([v.replace("\r\n", "\n").replace("\r", "\n").replace("\n", CRLF) for v in row])
    return buf.getvalue()


def csv_candidates(folder: Path, base: str) -> list[tuple[int, Path]]:
    """保存先フォルダにある <base>.csv, <base>_2.csv, … を番号順に返す"""
    pattern = re.compile(rf"^{re.escape(base)}(?:_([1-9][0-9]*))?\.csv$", re.IGNORECASE)
    found: dict[int, Path] = {}
    for p in folder.iterdir():
        m = pattern.match(p.name)
        if not m or not p.is_file():
            continue
        n = int(m.group(1)) if m.group(1) else 1
        if n == 1 and m.group(1):
            continue  # "<base>_1.csv" は対象外
        found.setdefault(n, p)
    return sorted(found.items())


def read_csv_header(path: Path) -> list[str] | None:
    """CSV の1行目。空ファイルは []、読めない（文字コード不正など）場合は None。

    PermissionError（他のアプリがロック中）は呼び出し元に伝える。
    """
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as fp:
            reader = csv.reader(fp)
            return next(reader, [])
    except PermissionError:
        raise
    except (UnicodeDecodeError, csv.Error, OSError):
        return None


@dataclass
class CsvPlan:
    path: Path
    is_new: bool  # 新規作成するか（False なら追記）
    needs_confirm: bool  # 項目構成が変わったための新規作成（確認が必要）


def plan_csv(folder: Path, settings: Settings) -> CsvPlan:
    """追記・新規作成する CSV を決める（5.2「保存するファイルの決定」）"""
    base = settings.history_csv_name
    header = csv_header(settings)
    candidates = csv_candidates(folder, base)
    for _, path in candidates:
        existing = read_csv_header(path)
        if existing == header or existing == []:
            return CsvPlan(path, is_new=False, needs_confirm=False)
    if not candidates:
        return CsvPlan(folder / numbered_name(base, 1, ".csv"), is_new=True, needs_confirm=False)
    n = max(n for n, _ in candidates) + 1
    return CsvPlan(folder / numbered_name(base, n, ".csv"), is_new=True, needs_confirm=True)


def write_csv(plan: CsvPlan, settings: Settings, values: dict[str, str], memo_name: str) -> None:
    """CSV に1行書き込む。途中で失敗した場合は書き込み前の状態に戻してから例外を送出する。"""
    row = csv_row(settings, values, memo_name)
    if plan.is_new:
        data = UTF8_BOM + encode_csv_rows([csv_header(settings), row]).encode("utf-8")
        with open(plan.path, "xb") as fp:
            try:
                fp.write(data)
                fp.flush()
            except BaseException:
                fp.close()
                _remove_quietly(plan.path)
                raise
        return

    with open(plan.path, "r+b") as fp:
        fp.seek(0, io.SEEK_END)
        original_size = fp.tell()
        prefix = b""
        if original_size == 0:
            # 空ファイル → ヘッダから書く
            prefix = UTF8_BOM + encode_csv_rows([csv_header(settings)]).encode("utf-8")
        else:
            fp.seek(original_size - 1)
            if fp.read(1) not in (b"\n", b"\r"):
                prefix = CRLF.encode("ascii")  # 最終行が改行で終わっていない
            fp.seek(0, io.SEEK_END)
        try:
            fp.write(prefix + encode_csv_rows([row]).encode("utf-8"))
            fp.flush()
        except BaseException:
            try:
                fp.truncate(original_size)
            except OSError:
                pass
            raise


# ---------------------------------------------------------------- 保存（F-09）

class SaveCancelled(Exception):
    """利用者がキャンセルした（何も保存されていない）"""


class SaveError(Exception):
    """保存に失敗した（何も保存されていない）"""

    def __init__(self, message: str, cause: BaseException | None = None):
        super().__init__(message)
        self.message = message
        self.cause = cause


def _remove_quietly(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


def _describe_os_error(e: OSError) -> str:
    return e.strerror or str(e)


def save_outputs(
    settings: Settings,
    values: dict[str, str],
    folder: Path,
    want_txt: bool,
    want_csv: bool,
    confirm_new_csv: Callable[[str], bool],
    retry_locked: Callable[[str], bool],
) -> list[str]:
    """条件メモ・条件履歴を出力し、出力したファイル名のリストを返す。

    - confirm_new_csv(ファイル名): 項目構成が変わり新しい CSV を作るときの確認。False でキャンセル
    - retry_locked(ファイル名): CSV が開かれていて書き込めないときの再試行確認。False でキャンセル

    失敗・キャンセル時は、この呼び出しで作ったファイルを削除して
    SaveError / SaveCancelled を送出する（何も保存されなかった状態にする）。
    """
    if not want_txt and not want_csv:
        raise ValueError("出力形式が選ばれていません")

    created: list[Path] = []
    saved_names: list[str] = []
    try:
        plan: CsvPlan | None = None
        if want_csv:
            plan = _plan_with_retry(folder, settings, retry_locked, confirm_new_csv, confirmed=None)

        memo_name = ""
        if want_txt:
            txt_path = _write_txt(settings, values, folder, created)
            memo_name = txt_path.name
            saved_names.append(memo_name)

        if want_csv:
            assert plan is not None
            while True:
                try:
                    write_csv(plan, settings, values, memo_name)
                    break
                except PermissionError:
                    if not retry_locked(plan.path.name):
                        raise SaveCancelled() from None
                    # 開いている間に内容が変わったかもしれないので決め直す
                    plan = _plan_with_retry(folder, settings, retry_locked, confirm_new_csv,
                                            confirmed=plan.path)
                except FileExistsError:
                    plan = _plan_with_retry(folder, settings, retry_locked, confirm_new_csv,
                                            confirmed=plan.path)
                except OSError as e:
                    raise SaveError(
                        f"{plan.path.name} に書き込めませんでした（{_describe_os_error(e)}）", e) from e
            saved_names.append(plan.path.name)
    except BaseException:
        for p in created:
            _remove_quietly(p)
        raise
    return saved_names


def _plan_with_retry(
    folder: Path,
    settings: Settings,
    retry_locked: Callable[[str], bool],
    confirm_new_csv: Callable[[str], bool],
    confirmed: Path | None,
) -> CsvPlan:
    while True:
        try:
            plan = plan_csv(folder, settings)
        except PermissionError as e:
            locked = Path(e.filename) if e.filename else None
            if locked is None or not locked.is_file():
                raise SaveError(f"保存先フォルダを読み込めませんでした（{_describe_os_error(e)}）", e) from e
            if not retry_locked(locked.name):
                raise SaveCancelled() from None
            continue
        except OSError as e:
            raise SaveError(f"保存先フォルダを読み込めませんでした（{_describe_os_error(e)}）", e) from e
        if plan.needs_confirm and plan.path != confirmed:
            if not confirm_new_csv(plan.path.name):
                raise SaveCancelled()
        return plan


def _write_txt(settings: Settings, values: dict[str, str], folder: Path, created: list[Path]) -> Path:
    data = build_txt(settings, values)
    base = txt_base_name(settings, values)
    for _ in range(1000):
        path = free_txt_path(folder, base)
        try:
            fp = open(path, "xb")  # 既存ファイルは上書きしない
        except FileExistsError:
            continue
        except OSError as e:
            raise SaveError(f"{path.name} を作成できませんでした（{_describe_os_error(e)}）", e) from e
        created.append(path)
        try:
            with fp:
                fp.write(data)
        except OSError as e:
            raise SaveError(f"{path.name} に書き込めませんでした（{_describe_os_error(e)}）", e) from e
        return path
    raise SaveError(f"{base}.txt の保存先ファイル名を決められませんでした")
