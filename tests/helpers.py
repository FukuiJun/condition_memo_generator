"""テスト共通：src をインポートパスに加え、既定の設定と仕様書の例の入力を用意する"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from memogenerator.settings import DEFAULT_SETTINGS_TEXT, default_settings, parse_settings  # noqa: E402

DEFAULT = default_settings()

# select 型（選択のみ＋「その他」）の項目。既定の設定には無いので、select のテストで追加して使う
METHOD_FIELD = {"id": "method", "label": "充電・放電方式", "type": "select", "required": True,
                "options": ["USB充電", "ワイヤレス充電", "連続測定モード"],
                "other_option": "その他", "remember": True}


def example_raw(**overrides):
    """仕様書 5.2 の例と同じ入力（画面から集めた raw 値）"""
    raw = {
        "date": "2026-09-28",
        "program": "ver1.2.0",
        "board": "Rev.B",
        "board_state": {"筐体": False, "線出し": True, "シャント抵抗": True},
        "test_summary": "USB充電 定電流1A",
        "datafile": r"C:\eval\20260928\20260928_charge_test.csv",
        "note": "室温25℃\n負荷500mA",
        "measurer": "山田",
    }
    raw.update(overrides)
    return raw


def default_data():
    return json.loads(DEFAULT_SETTINGS_TEXT)


def _insert_before(data, before_id, field):
    idx = [f["id"] for f in data["fields"]].index(before_id)
    data["fields"].insert(idx, field)
    return data


def settings_with_temp_field():
    """AC-16：備考の前に「周囲温度」を追加した設定"""
    data = _insert_before(default_data(), "note", {"id": "temp", "label": "周囲温度", "type": "text"})
    return parse_settings(json.dumps(data, ensure_ascii=False))


def settings_with_select_text() -> str:
    """既定の設定のデータファイルの前に select 項目（充電・放電方式）を追加した settings.json の内容"""
    data = _insert_before(default_data(), "datafile", dict(METHOD_FIELD))
    return json.dumps(data, ensure_ascii=False)


def settings_with_select():
    return parse_settings(settings_with_select_text())


def settings_with_time():
    """日付の項目を時刻付き（with_time: true）にした設定"""
    data = default_data()
    data["fields"][0]["with_time"] = True
    return parse_settings(json.dumps(data, ensure_ascii=False))
