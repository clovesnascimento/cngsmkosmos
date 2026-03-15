@echo off
:: ============================================================
::  KOSMOS — Verificacao pos-instalacao Docker no D:\
::  Execute APOS reiniciar e abrir o Docker Desktop
:: ============================================================
setlocal EnableDelayedExpansion

for /f %%a in ('echo prompt $E ^| cmd') do set "ESC=%%a"
set "GREEN=%ESC%[92m"
set "YELLOW=%ESC%[93m"
set "RED=%ESC%[91m"
set "CYAN=%ESC%[96m"
set "BOLD=%ESC%[1m"
set "RESET=%ESC%[0m"

echo.
echo %BOLD%%CYAN%============================================================%RESET%
echo %BOLD%   KOSMOS — Verificacao Docker D:\ %RESET%
echo %BOLD%%CYAN%============================================================%RESET%
echo.

:: 1. Docker respondendo?
echo %CYAN%[1/4] Testando Docker daemon...%RESET%
docker ps >nul 2>&1
if %errorLevel% equ 0 (
    echo   %GREEN%[OK]%RESET% Docker daemon esta rodando
) else (
    echo   %RED%[FALHA]%RESET% Docker nao responde.
    echo   Certifique-se que o Docker Desktop esta aberto e com status verde.
    pause
    exit /b 1
)

:: 2. WSL distros no D:?
echo.
echo %CYAN%[2/4] Verificando localizacao das distros WSL...%RESET%
wsl --list --verbose
echo.
if exist "D:\Docker\WSL\" (
    echo   %GREEN%[OK]%RESET% Diretorio D:\Docker\WSL\ existe
    dir /b "D:\Docker\WSL\" 2>nul
) else (
    echo   %YELLOW%[AVISO]%RESET% D:\Docker\WSL\ nao encontrado
    echo   O Docker Desktop pode ter recriado as distros em local padrao.
)

:: 3. Espaco em C: vs D:
echo.
echo %CYAN%[3/4] Espaco em disco...%RESET%
echo   C:\ livre:
for /f "tokens=3" %%a in ('dir C:\ /-c 2^>nul ^| findstr /i "bytes free"') do echo     %%a bytes
echo   D:\ livre:
for /f "tokens=3" %%a in ('dir D:\ /-c 2^>nul ^| findstr /i "bytes free"') do echo     %%a bytes

:: 4. Teste hello-world
echo.
echo %CYAN%[4/4] Rodando teste docker hello-world...%RESET%
docker run --rm hello-world >nul 2>&1
if %errorLevel% equ 0 (
    echo   %GREEN%[OK]%RESET% hello-world executou com sucesso!
) else (
    echo   %YELLOW%[AVISO]%RESET% hello-world falhou. Verifique conexao com internet.
)

echo.
echo %BOLD%%GREEN%Verificacao concluida!%RESET%
echo.
echo Agora rode no projeto KOSMOS:
echo   %CYAN%cd D:\FIRECRACKER\kosmos_agent%RESET%
echo   %CYAN%python preflight_check.py%RESET%
echo.
pause
