@echo off
title Онко-Чат ИИ - Полный запуск
color 0A

echo ================================
echo ЗАПУСК ОНКО-ЧАТА С ИИ
echo ================================
echo.

:: Проверяем Python
echo [1/5] Проверка Python...
python --version >nul 2>&1
if %errorlevel% equ 0 (
    echo ✓ Python найден
) else (
    echo × Python не найден!
    echo Установите Python с python.org
    pause
    exit /b
)

:: Проверяем Ollama
echo [2/5] Проверка Ollama...
curl -s http://localhost:11434/api/tags >nul 2>&1
if %errorlevel% equ 0 (
    echo ✓ Ollama запущен
) else (
    echo × Ollama не запущен!
    echo Запустите Ollama вручную
    pause
    exit /b
)

:: Проверяем зависимости
echo [3/5] Проверка зависимостей...
if exist "requirements.txt" (
    pip show flask >nul 2>&1
    if %errorlevel% equ 0 (
        echo ✓ Зависимости установлены
    ) else (
        echo × Установка зависимостей...
        pip install -r requirements.txt
        if %errorlevel% equ 0 (
            echo ✓ Зависимости установлены
        ) else (
            echo × Ошибка установки зависимостей!
            pause
            exit /b
        )
    )
)

:: Проверяем ngrok
echo [4/5] Проверка ngrok...
if exist "C:\Users\Admin\Downloads\ngrok-v3-stable-windows-amd64\ngrok.exe" (
    echo ✓ ngrok найден
    set NGROK_PATH="C:\Users\Admin\Downloads\ngrok-v3-stable-windows-amd64\ngrok.exe"
) else if exist "ngrok.exe" (
    echo ✓ ngrok найден в текущей папке
    set NGROK_PATH="ngrok.exe"
) else (
    echo × ngrok не найден!
    echo Скачайте ngrok с https://ngrok.com/download
    pause
    exit /b
)

:: Получаем IP
echo [5/5] Получение IP адреса...
for /f "tokens=2 delims=[]" %%a in ('ping -4 -n 1 %ComputerName% ^| findstr "["') do set NetworkIP=%%a

echo.
echo ================================
echo ЗАПУСК СЕРВЕРА И NGROK
echo ================================
echo.

if defined NetworkIP (
    echo Локальный адрес: http://%NetworkIP%:5000
) else (
    echo Локальный адрес: http://localhost:5000
)

echo.
echo Запуск сервера в фоне...
start "Сервер" /min cmd /c "python run_server.py ^> server.log 2^>^&1"

echo Ожидание запуска сервера...
timeout /t 5 /nobreak >nul

echo.
echo Запуск ngrok...
start "ngrok" cmd /c %NGROK_PATH% http 127.0.0.1:5000

echo.
echo Открываем локальный адрес...
timeout /t 3 /nobreak >nul
start http://localhost:5000

echo.
echo ================================
echo ГОТОВО! Сервер запущен!
echo ================================
echo.
echo Локально: http://localhost:5000
if defined NetworkIP echo В сети: http://%NetworkIP%:5000
echo Через интернет: см. окно ngrok
echo.
echo Для остановки закройте все окна команд
echo.

pause
