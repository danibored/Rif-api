@echo off
setlocal enabledelabledelayedexpansion
title GESTOR RIF AUTOMATION (n8n + FastAPI + DB)
color 0B


docker --version >nul 2>&1
if %errorlevel% neq 0 (
    cls
    color 0E
    echo ======================================================
    echo       INSTALACION DE MOTOR DE AUTOMATIZACION
    echo ======================================================
    echo [!] Docker no ha sido detectado en este sistema.
    echo.
    echo 1. Se abrira el instalador incluido en la carpeta.
    echo 2. Sigue las instrucciones (deja todo por defecto).
    echo 3. Al finalizar, REINICIA el equipo y vuelve a abrir este script.
    echo ======================================================
    if exist "Docker Desktop Installer.exe" (
        pause
        start "" "Docker Desktop Installer.exe"
    ) else (
        echo [ERROR] No se encontro el instalador en esta carpeta.
        pause
    )
    exit
)

docker info >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Docker Desktop esta instalado pero NO esta abierto.
    echo Por favor, abre Docker Desktop y espera a que inicie.
    pause
    exit
)

:menu
cls
color 0B
echo ======================================================
echo    SISTEMA UNIFICADO RIF (n8n + API + DB + REDIS)
echo ======================================================
echo  1. Iniciar Todo el Sistema (Modo Segundo Plano)
echo  2. Detener Sistema (Cierre seguro)
echo  3. Ver Logs en Tiempo Real (Todo el sistema)
echo  4. Actualizar / Reconstruir (Cambios en Dockerfiles)
echo  5. CREAR BACKUP TOTAL (Datos + Codigo + Config)
echo  6. Reiniciar Servicios
echo  7. Salir
echo ======================================================
set /p opt="Selecciona una opcion (1-7): "

if "%opt%"=="1" goto start
if "%opt%"=="2" goto stop
if "%opt%"=="3" goto logs
if "%opt%"=="4" goto update
if "%opt%"=="5" goto backup
if "%opt%"=="6" goto restart
if "%opt%"=="7" goto exit
goto menu

:start
echo [INFO] Levantando el ecosistema...
docker compose up -d
echo.
echo ======================================================
echo [OK] SERVICIOS ACTIVOS:
echo [>] n8n: http://localhost:5678
echo [>] API RIF: http://localhost:8000/docs
echo ======================================================
pause
goto menu

:stop
echo [INFO] Deteniendo todos los servicios...
docker compose stop
echo [OK] Servicios detenidos.
pause
goto menu

:logs
echo [INFO] Viendo logs de todos los servicios. 
echo [CONSEJO] Si ves errores rojos, revisa la conexion a la DB.
echo Presiona Ctrl+C para volver al menu.
echo.

docker compose logs -f
goto menu

:update
echo [INFO] Reconstruyendo imagenes (esto aplicara cambios en tus Dockerfiles)...
docker compose down --remove-orphans
docker compose up -d --build
echo [OK] Sistema actualizado y reconstruido.
pause
goto menu

:backup
echo [INFO] Creando copia de seguridad completa...
set "fecha=%date:~-4%-%date:~4,2%-%date:~7,2%"
set "hora=%time:~0,2%-%time:~3,2%"
set "folder=backups\backup_%fecha%_%hora: =0%"

if not exist "backups" mkdir backups
mkdir "%folder%"

echo [INFO] Respaldando carpetas de datos...
if exist "n8n_data" xcopy /E /I /Y "n8n_data" "%folder%\n8n_data" >nul
if exist "postgres_data" xcopy /E /I /Y "postgres_data" "%folder%\postgres_data" >nul

echo [INFO] Respaldando archivos de configuracion y codigo...
copy ".env" "%folder%\" >nul
copy "docker-compose.yml" "%folder%\" >nul
copy "Dockerfile" "%folder%\" >nul
copy "Dockerfile.fastapi" "%folder%\" >nul
copy "main.py" "%folder%\" >nul
copy "requirements.txt" "%folder%\" >nul

echo [OK] Backup guardado en: %folder%
pause
goto menu

:restart
echo [INFO] Reiniciando servicios...
docker compose restart
echo [OK] Servicios reiniciados con exito.
pause
goto menu

:exit
exit