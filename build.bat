@echo off
rem Build MemoGenerator.exe (Windows 11 / Python 3.12)
rem Usage: double-click build.bat, or run it from a command prompt.
rem Output: dist\MemoGenerator.exe and dist\settings.json
rem This file is ASCII only on purpose (non-ASCII text breaks cmd parsing).
setlocal
cd /d "%~dp0" || goto :error

set PY=py -3.12
%PY% --version > /dev/null 2>&1 || set PY=python

echo [1/3] Running tests
%PY% -m unittest discover -s tests -t . || goto :error

echo [2/3] Installing PyInstaller
%PY% -m pip install --upgrade pyinstaller || goto :error

echo [3/3] Building MemoGenerator.exe
%PY% -m PyInstaller --noconfirm --clean --onefile --windowed --name MemoGenerator --icon assets\MemoGenerator.ico --paths src --distpath dist --workpath build src\MemoGenerator.py || goto :error
copy /y settings.json dist\settings.json || goto :error

echo.
echo Done: distribute dist\MemoGenerator.exe together with dist\settings.json
endlocal
exit /b 0

:error
echo.
echo BUILD FAILED
endlocal
exit /b 1
