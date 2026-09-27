@echo off
setlocal

rem Build the Sigma5 application as a single Windows executable.
cd /d "%~dp0"

set "PYTHON=python"

 echo [1/3] Installing build dependencies...
%PYTHON% -m pip install --upgrade PyInstaller -r requirements.txt
if errorlevel 1 goto :error

 echo [2/3] Removing previous build artifacts...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist Sigma5.spec del /q Sigma5.spec
if errorlevel 1 goto :error

 echo [3/3] Building bin\Sigma5.exe...
%PYTHON% -m PyInstaller --noconfirm --clean --onefile --windowed --name Sigma5 --distpath bin --workpath build --specpath . --collect-all PySide6 --hidden-import imgur_client --hidden-import machine_art --hidden-import puzzle main.py
if errorlevel 1 goto :error

echo.
echo Build complete: %CD%\bin\Sigma5.exe
exit /b 0

:error
echo.
echo Build failed. Check the error output above.
exit /b 1
