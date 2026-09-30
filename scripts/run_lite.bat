@echo off
REM Esteira YOLO — modo LITE (Galaxy Book S / 8 GB RAM)
cd /d "%~dp0.."
echo.
echo === Esteira YOLO LITE ===
echo Feche apps pesados. Deixe so este terminal + o browser da UI.
echo.
py -3.12 scripts/run_yolo_service.py --source 0 --direction rtl --lite
pause
