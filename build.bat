@echo off
chcp 65001 > nul
rem EvalMemo.exe をビルドする（Windows 11 / Python 3.12）
rem 使い方: build.bat をダブルクリック、またはコマンドプロンプトで実行
setlocal
cd /d "%~dp0"

set PY=py -3.12
%PY% --version > /dev/null 2>&1 || set PY=python

echo [1/3] 自動テスト
%PY% -m unittest discover -s tests -t . || goto :error

echo [2/3] PyInstaller の準備
%PY% -m pip install --upgrade pyinstaller || goto :error

echo [3/3] exe の作成
%PY% -m PyInstaller --noconfirm --clean --onefile --windowed --name EvalMemo --paths src --distpath dist --workpath build src\EvalMemo.py || goto :error
copy /y settings.json dist\settings.json > /dev/null || goto :error

echo.
echo 完了: dist\EvalMemo.exe と dist\settings.json を配布してください
endlocal
exit /b 0

:error
echo.
echo ビルドに失敗しました
endlocal
exit /b 1
