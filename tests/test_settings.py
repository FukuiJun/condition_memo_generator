import json
import tempfile
import unittest
from pathlib import Path

from .helpers import ROOT

from memogenerator.settings import (
    DEFAULT_SETTINGS_TEXT,
    SettingsError,
    load_settings,
    parse_settings,
)


def base_data():
    return json.loads(DEFAULT_SETTINGS_TEXT)


def errors_of(data) -> list[str]:
    text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    try:
        parse_settings(text)
    except SettingsError as e:
        return e.errors
    raise AssertionError("SettingsError が発生しませんでした")


class DefaultSettingsTest(unittest.TestCase):
    def test_default_is_valid(self):
        s = parse_settings(DEFAULT_SETTINGS_TEXT)
        self.assertEqual(s.history_csv_name, "条件履歴")
        self.assertEqual([f.label for f in s.fields],
                         ["日時", "プログラム", "基板", "基板状態", "充電・放電方式", "データファイル", "備考", "測定者"])
        self.assertEqual(s.field("board").options, ("Rev.A", "Rev.B"))
        self.assertEqual(s.field("method").other_option, "その他")
        self.assertEqual(s.field("note").rows, 5)
        self.assertEqual(s.field("measurer").blank_lines_before, 2)
        self.assertFalse(s.field("note").remember)

    def test_bundled_settings_json_is_default(self):
        bundled = (ROOT / "settings.json").read_text(encoding="utf-8")
        self.assertEqual(bundled, DEFAULT_SETTINGS_TEXT)


class ValidationTest(unittest.TestCase):
    # ---- AC-18
    def test_duplicate_id(self):
        data = base_data()
        data["fields"][2]["id"] = "program"
        errs = errors_of(data)
        self.assertTrue(any("3番目の項目" in e and "id「program」" in e and "重複" in e for e in errs), errs)

    def test_two_datetimes(self):
        data = base_data()
        data["fields"].append({"id": "dt2", "label": "日時2", "type": "datetime"})
        errs = errors_of(data)
        self.assertTrue(any("datetime 型" in e and "2 件" in e for e in errs), errs)

    def test_unknown_type(self):
        data = base_data()
        data["fields"][1]["type"] = "number"
        errs = errors_of(data)
        self.assertTrue(any("2番目の項目（id: program）" in e and "未知の種類" in e for e in errs), errs)

    # ---- その他の検証ルール
    def test_not_json(self):
        errs = errors_of('{"fields": [}')
        self.assertIn("JSON として読み込めません", errs[0])

    def test_no_fields(self):
        self.assertTrue(any("1件も" in e for e in errors_of({"fields": []})))
        self.assertTrue(any("fields がありません" in e for e in errors_of({})))

    def test_no_datetime(self):
        data = base_data()
        data["fields"] = [f for f in data["fields"] if f["type"] != "datetime"]
        self.assertTrue(any("datetime 型" in e and "0 件" in e for e in errors_of(data)))

    def test_two_datafiles(self):
        data = base_data()
        data["fields"].append({"id": "df2", "label": "データ2", "type": "datafile"})
        self.assertTrue(any("datafile 型" in e for e in errors_of(data)))

    def test_duplicate_label(self):
        data = base_data()
        data["fields"].append({"id": "x", "label": "備考", "type": "text"})
        self.assertTrue(any("label「備考」" in e and "重複" in e for e in errors_of(data)))

    def test_unknown_attribute(self):
        data = base_data()
        data["fields"][6]["options"] = ["a"]  # multiline に options は無い
        data["fields"][0]["colour"] = "red"
        errs = errors_of(data)
        self.assertTrue(any("7番目の項目" in e and "未知の属性 options" in e for e in errs), errs)
        self.assertTrue(any("1番目の項目" in e and "未知の属性 colour" in e for e in errs), errs)

    def test_unknown_top_level_attribute(self):
        data = base_data()
        data["extra"] = 1
        self.assertTrue(any("未知の属性 extra" in e for e in errors_of(data)))

    def test_missing_required_attrs(self):
        data = base_data()
        data["fields"].append({"type": "text"})
        errs = errors_of(data)
        self.assertTrue(any("9番目の項目" in e and "id" in e for e in errs))
        self.assertTrue(any("9番目の項目" in e and "label" in e for e in errs))

    def test_bad_id_chars(self):
        data = base_data()
        data["fields"][1]["id"] = "プログラム"
        self.assertTrue(any("半角英数字" in e for e in errors_of(data)))

    def test_attribute_types(self):
        cases = [
            (1, "required", "yes"),
            (1, "remember", 1),
            (1, "options", "Rev.A"),
            (1, "options", [1, 2]),
            (1, "history", "true"),
            (6, "rows", "5"),
            (7, "blank_lines_before", 6),
            (7, "blank_lines_before", True),
            (3, "items", []),
            (3, "separator", 1),
            (4, "other_option", 5),
        ]
        for idx, key, value in cases:
            with self.subTest(key=key, value=value):
                data = base_data()
                data["fields"][idx][key] = value
                errs = errors_of(data)
                self.assertTrue(any(f"{idx + 1}番目の項目" in e and key in e for e in errs), errs)

    def test_required_not_allowed_on_checkgroup(self):
        data = base_data()
        data["fields"][3]["required"] = False
        self.assertTrue(any("checkgroup には required" in e for e in errors_of(data)))

    def test_select_needs_options(self):
        data = base_data()
        del data["fields"][4]["options"]
        self.assertTrue(any("select には options" in e for e in errors_of(data)))

    def test_history_csv_name(self):
        for bad in ["", "a/b", "条件:履歴", "CON", "abc.", 3]:
            with self.subTest(bad=bad):
                data = base_data()
                data["history_csv_name"] = bad
                self.assertTrue(any("history_csv_name" in e for e in errors_of(data)))
        data = base_data()
        del data["history_csv_name"]
        self.assertEqual(parse_settings(json.dumps(data)).history_csv_name, "条件履歴")

    def test_reserved_memo_label(self):
        data = base_data()
        data["fields"].append({"id": "m", "label": "メモファイル", "type": "text"})
        self.assertTrue(any("予約" in e for e in errors_of(data)))

    def test_ac16_added_field_is_valid(self):
        data = base_data()
        data["fields"].insert(6, {"id": "temp", "label": "周囲温度", "type": "text"})
        s = parse_settings(json.dumps(data, ensure_ascii=False))
        self.assertEqual(s.fields[6].label, "周囲温度")


class LoadSettingsTest(unittest.TestCase):
    def test_missing_file_is_created_with_default(self):  # AC-01（ファイル作成部分）
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "settings.json"
            result = load_settings(path)
            self.assertTrue(result.created)
            self.assertEqual(result.errors, [])
            self.assertEqual(len(result.settings.fields), 8)
            self.assertEqual(path.read_text(encoding="utf-8"), DEFAULT_SETTINGS_TEXT)

    def test_invalid_file_falls_back_and_is_not_overwritten(self):  # AC-18（起動時の動作）
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "settings.json"
            data = base_data()
            data["fields"][1]["type"] = "number"
            text = json.dumps(data, ensure_ascii=False)
            path.write_text(text, encoding="utf-8")
            result = load_settings(path)
            self.assertFalse(result.created)
            self.assertTrue(result.errors)
            self.assertEqual(len(result.settings.fields), 8)
            self.assertEqual(path.read_text(encoding="utf-8"), text)

    def test_bom_is_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "settings.json"
            path.write_bytes(b"\xef\xbb\xbf" + DEFAULT_SETTINGS_TEXT.encode("utf-8"))
            self.assertEqual(load_settings(path).errors, [])


if __name__ == "__main__":
    unittest.main()
