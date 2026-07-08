@echo off
REM ==========================================================================
REM  QuickDock - script de build do executavel (.exe) com PyInstaller
REM ==========================================================================
REM  Gera dist\QuickDock.exe (arquivo unico, sem console).
REM  Os dados (settings + atalhos) ficam em %APPDATA%\QuickDock, entao
REM  atualizar/substituir o .exe NAO apaga seus atalhos.
REM  (Para versao portatil, crie um "portable.txt" ao lado do .exe.)
REM
REM  Este script NUNCA apaga seus atalhos:
REM   - faz um BACKUP automatico em backups\ antes de compilar;
REM   - NAO apaga a pasta dist\ inteira (preserva dist\data do modo portatil).
REM  Dica: feche o QuickDock antes de rodar o build.
REM ==========================================================================

setlocal
cd /d "%~dp0"

REM --- [0/4] Backup de seguranca dos atalhos -------------------------------
echo [0/4] Fazendo backup dos atalhos...
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HH-mm-ss"') do set "STAMP=%%i"
set "BKP=backups\%STAMP%"

if exist "%APPDATA%\QuickDock\shortcuts.json" (
  if not exist "%BKP%" mkdir "%BKP%"
  copy /y "%APPDATA%\QuickDock\shortcuts.json" "%BKP%\" >nul
  if exist "%APPDATA%\QuickDock\settings.json" copy /y "%APPDATA%\QuickDock\settings.json" "%BKP%\" >nul
  echo   Backup salvo em: %BKP%
)
if exist "dist\data\shortcuts.json" (
  if not exist "%BKP%" mkdir "%BKP%"
  copy /y "dist\data\*.json" "%BKP%\" >nul
  echo   Backup do modo portatil salvo em: %BKP%
)
if not exist "%BKP%" echo   Nenhum atalho encontrado ainda - nada a salvar.

echo [1/4] Instalando dependencias...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :erro

REM --- [2/4] Limpeza: apenas arquivos temporarios do build ----------------
REM  NAO apagamos a pasta dist\ inteira, para preservar dist\data (portatil).
echo [2/4] Limpando temporarios do build...
if exist build rmdir /s /q build
if exist QuickDock.spec del /q QuickDock.spec

echo [3/4] Gerando executavel...
pyinstaller ^
  --name QuickDock ^
  --onefile ^
  --noconsole ^
  --hidden-import win32gui ^
  --hidden-import win32ui ^
  --hidden-import win32con ^
  --collect-all customtkinter ^
  main.py
if errorlevel 1 goto :erro

echo.
echo ==========================================================
echo  [4/4] Concluido!  Executavel em:  dist\QuickDock.exe
echo  Seus atalhos continuam em: %APPDATA%\QuickDock
echo  Backup desta build em:     %BKP%
echo ==========================================================
echo.
pause
goto :fim

:erro
echo.
echo *** Ocorreu um erro durante o build. ***
echo Verifique a mensagem acima. Causas comuns:
echo   - Python nao esta instalado ou nao esta no PATH.
echo     Instale em https://python.org e marque "Add Python to PATH".
echo   - Sem internet para baixar as dependencias.
echo.
pause
exit /b 1

:fim
endlocal
