@echo off
setlocal
chcp 65001 >nul
title Esteira - contador de comprimidos
cd /d "%~dp0"

rem Uso: run.bat [camera]   (padrao 2 = Iriun no PC do Vinicius; 0 = webcam)
set "SOURCE=%~1"
if "%SOURCE%"=="" set "SOURCE=2"

set "PY=py -3.12"
%PY% --version >nul 2>&1
if errorlevel 1 (
    set "PY=python"
    python --version >nul 2>&1
    if errorlevel 1 (
        echo [ERRO] Python nao encontrado. Instale o Python 3.12: https://www.python.org/downloads/
        pause
        exit /b 1
    )
)

where node >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Node.js nao encontrado. Instale o Node LTS: https://nodejs.org/
    pause
    exit /b 1
)

%PY% -c "import ultralytics, fastapi, uvicorn, cv2" >nul 2>&1
if errorlevel 1 (
    echo Instalando dependencias do YOLO ^(so na primeira vez neste PC^)...
    %PY% -m pip install -r requirements-yolo.txt
    if errorlevel 1 (
        echo [ERRO] Falha ao instalar as dependencias.
        pause
        exit /b 1
    )
)

echo Iniciando servico YOLO (camera %SOURCE%) na porta 8765...
start "Esteira - YOLO" cmd /k %PY% scripts\run_yolo_service.py --source %SOURCE% --direction rtl --lite

echo Iniciando interface na porta 8080...
start "Esteira - Interface" cmd /k node server.mjs --http

echo Aguardando o servico carregar o modelo...
timeout /t 10 /nobreak >nul
start "" http://localhost:8080

echo.
echo Pronto: http://localhost:8080 ^> Conectar YOLO. Troque camera/video no botao Fonte.
echo Para parar, feche as janelas "Esteira - YOLO" e "Esteira - Interface".
timeout /t 8 >nul
