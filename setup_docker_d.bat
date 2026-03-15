@echo off
:: ============================================================
::  KOSMOS — Docker Desktop + WSL2 no Drive D:\
::  Script de Setup Completo
::  Autor: CNGSM CODE
::  Uso: Clique com botao direito → "Executar como Administrador"
:: ============================================================
setlocal EnableDelayedExpansion

:: Cores ANSI (funciona no Windows 10+)
for /f %%a in ('echo prompt $E ^| cmd') do set "ESC=%%a"
set "GREEN=%ESC%[92m"
set "YELLOW=%ESC%[93m"
set "RED=%ESC%[91m"
set "CYAN=%ESC%[96m"
set "BOLD=%ESC%[1m"
set "RESET=%ESC%[0m"

echo.
echo %BOLD%%CYAN%============================================================%RESET%
echo %BOLD%   KOSMOS — Docker Desktop Setup ^| WSL2 no D:\%RESET%
echo %BOLD%%CYAN%============================================================%RESET%
echo.

:: ─── VERIFICACAO DE ADMIN ───────────────────────────────────
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo %RED%[ERRO] Execute como Administrador!%RESET%
    echo       Clique direito no arquivo ^> "Executar como Administrador"
    pause
    exit /b 1
)
echo %GREEN%[OK]%RESET% Executando como Administrador

:: ─── VERIFICACAO DO DRIVE D ─────────────────────────────────
if not exist "D:\" (
    echo %RED%[ERRO] Drive D:\ nao encontrado!%RESET%
    pause
    exit /b 1
)

:: Verifica espaco livre no D: (precisa de pelo menos 10GB)
for /f "tokens=3" %%a in ('dir D:\ /-c ^| findstr /i "bytes free"') do set FREE_BYTES=%%a
echo %GREEN%[OK]%RESET% Drive D:\ encontrado

:: ─── CRIA ESTRUTURA DE DIRETORIOS ───────────────────────────
echo.
echo %CYAN%[1/6] Criando estrutura de diretorios em D:\...%RESET%

set "DOCKER_ROOT=D:\Docker"
set "WSL_DIR=%DOCKER_ROOT%\WSL"
set "DATA_DIR=%DOCKER_ROOT%\Data"
set "BACKUP_DIR=%DOCKER_ROOT%\Backup"

for %%d in ("%DOCKER_ROOT%" "%WSL_DIR%" "%DATA_DIR%" "%BACKUP_DIR%") do (
    if not exist "%%~d" (
        mkdir "%%~d"
        echo   Criado: %%~d
    ) else (
        echo   Ja existe: %%~d
    )
)
echo %GREEN%[OK]%RESET% Estrutura criada em %DOCKER_ROOT%

:: ─── HABILITA WSL2 ──────────────────────────────────────────
echo.
echo %CYAN%[2/6] Habilitando WSL2 e Hyper-V...%RESET%

dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart >nul 2>&1
if %errorLevel% equ 0 (
    echo   %GREEN%[OK]%RESET% WSL habilitado
) else (
    echo   %YELLOW%[AVISO]%RESET% WSL ja estava habilitado ou erro ignoravel
)

dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart >nul 2>&1
if %errorLevel% equ 0 (
    echo   %GREEN%[OK]%RESET% Virtual Machine Platform habilitado
) else (
    echo   %YELLOW%[AVISO]%RESET% VMP ja estava habilitado
)

:: Define WSL2 como padrao
wsl --set-default-version 2 >nul 2>&1
echo   %GREEN%[OK]%RESET% WSL2 definido como versao padrao

:: ─── VERIFICA SE DOCKER DESKTOP JA ESTA INSTALADO ──────────
echo.
echo %CYAN%[3/6] Verificando Docker Desktop...%RESET%

set "DOCKER_INSTALLED=0"
set "DOCKER_EXE="

:: Verifica paths comuns
for %%p in (
    "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    "%LOCALAPPDATA%\Programs\Docker\Docker\Docker Desktop.exe"
) do (
    if exist "%%~p" (
        set "DOCKER_INSTALLED=1"
        set "DOCKER_EXE=%%~p"
    )
)

if "%DOCKER_INSTALLED%"=="1" (
    echo   %GREEN%[OK]%RESET% Docker Desktop encontrado: %DOCKER_EXE%
    echo   %YELLOW%[INFO]%RESET% Certifique-se que o Docker Desktop esta FECHADO antes de continuar
    echo.
    echo   Pressione qualquer tecla quando o Docker Desktop estiver fechado...
    pause >nul
) else (
    echo   %YELLOW%[AVISO]%RESET% Docker Desktop nao encontrado.
    echo.
    echo   %BOLD%Voce precisa instalar o Docker Desktop primeiro:%RESET%
    echo   1. Acesse: %CYAN%https://www.docker.com/products/docker-desktop/%RESET%
    echo   2. Baixe o instalador para Windows
    echo   3. Instale normalmente (vai para C:\ — isso e esperado)
    echo   4. %YELLOW%NAO inicie o Docker Desktop ainda%RESET%
    echo   5. Execute este script novamente
    echo.
    echo   %CYAN%Abrindo pagina de download...%RESET%
    start https://www.docker.com/products/docker-desktop/
    pause
    exit /b 0
)

:: ─── MIGRA WSL PARA D:\ ─────────────────────────────────────
echo.
echo %CYAN%[4/6] Migrando distros WSL para D:\Docker\WSL\...%RESET%
echo   %YELLOW%Isso pode demorar alguns minutos dependendo do tamanho...%RESET%
echo.

:: Lista distros existentes
echo   Distros WSL encontradas:
wsl --list --verbose 2>nul
echo.

:: Migra docker-desktop
echo   Exportando docker-desktop...
wsl --export docker-desktop "%BACKUP_DIR%\docker-desktop.tar" >nul 2>&1
if %errorLevel% equ 0 (
    echo   %GREEN%[OK]%RESET% docker-desktop exportado ^(%BACKUP_DIR%\docker-desktop.tar^)
    
    wsl --unregister docker-desktop >nul 2>&1
    echo   %GREEN%[OK]%RESET% docker-desktop removido do C:\
    
    wsl --import docker-desktop "%WSL_DIR%\docker-desktop" "%BACKUP_DIR%\docker-desktop.tar" --version 2
    if !errorLevel! equ 0 (
        echo   %GREEN%[OK]%RESET% docker-desktop importado em D:\Docker\WSL\docker-desktop
    ) else (
        echo   %RED%[ERRO]%RESET% Falha ao importar docker-desktop
    )
) else (
    echo   %YELLOW%[AVISO]%RESET% docker-desktop nao encontrado ^(sera criado pelo Docker Desktop^)
)

:: Migra docker-desktop-data (onde ficam as imagens — mais importante!)
echo.
echo   Exportando docker-desktop-data ^(imagens e containers^)...
wsl --export docker-desktop-data "%BACKUP_DIR%\docker-desktop-data.tar" >nul 2>&1
if %errorLevel% equ 0 (
    echo   %GREEN%[OK]%RESET% docker-desktop-data exportado
    
    wsl --unregister docker-desktop-data >nul 2>&1
    echo   %GREEN%[OK]%RESET% docker-desktop-data removido do C:\
    
    wsl --import docker-desktop-data "%WSL_DIR%\docker-desktop-data" "%BACKUP_DIR%\docker-desktop-data.tar" --version 2
    if !errorLevel! equ 0 (
        echo   %GREEN%[OK]%RESET% docker-desktop-data importado em D:\Docker\WSL\docker-desktop-data
    ) else (
        echo   %RED%[ERRO]%RESET% Falha ao importar docker-desktop-data
    )
) else (
    echo   %YELLOW%[AVISO]%RESET% docker-desktop-data nao encontrado ^(normal na 1a instalacao^)
)

:: ─── CONFIGURA DOCKER DESKTOP PARA D:\ ──────────────────────
echo.
echo %CYAN%[5/6] Configurando Docker Desktop para usar D:\...%RESET%

:: Cria/atualiza settings.json do Docker Desktop
set "DOCKER_CONFIG=%APPDATA%\Docker"
if not exist "%DOCKER_CONFIG%" mkdir "%DOCKER_CONFIG%"

echo {> "%DOCKER_CONFIG%\settings.json"
echo   "wslEngineEnabled": true,>> "%DOCKER_CONFIG%\settings.json"
echo   "wslDistroDataDirectory": "D:\\Docker\\WSL\\docker-desktop-data",>> "%DOCKER_CONFIG%\settings.json"
echo   "diskSizeMb": 102400,>> "%DOCKER_CONFIG%\settings.json"
echo   "diskPath": "D:\\Docker\\Data\\docker.raw",>> "%DOCKER_CONFIG%\settings.json"
echo   "autoStart": false,>> "%DOCKER_CONFIG%\settings.json"
echo   "buildkitForCompose": true>> "%DOCKER_CONFIG%\settings.json"
echo }>> "%DOCKER_CONFIG%\settings.json"

echo   %GREEN%[OK]%RESET% settings.json configurado em %DOCKER_CONFIG%

:: ─── CRIA ARQUIVO .wslconfig ────────────────────────────────
echo.
echo   Configurando .wslconfig para limitar uso de RAM...

set "WSLCONFIG=%USERPROFILE%\.wslconfig"
echo [wsl2]> "%WSLCONFIG%"
echo memory=4GB>> "%WSLCONFIG%"
echo processors=2>> "%WSLCONFIG%"
echo swap=2GB>> "%WSLCONFIG%"
echo swapFile=D:\Docker\swap.vhdx>> "%WSLCONFIG%"
echo localhostForwarding=true>> "%WSLCONFIG%"

echo   %GREEN%[OK]%RESET% .wslconfig criado ^(RAM: 4GB, CPUs: 2, Swap: D:\Docker\swap.vhdx^)

:: ─── VERIFICACAO FINAL ───────────────────────────────────────
echo.
echo %CYAN%[6/6] Verificacao final...%RESET%
echo.

echo   Estrutura criada em D:\Docker\:
dir /b "%DOCKER_ROOT%" 2>nul | findstr /v "^$" | (for /f %%i in ('more') do echo     %%i)

echo.
echo   Distros WSL configuradas:
wsl --list --verbose 2>nul

:: ─── INSTRUCOES FINAIS ───────────────────────────────────────
echo.
echo %BOLD%%GREEN%============================================================%RESET%
echo %BOLD%%GREEN%  Setup concluido!%RESET%
echo %BOLD%%GREEN%============================================================%RESET%
echo.
echo %BOLD%Proximos passos:%RESET%
echo.
echo   1. %CYAN%Reinicie o computador%RESET% ^(necessario para WSL2^)
echo.
echo   2. Apos reiniciar, abra o Docker Desktop
echo      • Ele vai reconfigurar as distros automaticamente
echo      • Aguarde o status ficar verde ^("Running"^)
echo.
echo   3. Teste no terminal:
echo      %CYAN%docker ps%RESET%
echo      %CYAN%docker run hello-world%RESET%
echo.
echo   4. Volte ao projeto e rode:
echo      %CYAN%python preflight_check.py%RESET%
echo.
echo %YELLOW%Estrutura final em D:\:%RESET%
echo   D:\Docker\
echo   ├── WSL\
echo   │   ├── docker-desktop\        ^(distro WSL do Docker^)
echo   │   └── docker-desktop-data\   ^(imagens e containers^)
echo   ├── Data\
echo   │   └── docker.raw             ^(disco virtual^)
echo   ├── Backup\                    ^(tars de backup — pode apagar depois^)
echo   └── swap.vhdx                  ^(swap do WSL2^)
echo.
echo %YELLOW%Nota:%RESET% Os backups em D:\Docker\Backup\ podem ser deletados
echo       apos confirmar que o Docker esta funcionando.
echo.

set /p RESTART="Deseja reiniciar agora? (s/n): "
if /i "%RESTART%"=="s" (
    echo Reiniciando em 10 segundos... Pressione Ctrl+C para cancelar.
    shutdown /r /t 10 /c "KOSMOS Setup: reiniciando para finalizar configuracao WSL2"
) else (
    echo Lembre-se de reiniciar antes de usar o Docker!
)

pause
