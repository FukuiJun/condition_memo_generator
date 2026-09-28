"""画面の自動テスト。ディスプレイが無い環境（tkinter が使えない環境）ではスキップする。"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from .helpers import DEFAULT

try:
    import tkinter as tk

    _root = tk.Tk()
    _root.destroy()
    HAS_DISPLAY = True
except Exception:  # noqa: BLE001
    HAS_DISPLAY = False

from memogenerator.settings import DEFAULT_SETTINGS_TEXT, load_settings
from memogenerator.state import StateStore


@unittest.skipUnless(HAS_DISPLAY, "ディスプレイが無いためスキップ")
class GuiTest(unittest.TestCase):
    def setUp(self):
        from memogenerator import gui

        self.gui = gui
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.app_dir = base / "app"
        self.data_dir = base / "appdata"
        self.folder = base / "eval" / "20260928"
        for d in (self.app_dir, self.data_dir, self.folder):
            d.mkdir(parents=True)
        self.env = mock.patch.dict(os.environ, {"MEMOGENERATOR_DATA_DIR": str(self.data_dir)})
        self.env.start()
        self.messages = []
        self.patches = [
            mock.patch.object(gui.messagebox, name, side_effect=self._recorder(name, ret))
            for name, ret in [("showwarning", "ok"), ("showerror", "ok"), ("showinfo", "ok"),
                              ("askokcancel", True), ("askretrycancel", False)]
        ]
        for p in self.patches:
            p.start()
        self.root = None
        self.app = self.start()

    def _recorder(self, name, ret):
        def record(title, message, **kwargs):
            self.messages.append((name, title, message))
            return ret
        return record

    def tearDown(self):
        if self.root is not None:
            self.root.destroy()
        for p in self.patches:
            p.stop()
        self.env.stop()
        self._tmp.cleanup()

    def start(self):
        if self.root is not None:
            self.root.destroy()
        self.root = tk.Tk()
        loaded = load_settings(self.app_dir / "settings.json")
        state = StateStore(self.data_dir / "state.json")
        state.load()
        app = self.gui.MemoGeneratorApp(self.root, loaded.settings, self.app_dir / "settings.json", state)
        self.root.update()
        return app

    def fill_example(self):
        w = self.app.widgets
        w["datetime"].set_raw("2026-09-28 14:30")
        w["program"].set_raw("ver1.2.0")
        w["board"].set_raw("Rev.B")
        w["board_state"].set_raw({"外枠": False, "線出し": True, "シャント抵抗": True})
        w["method"].set_raw({"choice": "USB充電", "other": ""})
        w["datafile"].set_raw(str(self.folder / "20260928_charge_test.csv"))
        w["note"].set_raw("室温25℃\n負荷500mA")
        w["measurer"].set_raw("山田")
        self.app.set_folder(str(self.folder))

    def files(self):
        return sorted(p.name for p in self.folder.iterdir())

    def test_ac01_default_screen(self):
        self.assertEqual((self.app_dir / "settings.json").read_text(encoding="utf-8"), DEFAULT_SETTINGS_TEXT)
        self.assertEqual(list(self.app.widgets), [f.id for f in DEFAULT.fields])
        self.assertEqual(self.root.title(), "MemoGenerator v1.0.0")
        program = self.app.widgets["program"]
        self.assertEqual(program.label.cget("text"), "プログラム")
        self.assertEqual(program.required_mark.cget("text"), " *")  # 必須の印
        self.assertEqual(self.app.widgets["board_state"].label.cget("text"), "基板状態")
        self.assertIsNone(self.app.widgets["board_state"].required_mark)

    def test_ac08_output_format(self):
        self.assertTrue(self.app.csv_var.get())
        self.assertFalse(self.app.txt_var.get())
        self.fill_example()
        self.app.csv_var.set(False)
        self.app.save()
        self.assertEqual(self.messages[-1][2], "出力形式を1つ以上選んでください")
        self.assertEqual(self.files(), [])

    def test_ac07_other_entry(self):
        sel = self.app.widgets["method"]
        self.assertEqual(str(sel.other_entry.cget("state")), "disabled")
        sel.choice_var.set("その他")
        sel._on_selected()
        self.assertEqual(str(sel.other_entry.cget("state")), "normal")
        sel.other_var.set("放電 定電流1A")
        sel.choice_var.set("USB充電")
        sel._on_selected()
        self.assertEqual(str(sel.other_entry.cget("state")), "disabled")
        self.assertEqual(sel.other_var.get(), "放電 定電流1A")  # 内容は保持

    def test_ac13_required_errors(self):
        self.app.set_folder(str(self.folder))
        self.app.save()
        name, _title, message = self.messages[-1]
        self.assertEqual(name, "showwarning")
        for label in ["プログラム", "基板", "充電・放電方式", "測定者"]:
            self.assertIn(label, message)
        self.assertEqual(self.files(), [])

    def test_save_ctrl_s_and_restart(self):  # AC-02/03（画面経由）, AC-14, AC-20
        self.fill_example()
        self.app.txt_var.set(True)
        note = self.app.widgets["note"].text
        note.focus_force()
        self.root.update()
        note.event_generate("<Control-s>")
        self.root.update()
        self.assertEqual(self.files(), ["20260928_charge_test_条件メモ.txt", "条件履歴.csv"])
        self.assertEqual(self.app.status_var.get(),
                         "保存しました：20260928_charge_test_条件メモ.txt, 条件履歴.csv")
        self.assertEqual(self.app.status_icon.cget("text"), "✓")
        # 保存後：remember でない項目はクリア、出力形式・保存先は保持
        w = self.app.widgets
        self.assertEqual(w["note"].get_raw(), "")
        self.assertEqual(w["datafile"].get_raw(), "")
        self.assertEqual(w["program"].get_raw(), "ver1.2.0")
        self.assertTrue(self.app.txt_var.get())
        self.assertEqual(self.app.folder_var.get(), str(self.folder))
        self.assertEqual(list(w["program"].combo.cget("values")), ["ver1.2.0"])

        # 再起動
        self.app = self.start()
        w = self.app.widgets
        self.assertEqual(w["program"].get_raw(), "ver1.2.0")
        self.assertEqual(w["measurer"].get_raw(), "山田")
        self.assertEqual(w["method"].get_raw()["choice"], "USB充電")
        self.assertEqual(w["board_state"].get_raw(), {"外枠": False, "線出し": True, "シャント抵抗": True})
        self.assertEqual(w["note"].get_raw(), "")
        self.assertEqual(w["datafile"].get_raw(), "")
        self.assertNotEqual(w["datetime"].get_raw(), "2026-09-28 14:30")
        self.assertEqual(self.app.folder_var.get(), str(self.folder))
        self.assertTrue(self.app.csv_var.get())
        self.assertFalse(self.app.txt_var.get())

    def test_ac19_locked_cancel(self):
        self.fill_example()
        self.app.txt_var.set(True)
        with mock.patch("memogenerator.output.write_csv", side_effect=PermissionError(13, "locked")):
            self.app.save()
        self.assertEqual(self.messages[-1][0], "askretrycancel")
        self.assertIn("条件履歴.csv が開かれています", self.messages[-1][2])
        self.assertEqual(self.files(), [])
        self.assertIn("キャンセル", self.app.status_var.get())

    def test_ac10_datafile_sets_folder(self):  # F-05
        other = Path(self._tmp.name) / "eval" / "x"
        other.mkdir()
        self.app.set_folder(str(self.folder))
        picked = str(other / "abc.csv")
        with mock.patch.object(self.gui.filedialog, "askopenfilename", return_value=picked):
            self.app.widgets["datafile"].browse()
        self.assertEqual(self.app.folder_var.get(), str(other))
        self.assertEqual(self.app.widgets["datafile"].name_var.get(), "abc.csv")
        self.assertIn("データファイルのフォルダに変更", self.app.status_var.get())
        self.assertEqual(str(self.app.folder_label.cget("style")), "FolderHighlight.TLabel")
        # 手動で変更した後でも、データファイルを選び直せばそのフォルダが優先される
        self.app.set_folder(str(self.folder))
        with mock.patch.object(self.gui.filedialog, "askopenfilename", return_value=picked):
            self.app.widgets["datafile"].browse()
        self.assertEqual(self.app.folder_var.get(), str(other))

    def test_ac16_reload_keeps_values(self):
        self.fill_example()
        data = json.loads(DEFAULT_SETTINGS_TEXT)
        data["fields"].insert(6, {"id": "temp", "label": "周囲温度", "type": "text"})
        (self.app_dir / "settings.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        self.app.reload_settings()
        self.root.update()
        self.assertEqual(list(self.app.widgets)[6], "temp")
        self.assertEqual(self.app.widgets["program"].get_raw(), "ver1.2.0")
        self.assertEqual(self.app.widgets["note"].get_raw(), "室温25℃\n負荷500mA")
        self.assertEqual(self.app.widgets["datetime"].get_raw(), "2026-09-28 14:30")

    def test_reload_error_keeps_screen(self):
        self.fill_example()
        (self.app_dir / "settings.json").write_text('{"fields": [{"id": "a", "label": "A", "type": "x"}]}',
                                                   encoding="utf-8")
        self.app.reload_settings()
        self.assertEqual(self.messages[-1][0], "showerror")
        self.assertIn("未知の種類", self.messages[-1][2])
        self.assertEqual(len(self.app.widgets), 8)
        self.assertEqual(self.app.widgets["program"].get_raw(), "ver1.2.0")


if __name__ == "__main__":
    unittest.main()
