import tempfile
import unittest
from pathlib import Path
from unittest import mock

from .helpers import DEFAULT, example_raw, settings_with_temp_field

from evalmemo import output
from evalmemo.output import SaveCancelled, SaveError, build_txt, save_outputs, txt_base_name
from evalmemo.values import output_values, validate_input

BOM = b"\xef\xbb\xbf"

EXPECTED_TXT = (
    "日時：2026-09-28 14:30\r\n"
    "プログラム：ver1.2.0\r\n"
    "基板：Rev.B\r\n"
    "基板状態：外枠無、線出し有、シャント抵抗有\r\n"
    "充電・放電方式：USB充電\r\n"
    "データファイル：20260928_charge_test.csv\r\n"
    "備考：室温25℃\r\n"
    "負荷500mA\r\n"
    "\r\n"
    "\r\n"
    "測定者：山田\r\n"
).encode("utf-8")

EXPECTED_HEADER = "日時,プログラム,基板,基板状態,充電・放電方式,データファイル,備考,測定者,メモファイル\r\n"
EXPECTED_ROW = ('2026-09-28 14:30,ver1.2.0,Rev.B,外枠無、線出し有、シャント抵抗有,USB充電,'
                '20260928_charge_test.csv,"室温25℃\r\n負荷500mA",山田,20260928_charge_test_条件メモ.txt\r\n')


def never(_name):
    raise AssertionError("ダイアログは出ないはず")


class TempDirTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def save(self, raw=None, settings=DEFAULT, txt=False, csv=True, confirm=never, retry=never):
        values = output_values(settings, raw or example_raw())
        return save_outputs(settings, values, self.dir, want_txt=txt, want_csv=csv,
                            confirm_new_csv=confirm, retry_locked=retry)

    def files(self):
        return sorted(p.name for p in self.dir.iterdir())


class TxtTest(TempDirTest):
    def test_ac02_txt_matches_spec_example_byte_for_byte(self):
        values = output_values(DEFAULT, example_raw())
        self.assertEqual(build_txt(DEFAULT, values), EXPECTED_TXT)
        names = self.save(txt=True, csv=False)
        self.assertEqual(names, ["20260928_charge_test_条件メモ.txt"])
        self.assertEqual((self.dir / names[0]).read_bytes(), EXPECTED_TXT)
        self.assertFalse(EXPECTED_TXT.startswith(BOM))

    def test_empty_values(self):
        raw = example_raw(datafile="", note="", program="")
        text = build_txt(DEFAULT, output_values(DEFAULT, raw)).decode("utf-8")
        self.assertIn("\r\nプログラム：\r\n", text)
        self.assertIn("\r\nデータファイル：（なし）\r\n", text)
        self.assertIn("\r\n備考：\r\n", text)

    def test_ac10_file_name_rules(self):
        values = output_values(DEFAULT, example_raw(datafile=r"C:\eval\x\abc.csv"))
        self.assertEqual(txt_base_name(DEFAULT, values) + ".txt", "abc_条件メモ.txt")
        values = output_values(DEFAULT, example_raw(datafile="/home/u/eval/x/abc.csv"))
        self.assertEqual(txt_base_name(DEFAULT, values) + ".txt", "abc_条件メモ.txt")
        values = output_values(DEFAULT, example_raw(datafile=""))
        self.assertEqual(txt_base_name(DEFAULT, values) + ".txt", "20260928_1430_条件メモ.txt")

    def test_ac11_existing_txt_is_not_overwritten(self):
        existing = self.dir / "20260928_charge_test_条件メモ.txt"
        existing.write_bytes(b"old")
        self.assertEqual(self.save(txt=True, csv=False), ["20260928_charge_test_条件メモ_2.txt"])
        self.assertEqual(self.save(txt=True, csv=False), ["20260928_charge_test_条件メモ_3.txt"])
        self.assertEqual(existing.read_bytes(), b"old")
        self.assertEqual((self.dir / "20260928_charge_test_条件メモ_2.txt").read_bytes(), EXPECTED_TXT)

    def test_ac16_added_field_position(self):
        settings = settings_with_temp_field()
        raw = example_raw(temp="25℃")
        text = build_txt(settings, output_values(settings, raw)).decode("utf-8")
        self.assertIn("データファイル：20260928_charge_test.csv\r\n周囲温度：25℃\r\n備考：", text)


class CsvTest(TempDirTest):
    def test_ac03_csv_matches_spec_example(self):
        self.assertEqual(self.save(txt=True, csv=True),
                         ["20260928_charge_test_条件メモ.txt", "条件履歴.csv"])
        data = (self.dir / "条件履歴.csv").read_bytes()
        self.assertTrue(data.startswith(BOM))
        self.assertEqual(data, BOM + (EXPECTED_HEADER + EXPECTED_ROW).encode("utf-8"))

    def test_ac05_three_saves_append(self):
        for _ in range(3):
            self.assertEqual(self.save(), ["条件履歴.csv"])
        import csv

        with open(self.dir / "条件履歴.csv", encoding="utf-8-sig", newline="") as fp:
            rows = list(csv.reader(fp))
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0][-1], "メモファイル")
        self.assertEqual(rows[1][6], "室温25℃\r\n負荷500mA")
        self.assertEqual(self.files(), ["条件履歴.csv"])
        self.assertEqual((self.dir / "条件履歴.csv").read_bytes().count(BOM), 1)

    def test_ac09_memo_column(self):
        self.save(txt=True, csv=True)
        self.save(txt=False, csv=True)
        text = (self.dir / "条件履歴.csv").read_bytes()[len(BOM):].decode("utf-8")
        lines = text.split("\r\n")
        # 1行目ヘッダ、2〜3行目が1件目（備考が2行）、4〜5行目が2件目
        self.assertTrue(lines[2].endswith(",山田,20260928_charge_test_条件メモ.txt"))
        self.assertTrue(lines[4].endswith(",山田,"))
        self.assertEqual(self.files(), ["20260928_charge_test_条件メモ.txt", "条件履歴.csv"])

    def test_quoting(self):
        raw = example_raw(program='a,b "c"', note="")
        self.save(raw=raw)
        text = (self.dir / "条件履歴.csv").read_text(encoding="utf-8-sig")
        self.assertIn(',"a,b ""c""",', text)

    def test_appends_after_file_without_trailing_newline(self):
        path = self.dir / "条件履歴.csv"
        path.write_bytes(BOM + EXPECTED_HEADER.rstrip("\r\n").encode("utf-8"))
        self.save()
        text = path.read_bytes().decode("utf-8-sig")
        self.assertTrue(text.startswith(EXPECTED_HEADER + "2026-09-28 14:30,"))

    def test_ac17_header_change_creates_numbered_file(self):
        self.save()
        original = (self.dir / "条件履歴.csv").read_bytes()
        settings = settings_with_temp_field()
        asked = []

        def confirm(name):
            asked.append(name)
            return True

        names = self.save(raw=example_raw(temp="25℃"), settings=settings, confirm=confirm)
        self.assertEqual(asked, ["条件履歴_2.csv"])
        self.assertEqual(names, ["条件履歴_2.csv"])
        self.assertEqual((self.dir / "条件履歴.csv").read_bytes(), original)
        header = (self.dir / "条件履歴_2.csv").read_bytes().decode("utf-8-sig").split("\r\n")[0]
        self.assertEqual(header, "日時,プログラム,基板,基板状態,充電・放電方式,データファイル,"
                                 "周囲温度,備考,測定者,メモファイル")
        # 2回目以降は一致する _2 に確認なしで追記
        self.save(raw=example_raw(temp="26℃"), settings=settings)
        self.assertEqual(self.files(), ["条件履歴.csv", "条件履歴_2.csv"])
        # 元の構成に戻すと 条件履歴.csv に追記
        self.save()
        self.assertGreater(len((self.dir / "条件履歴.csv").read_bytes()), len(original))

    def test_ac17_cancel_saves_nothing(self):
        self.save()
        before = (self.dir / "条件履歴.csv").read_bytes()
        settings = settings_with_temp_field()
        with self.assertRaises(SaveCancelled):
            self.save(raw=example_raw(temp="x"), settings=settings, txt=True, confirm=lambda n: False)
        self.assertEqual(self.files(), ["条件履歴.csv"])
        self.assertEqual((self.dir / "条件履歴.csv").read_bytes(), before)

    def test_next_number_after_gap(self):
        (self.dir / "条件履歴.csv").write_bytes(BOM + b"a,b\r\n")
        (self.dir / "条件履歴_3.csv").write_bytes(BOM + b"c,d\r\n")
        names = self.save(confirm=lambda n: True)
        self.assertEqual(names, ["条件履歴_4.csv"])

    def test_matching_file_found_by_number_order(self):
        (self.dir / "条件履歴.csv").write_bytes(BOM + b"a,b\r\n")
        (self.dir / "条件履歴_2.csv").write_bytes(BOM + EXPECTED_HEADER.encode("utf-8"))
        self.assertEqual(self.save(), ["条件履歴_2.csv"])

    def test_custom_history_csv_name(self):
        import json

        from evalmemo.settings import DEFAULT_SETTINGS_TEXT, parse_settings

        data = json.loads(DEFAULT_SETTINGS_TEXT)
        data["history_csv_name"] = "history"
        settings = parse_settings(json.dumps(data, ensure_ascii=False))
        self.assertEqual(self.save(settings=settings), ["history.csv"])


class RollbackTest(TempDirTest):
    """F-09 / 9章：一部のファイルだけ保存された状態を残さない"""

    def test_ac19_locked_csv_cancel_removes_txt(self):
        self.save()
        before = (self.dir / "条件履歴.csv").read_bytes()
        asked = []

        def retry(name):
            asked.append(name)
            return False

        with mock.patch.object(output, "write_csv", side_effect=PermissionError(13, "locked")):
            with self.assertRaises(SaveCancelled):
                self.save(txt=True, csv=True, retry=retry)
        self.assertEqual(asked, ["条件履歴.csv"])
        self.assertEqual(self.files(), ["条件履歴.csv"])
        self.assertEqual((self.dir / "条件履歴.csv").read_bytes(), before)

    def test_ac19_locked_csv_retry_succeeds(self):
        self.save()
        real = output.write_csv
        calls = {"n": 0}

        def flaky(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise PermissionError(13, "locked")
            return real(*args, **kwargs)

        asked = []
        with mock.patch.object(output, "write_csv", side_effect=flaky):
            names = self.save(txt=True, csv=True, retry=lambda n: asked.append(n) or True)
        self.assertEqual(asked, ["条件履歴.csv"])
        self.assertEqual(names, ["20260928_charge_test_条件メモ.txt", "条件履歴.csv"])
        self.assertEqual(self.files(), ["20260928_charge_test_条件メモ.txt", "条件履歴.csv"])

    def test_locked_while_reading_header(self):
        self.save()
        real = output.read_csv_header
        calls = {"n": 0}

        def flaky(path):
            calls["n"] += 1
            if calls["n"] == 1:
                raise PermissionError(13, "locked", str(path))
            return real(path)

        asked = []
        with mock.patch.object(output, "read_csv_header", side_effect=flaky):
            self.save(retry=lambda n: asked.append(n) or True)
        self.assertEqual(asked, ["条件履歴.csv"])

    def test_csv_write_error_removes_txt(self):
        with mock.patch.object(output, "write_csv", side_effect=OSError(28, "No space left")):
            with self.assertRaises(SaveError):
                self.save(txt=True, csv=True)
        self.assertEqual(self.files(), [])

    def test_partial_append_is_truncated(self):
        self.save()
        path = self.dir / "条件履歴.csv"
        before = path.read_bytes()
        real_open = open

        class FailingFile:
            def __init__(self, fp):
                self.fp = fp

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                self.fp.close()

            def write(self, data):
                self.fp.write(data[:10])
                self.fp.flush()
                raise OSError(28, "No space left")

            def __getattr__(self, name):
                return getattr(self.fp, name)

        def fake_open(file, mode="r", *args, **kwargs):
            fp = real_open(file, mode, *args, **kwargs)
            return FailingFile(fp) if mode == "r+b" else fp

        with mock.patch("builtins.open", side_effect=fake_open):
            with self.assertRaises(SaveError):
                self.save(txt=True, csv=True)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(self.files(), ["条件履歴.csv"])

    def test_txt_write_error_does_not_touch_csv(self):
        real_open = open

        def fake_open(file, mode="r", *args, **kwargs):
            if str(file).endswith(".txt"):
                raise PermissionError(13, "Permission denied", str(file))
            return real_open(file, mode, *args, **kwargs)

        with mock.patch("builtins.open", side_effect=fake_open):
            with self.assertRaises(SaveError):
                self.save(txt=True, csv=True)
        self.assertEqual(self.files(), [])


class ValidationTest(TempDirTest):
    def check(self, raw, csv=True, txt=False, folder=None):
        return validate_input(DEFAULT, raw, str(self.dir) if folder is None else folder, csv, txt)

    def test_ok(self):
        self.assertEqual(self.check(example_raw()), [])

    def test_ac12_nonexistent_date(self):
        errs = self.check(example_raw(datetime="2026-02-30 10:00"))
        self.assertEqual(len(errs), 1)
        self.assertIn("日時", errs[0])
        for bad in ["2026/09/28 14:30", "2026-09-28 14:30:00", "2026-9-28 14:30", "2026-09-28 24:00", ""]:
            with self.subTest(bad=bad):
                self.assertTrue(self.check(example_raw(datetime=bad)))

    def test_ac07_other_option(self):
        raw = example_raw(method={"choice": "その他", "other": "放電 定電流1A"})
        self.assertEqual(self.check(raw), [])
        self.assertEqual(output_values(DEFAULT, raw)["method"], "放電 定電流1A")
        errs = self.check(example_raw(method={"choice": "その他", "other": "  "}))
        self.assertEqual(errs, ["充電・放電方式：「その他」の内容が入力されていません"])
        # その他以外を選べば、入力済みの他テキストは出力されない
        raw = example_raw(method={"choice": "USB充電", "other": "放電 定電流1A"})
        self.assertEqual(output_values(DEFAULT, raw)["method"], "USB充電")

    def test_ac13_required_fields_listed(self):
        raw = example_raw(program="", board=" ", method={"choice": "", "other": ""}, measurer="")
        errs = self.check(raw)
        labels = [e.split("：")[0] for e in errs]
        self.assertEqual(labels, ["プログラム", "基板", "充電・放電方式", "測定者"])

    def test_folder_and_format(self):
        self.assertEqual(self.check(example_raw(), folder=""), ["保存先：フォルダが選択されていません"])
        self.assertTrue(self.check(example_raw(), folder=str(self.dir / "none"))[0].startswith("保存先"))
        self.assertEqual(self.check(example_raw(), csv=False, txt=False), ["出力形式を1つ以上選んでください"])


class ValueTest(unittest.TestCase):
    def test_ac06_checkgroup(self):
        raw = example_raw(board_state={"外枠": False, "線出し": True, "シャント抵抗": True})
        self.assertEqual(output_values(DEFAULT, raw)["board_state"], "外枠無、線出し有、シャント抵抗有")
        raw = example_raw(board_state={})
        self.assertEqual(output_values(DEFAULT, raw)["board_state"], "外枠無、線出し無、シャント抵抗無")

    def test_datafile_name_only(self):
        self.assertEqual(output_values(DEFAULT, example_raw())["datafile"], "20260928_charge_test.csv")
        self.assertEqual(output_values(DEFAULT, example_raw(datafile=""))["datafile"], "")

    def test_multiline_trailing_newlines_removed(self):
        raw = example_raw(note="a\r\nb\n\n")
        self.assertEqual(output_values(DEFAULT, raw)["note"], "a\nb")


if __name__ == "__main__":
    unittest.main()
