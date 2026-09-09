@echo off
REM Build Windows executables for Fanorona server and GUI client using PyInstaller
REM Usage: run this from project root in an elevated terminal if required
python -m pip install --upgrade pip
python -m pip install --upgrade pyinstaller
pyinstaller --onefile --name fanorona_server server.py
pyinstaller --noconsole --onefile --name fanorona_gui gui_client.py
echo Build finished. See the "dist" folder.
pause
