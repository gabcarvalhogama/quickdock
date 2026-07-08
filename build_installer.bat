@echo off
REM ==========================================================================
REM  QuickDock - gera o INSTALADOR (dist\installer\QuickDockSetup.exe)
REM ==========================================================================
REM  Pre-requisitos:
REM   1) dist\QuickDock.exe ja compilado  -> rode build.bat antes.
REM   2) Inno Setup 6 instalado           -> https://jrsoftware.org/isdl.php
REM                                          (ou: winget install JRSoftware.InnoSetup)
REM
REM  Este script apenas EMPACOTA o .exe num instalador; nao recompila o Python.
REM ==========================================================================

setlocal
cd /d "%~dp0"

REM --- [1/2] Verifica se o executavel existe -------------------------------
if not exist "dist\QuickDock.exe" (
  echo [ERRO] dist\QuickDock.exe nao encontrado.
  echo Rode build.bat primeiro para gerar o executavel.
  pause
  exit /b 1
)

REM --- Localiza o compilador do Inno Setup (ISCC.exe) ----------------------
set "ISCC="
for %%p in (
  "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
  "%ProgramFiles%\Inno Setup 6\ISCC.exe"
  "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
) do if exist "%%~p" set "ISCC=%%~p"

if not defined ISCC (
  for /f "delims=" %%i in ('where ISCC.exe 2^>nul') do set "ISCC=%%i"
)

if not defined ISCC (
  echo [ERRO] Inno Setup nao encontrado.
  echo Instale em: https://jrsoftware.org/isdl.php
  echo   ou pelo terminal:  winget install JRSoftware.InnoSetup
  pause
  exit /b 1
)

REM --- [2/2] Compila o instalador ------------------------------------------
echo [2/2] Gerando instalador com:
echo    %ISCC%
"%ISCC%" installer.iss
if errorlevel 1 goto :erro

echo.
echo ==========================================================
echo  Concluido!  Instalador em:  dist\installer\QuickDockSetup.exe
echo ==========================================================
echo.
pause
goto :fim

:erro
echo.
echo *** Ocorreu um erro ao compilar o instalador. ***
pause
exit /b 1

:fim
endlocal
