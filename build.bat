@echo off
REM Gera o executavel standalone (dist\LightNovelTranslator.exe).
REM Quem usa o .exe nao precisa instalar Python - so o Ollama.
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo ERRO: Python nao encontrado no PATH.
    echo Instale em https://python.org marcando "Add Python to PATH".
    pause
    exit /b 1
)

echo [1/3] Instalando dependencias...
python -m pip install --upgrade pyinstaller
if errorlevel 1 goto :falha
python -m pip install -r requirements.txt
if errorlevel 1 goto :falha

echo [2/3] Empacotando (pode levar alguns minutos)...
REM "python -m PyInstaller" evita o problema classico do comando
REM "pyinstaller" nao estar no PATH do Windows.
python -m PyInstaller --noconfirm --onefile --windowed ^
    --name LightNovelTranslator main.py
if errorlevel 1 goto :falha

echo [3/3] Verificando resultado...
if exist "dist\LightNovelTranslator.exe" (
    echo.
    echo PRONTO: dist\LightNovelTranslator.exe
) else (
    goto :falha
)
pause
exit /b 0

:falha
echo.
echo FALHOU - role para cima e procure a primeira linha de erro.
echo Causas comuns: antivirus bloqueando o PyInstaller (adicione excecao
echo para esta pasta) ou falta de internet para o pip.
pause
exit /b 1
