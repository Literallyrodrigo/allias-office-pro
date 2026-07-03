@echo off

pyinstaller ^
--onefile ^
--windowed ^
--icon=assets/icon.ico ^
--name "AlliasOfficePRO" ^
--version-file version.txt ^
--add-data "assets;assets" ^
src/main.py

pause