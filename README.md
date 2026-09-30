# MemoGenerator（評価条件メモ出力ソフト）

評価データを取得したときの条件（プログラム・基板・基板状態・測定条件など）を決まった項目で入力し、
測定フォルダに次のファイルを出力します。

- **条件履歴**（`条件履歴.csv`）… 1測定1行で追記。Excel で開いて条件の変遷を確認できます
- **条件メモ**（`<データファイル名>_条件メモ.txt`）… 1測定1ファイル

入力欄の構成（項目・並び順・候補・必須）は `settings.json` で変更できます（exe の作り直しは不要）。
仕様は [SPEC.md](SPEC.md) を参照してください。

---

## 使い方

1. 評価データを取得する
2. `MemoGenerator.exe` を起動する（前回の入力値が入った状態で開きます。日付は今日）
3. 「データファイル」の［参照］で測定データのファイルを選ぶ
   → 保存先がそのファイルのフォルダに自動で変わります（変わったときは保存先が黄色で強調され、下のステータス欄にも表示されます）
4. 変わった項目だけ修正する
5. 出力形式を確認して［保存］（または **Ctrl+S**）

| 画面の部品 | 説明 |
|---|---|
| ラベルの後ろの `*` | 必須項目。空のままでは保存できません |
| 日付の［今日］ | 今日の日付を入れ直します |
| 試験概要・プログラムなどのプルダウン | 過去に入力した内容（新しい順に最新10件）が候補に出ます。自由に入力もできます |
| データファイルの［クリア］ | 選択を取り消します（保存先は変わりません） |
| 出力形式 | 起動時は「CSV」のみチェック。両方チェックも可 |
| 保存先の［変更］ | 保存先フォルダを手動で選びます。その後データファイルを選び直すと、データファイルのフォルダが優先されます |

保存に成功すると、次の保存に備えて「前回値を引き継がない項目」（既定では備考・データファイル）が空になり、
日付が今日に更新されます。出力形式と保存先はそのまま残ります。

### 出力されるファイル

条件メモ（UTF-8 / CRLF）の例:

```
日付：2026-09-28
プログラム：ver1.2.0
基板：Rev.B
基板状態：筐体無、線出し有、シャント抵抗有
試験概要：USB充電 定電流1A
データファイル：20260928_charge_test.csv
備考：室温25℃
負荷500mA


測定者：山田
```

- ファイル名はデータファイルを選んだとき `<データファイル名（拡張子なし）>_条件メモ.txt`、
  選んでいないとき `<日付 YYYYMMDD>_条件メモ.txt`
- 同名のファイルがあるときは上書きせず `_2`, `_3`… を付けます

条件履歴（UTF-8 BOM付き / CRLF）:

- 1行目は項目の label（最後に「メモファイル」列）。「メモファイル」列には同時に出力した .txt のファイル名が入ります
- **項目構成を変えた後**に既存の `条件履歴.csv` があるフォルダへ保存すると、
  「項目構成が変わったため、新しいファイル 条件履歴_2.csv に保存します」と確認が出ます。
  OK で `条件履歴_2.csv` を作成し、以降は見出しが一致するファイルに追記します（元のファイルは変更しません）
- CSV を Excel で開いたまま保存すると「閉じてから［再試行］を押してください」と表示されます。
  ［キャンセル］するとその回の .txt も削除され、何も保存されなかった状態に戻ります

### データの置き場所

| ファイル | 場所 |
|---|---|
| 設定ファイル | `MemoGenerator.exe` と同じフォルダの `settings.json`（無ければ起動時に既定値で作成） |
| 前回値・入力履歴・前回の保存先 | `%APPDATA%\MemoGenerator\state.json`（PC・Windows ユーザーごと） |
| エラーログ | `%APPDATA%\MemoGenerator\error.log`（エラーが起きたときだけ追記） |

---

## 設定ファイル（settings.json）の書き方

`settings.json` をテキストエディタ（メモ帳など）で編集し、メニュー「ファイル → 設定を再読み込み」を選ぶと画面に反映されます
（「ファイル → 設定ファイルを開く」で既定のアプリで開けます）。文字コードは UTF-8 で保存してください。

設定に誤りがあると、どの項目の何が不正かを一覧で表示します。
起動時は既定の設定で起動し（settings.json は書き換えません）、再読み込み時は画面を変更前のままにします。

チームで同じ設定を使うときは、編集した `settings.json` を `MemoGenerator.exe` と一緒に配布してください。

### 全体の形

```json
{
  "history_csv_name": "条件履歴",
  "fields": [
    { 項目1 },
    { 項目2 },
    ...
  ]
}
```

| 属性 | 意味 |
|---|---|
| `history_csv_name` | 条件履歴のファイル名（拡張子なし）。省略時「条件履歴」。`\ / : * ? " < > \|` は使えません |
| `fields` | 項目の配列。**書いた順に**画面・.txt・CSV の列に並びます（1件以上） |

### 項目の共通の属性

| 属性 | 必須 | 既定 | 意味 |
|---|---|---|---|
| `id` | ○ | - | 半角英数字と `_`。全項目で重複不可。前回値・入力履歴の保存キーになるので、**運用開始後は変えない**でください |
| `label` | ○ | - | 画面・.txt・CSV の見出しに使う表示名。全項目で重複不可（「メモファイル」は使えません） |
| `type` | ○ | - | 項目の種類（下表） |
| `required` | | `false` | `true` なら空で保存できません（checkgroup には指定不可） |
| `remember` | | `false` | `true` なら保存後も値を残し、次回起動時に復元します |
| `blank_lines_before` | | `0` | .txt でこの項目の前に入れる空行の数（0〜5） |

- `true` / `false` や数値は `"` で囲まずに書きます
- 種類ごとに使える属性は決まっています。知らない属性（スペルミスを含む）はエラーになります
- datetime 型はちょうど1件、datafile 型は0件または1件にしてください

### 項目の種類（type）ごとの書き方

#### text（1行テキスト）

```json
{"id": "temp", "label": "周囲温度", "type": "text"}
```

#### multiline（複数行テキスト）

`rows` は表示する行数（既定 5）。.txt では2行目以降をインデントせずにそのまま続けて出力します。

```json
{"id": "note", "label": "備考", "type": "multiline", "rows": 5}
```

#### combo（候補から選択 or 自由入力）

`options` は候補（省略可）。`history` を `true` にすると、過去の入力値（新しい順に最新10件）が候補の先頭に追加されます。

```json
{"id": "board", "label": "基板", "type": "combo", "required": true,
 "options": ["Rev.A", "Rev.B"], "history": true, "remember": true}
```

決まった候補を用意せず、過去の入力だけを候補にする例（既定の「試験概要」）:

```json
{"id": "test_summary", "label": "試験概要", "type": "combo", "required": true,
 "options": [], "history": true, "remember": true}
```

#### select（候補から選ぶだけ）

`options` は必須。`other_option` を指定すると、その名前の選択肢が末尾に追加され、
選んだときだけ隣のテキスト欄に入力でき、入力した文字列がそのまま出力値になります（既定の設定では使っていません）。

```json
{"id": "method", "label": "充電・放電方式", "type": "select", "required": true,
 "options": ["USB充電", "ワイヤレス充電", "連続測定モード"],
 "other_option": "その他", "remember": true}
```

#### checkgroup（チェックボックスの組）

`items`（1件以上）の数だけチェックボックスを横に並べます。出力値は各 item に `on_text`（既定「有」）/`off_text`（既定「無」）を付け、
`separator`（既定「、」）でつないだ文字列です（例：`筐体無、線出し有、シャント抵抗有`）。
前回値は item 名で対応付けるので、item を追加・並べ替えしても既存のチェック状態は引き継がれます。

```json
{"id": "board_state", "label": "基板状態", "type": "checkgroup",
 "items": ["筐体", "線出し", "シャント抵抗"],
 "on_text": "有", "off_text": "無", "separator": "、", "remember": true}
```

#### datetime（日付）

`YYYY-MM-DD` 形式の日付。起動時と保存後は今日の日付が入ります（［今日］ボタンで入れ直し可）。ちょうど1件必要です。
条件メモのファイル名（データファイル未選択時）にも使います。

```json
{"id": "date", "label": "日付", "type": "datetime", "required": true}
```

時刻も記録したいときは `"with_time": true` を付けると `YYYY-MM-DD HH:MM` 形式になり、ボタンは［現在時刻］になります。

```json
{"id": "date", "label": "日時", "type": "datetime", "required": true, "with_time": true}
```

#### datafile（データファイル）

［参照］で選んだファイルの名前（パスなし）を出力します。選ぶと保存先がそのファイルのフォルダになり、
条件メモのファイル名にも使われます。未選択時、.txt には「（なし）」と出力します。0件または1件。

```json
{"id": "datafile", "label": "データファイル", "type": "datafile"}
```

### 例：備考の前に「周囲温度」を追加する

```json
    {"id": "datafile", "label": "データファイル", "type": "datafile"},
    {"id": "temp", "label": "周囲温度", "type": "text"},
    {"id": "note", "label": "備考", "type": "multiline", "rows": 5},
```

追加後に既存の `条件履歴.csv` があるフォルダへ保存すると、列が変わるため `条件履歴_2.csv` が新しく作られます（上記「出力されるファイル」参照）。

### よくある誤り

- 最後の項目の後ろに `,` を付けた／項目の間の `,` を忘れた → 「JSON として読み込めません（○行 ○列 …）」
- `"required": "true"` のように `true` を `"` で囲んだ → 「required は true または false で指定してください」
- id を他の項目と同じにした → 「id「○○」が ○番目の項目と重複しています」

---

## 開発

### フォルダ構成

| パス | 内容 |
|---|---|
| `src/MemoGenerator.py` | 起動スクリプト（exe のエントリポイント） |
| `src/memogenerator/settings.py` | 設定ファイルの定義・読み込み・検証 |
| `src/memogenerator/values.py` | 入力値→出力値の変換、入力チェック |
| `src/memogenerator/output.py` | 条件メモ・条件履歴の生成と保存（ロールバック含む） |
| `src/memogenerator/state.py` | 状態ファイル（前回値・入力履歴・前回保存先） |
| `src/memogenerator/gui.py` | 画面（tkinter） |
| `src/memogenerator/theme.py` | 画面デザイン「ラボノート」の色・フォント（見た目を変えるときはここだけ編集） |
| `src/memogenerator/icon_data.py` | ウィンドウのアイコン画像（`tools/make_icon.py` が生成。直接編集しない） |
| `assets/icon.svg`, `assets/icon-small.svg` | アプリアイコンの原画（24px 以下は small の方を使う） |
| `assets/MemoGenerator.ico` | exe のアイコン（`tools/make_icon.py` が生成） |
| `tools/make_icon.py` | SVG からアイコン（.ico と埋め込み用 PNG）を作るツール |
| `settings.json` | 既定の設定ファイル（exe と同梱） |
| `build.bat` | exe のビルド |
| `tests/` | 自動テスト |

外部ライブラリは使っていません（Python 3.12 標準ライブラリのみ。ビルド時のみ PyInstaller）。

### 実行・テスト

```bat
cd src
py -3.12 MemoGenerator.py
```

開発時の `settings.json` はリポジトリ直下のものを使います（環境変数 `MEMOGENERATOR_APP_DIR` で変更可。
`MEMOGENERATOR_DATA_DIR` で state.json / error.log の場所も変更できます）。

```bat
py -3.12 -m unittest discover -s tests -t .
```

画面のテスト（`tests/test_gui.py`）はディスプレイが無い環境では自動でスキップされます。

### exe のダウンロード（GitHub Actions）

プッシュするたびに GitHub Actions（`.github/workflows/build.yml`）が Windows 上でテスト・exe 作成・起動確認を行います。

1. GitHub のリポジトリ画面で「Actions」タブを開く
2. 「Build MemoGenerator.exe」の実行一覧から、対象ブランチの成功した（緑のチェックの）実行を開く
3. ページ下部の「Artifacts」にある **MemoGenerator** をクリックして zip をダウンロード
4. zip の中の `MemoGenerator.exe` と `settings.json` を同じフォルダに置いて配布する

Artifacts の保存期間は 90 日です。「Run workflow」ボタンから手動で実行することもできます。

### アイコンの変更

アイコンは「ペン立て付きのメモ帳」（リング綴じのメモ帳とペン立て）です。変えるときは `assets/icon.svg`
（小さいサイズ用は `assets/icon-small.svg`）を編集し、次を実行して `.ico` と埋め込み用の画像を作り直してコミットします。

```bat
py -3.12 -m pip install cairosvg pillow
py -3.12 tools\make_icon.py
```

（cairosvg と Pillow はこのツールでのみ使います。アプリ本体・ビルドには不要です）

### ビルド（手元の PC で行う場合）

Windows 11 + Python 3.12 で `build.bat` を実行すると、テスト → PyInstaller のインストール → exe 作成を行い、
`dist\MemoGenerator.exe` と `dist\settings.json` ができます。この2ファイルを配布してください（Python のインストールは不要）。
