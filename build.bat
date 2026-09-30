@echo off
rem Build MemoGenerator (Windows 11 / Python 3.12)
rem Usage: double-click build.bat, or run it from a command prompt.
rem Output: dist\MemoGenerator\ (MemoGenerator.exe, settings.json and the _internal folder).
rem         Distribute the whole dist\MemoGenerator folder. The exe does not run on its own.
rem Folder (onedir) build on purpose: it starts much faster than a single-file (onefile) exe,
rem which has to unpack itself to a temp folder on every start.
rem This file is ASCII only on purpose (non-ASCII text breaks cmd parsing).
setlocal
cd /d "%~dp0" || goto :error

set PY=py -3.12
%PY% --version >NUL 2>&1 || set PY=python

echo [1/3] Running tests
%PY% -m unittest discover -s tests -t . || goto :error

echo [2/3] Installing PyInstaller
%PY% -m pip install --upgrade pyinstaller || goto :error

echo [3/3] Building MemoGenerator
%PY% -m PyInstaller --noconfirm --clean --onedir --windowed --name MemoGenerator --icon assets\MemoGenerator.ico --paths src --distpath dist --workpath build src\MemoGenerator.py || goto :error
copy /y settings.json dist\MemoGenerator\settings.json || goto :error

echo.
echo Done: distribute the whole dist\MemoGenerator folder
endlocal
exit /b 0

:error
echo.
echo BUILD FAILED
endlocal
exit /b 1
