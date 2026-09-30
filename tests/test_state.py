import json
import tempfile
import unittest
from pathlib import Path

from .helpers import DEFAULT, example_raw, settings_with_select_text

from memogenerator.settings import parse_settings
from memogenerator.state import StateStore, combo_candidates, update_history
from memogenerator.values import output_values


class HistoryTest(unittest.TestCase):
    def test_ac15_latest_ten_newest_first(self):
        with tempfile.TemporaryDirectory() as d:
            store = StateStore(Path(d) / "state.json")
            for i in range(1, 12):
                raw = example_raw(program=f"ver1.{i}")
                store.update_after_save(DEFAULT, raw, output_values(DEFAULT, raw), d)
                store.save()
            reloaded = StateStore(Path(d) / "state.json")
            self.assertIsNone(reloaded.load())
            expected = [f"ver1.{i}" for i in range(11, 1, -1)]
            self.assertEqual(reloaded.history("program"), expected)
            self.assertEqual(combo_candidates(DEFAULT.field("program"), reloaded.history("program")), expected)

    def test_test_summary_history(self):  # 試験概要：プリセット無し、過去の入力が候補になる
        field = DEFAULT.field("test_summary")
        self.assertEqual((field.type, field.options, field.history), ("combo", (), True))
        self.assertEqual(combo_candidates(field, []), [])
        with tempfile.TemporaryDirectory() as d:
            store = StateStore(Path(d) / "state.json")
            for summary in ["USB充電 1A", "放電 定電流1A", "USB充電 1A"]:
                raw = example_raw(test_summary=summary)
                store.update_after_save(DEFAULT, raw, output_values(DEFAULT, raw), d)
            self.assertEqual(combo_candidates(field, store.history("test_summary")),
                             ["USB充電 1A", "放電 定電流1A"])

    def test_no_duplicates(self):
        h = []
        for v in ["a", "b", "a", "", "c", "b"]:
            h = update_history(h, v)
        self.assertEqual(h, ["b", "c", "a"])

    def test_candidates_history_first_then_options(self):
        field = DEFAULT.field("board")
        self.assertEqual(combo_candidates(field, ["Rev.C", "Rev.B"]), ["Rev.C", "Rev.B", "Rev.A"])
        self.assertEqual(combo_candidates(field, []), ["Rev.A", "Rev.B"])


class RememberTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "MemoGenerator" / "state.json"

    def tearDown(self):
        self._tmp.cleanup()

    def saved_store(self, raw, settings=DEFAULT):
        store = StateStore(self.path)
        store.load()
        store.update_after_save(settings, raw, output_values(settings, raw), self._tmp.name)
        store.save()
        reloaded = StateStore(self.path)
        self.assertIsNone(reloaded.load())
        return reloaded

    def test_ac14_remember_only(self):
        store = self.saved_store(example_raw())
        s = DEFAULT
        self.assertEqual(store.remembered(s.field("program")), "ver1.2.0")
        self.assertEqual(store.remembered(s.field("board_state")),
                         {"筐体": False, "線出し": True, "シャント抵抗": True})
        self.assertEqual(store.remembered(s.field("test_summary")), "USB充電 定電流1A")
        self.assertIsNone(store.remembered(s.field("note")))
        self.assertIsNone(store.remembered(s.field("datafile")))
        self.assertIsNone(store.remembered(s.field("date")))
        self.assertEqual(store.last_folder, self._tmp.name)

    def test_select_remembered_with_other_text(self):
        sel_text = settings_with_select_text()
        sel = parse_settings(sel_text)
        store = self.saved_store(example_raw(method={"choice": "その他", "other": "放電 定電流1A"}), sel)
        self.assertEqual(store.remembered(sel.field("method")), {"choice": "その他", "other": "放電 定電流1A"})

    def test_select_value_not_in_options_is_unselected(self):
        sel_text = settings_with_select_text()
        store = self.saved_store(example_raw(method={"choice": "ワイヤレス充電", "other": ""}),
                                 parse_settings(sel_text))
        data = json.loads(sel_text)
        next(f for f in data["fields"] if f["id"] == "method")["options"] = ["USB充電"]
        s = parse_settings(json.dumps(data, ensure_ascii=False))
        self.assertEqual(store.remembered(s.field("method"))["choice"], "")

    def test_checkgroup_matched_by_item_name(self):
        store = self.saved_store(example_raw())
        data = json.loads(DEFAULT_TEXT())
        data["fields"][4]["items"] = ["シャント抵抗", "新項目", "筐体"]
        s = parse_settings(json.dumps(data, ensure_ascii=False))
        self.assertEqual(store.remembered(s.field("board_state")),
                         {"シャント抵抗": True, "新項目": False, "筐体": False})

    def test_renamed_item_starts_unchecked(self):  # 旧「外枠」の状態は「筐体」に引き継がない
        self.path.parent.mkdir(parents=True)
        self.path.write_text(json.dumps({"values": {"board_state": {"外枠": True, "線出し": True}}},
                                        ensure_ascii=False), encoding="utf-8")
        store = StateStore(self.path)
        store.load()
        self.assertEqual(store.remembered(DEFAULT.field("board_state")),
                         {"筐体": False, "線出し": True, "シャント抵抗": False})

    def test_unknown_ids_are_kept(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text(json.dumps({"values": {"old": "x"}, "history": {"old": ["x"]}}), encoding="utf-8")
        self.saved_store(example_raw())
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(data["values"]["old"], "x")
        self.assertEqual(data["history"]["old"], ["x"])

    def test_broken_state_is_ignored(self):
        self.path.parent.mkdir(parents=True)
        for content in ["{broken", "[1, 2]", '{"values": 3, "history": {"program": "x"}, "last_folder": 1}']:
            with self.subTest(content=content):
                self.path.write_text(content, encoding="utf-8")
                store = StateStore(self.path)
                store.load()
                self.assertIsNone(store.remembered(DEFAULT.field("program")))
                self.assertEqual(store.history("program"), [])
                self.assertEqual(store.last_folder, "")

    def test_legacy_state_is_read_when_new_is_missing(self):
        legacy = Path(self._tmp.name) / "EvalMemo" / "state.json"
        legacy.parent.mkdir(parents=True)
        legacy.write_text(json.dumps({"values": {"program": "ver0.9"}, "last_folder": "C:/x"}),
                          encoding="utf-8")
        store = StateStore(self.path, legacy)
        self.assertIsNone(store.load())
        self.assertEqual(store.remembered(DEFAULT.field("program")), "ver0.9")
        store.save()  # 保存は新しい場所へ
        self.assertTrue(self.path.is_file())
        # 新しい state.json があれば旧ファイルは読まない
        legacy.write_text(json.dumps({"values": {"program": "old"}}), encoding="utf-8")
        store = StateStore(self.path, legacy)
        store.load()
        self.assertEqual(store.remembered(DEFAULT.field("program")), "ver0.9")

    def test_missing_state_is_not_an_error(self):
        self.assertIsNone(StateStore(self.path).load())


def DEFAULT_TEXT():
    from memogenerator.settings import DEFAULT_SETTINGS_TEXT

    return DEFAULT_SETTINGS_TEXT


if __name__ == "__main__":
    unittest.main()
