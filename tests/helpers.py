"""テスト共通：src をインポートパスに加え、既定の設定と仕様書の例の入力を用意する"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from evalmemo.settings import default_settings, parse_settings  # noqa: E402

DEFAULT = default_settings()


def example_raw(**overrides):
    """仕様書 5.2 の例と同じ入力（画面から集めた raw 値）"""
    raw = {
        "datetime": "2026-09-28 14:30",
        "program": "ver1.2.0",
        "board": "Rev.B",
        "board_state": {"外枠": False, "線出し": True, "シャント抵抗": True},
        "method": {"choice": "USB充電", "other": ""},
        "datafile": r"C:\eval\20260928\20260928_charge_test.csv",
        "note": "室温25℃\n負荷500mA",
        "measurer": "山田",
    }
    raw.update(overrides)
    return raw


def settings_with_temp_field():
    """AC-16：備考の前に「周囲温度」を追加した設定"""
    import json

    from evalmemo.settings import DEFAULT_SETTINGS_TEXT

    data = json.loads(DEFAULT_SETTINGS_TEXT)
    idx = [f["id"] for f in data["fields"]].index("note")
    data["fields"].insert(idx, {"id": "temp", "label": "周囲温度", "type": "text"})
    return parse_settings(json.dumps(data, ensure_ascii=False))
