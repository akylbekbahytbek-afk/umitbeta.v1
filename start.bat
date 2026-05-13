@echo off
title Онко-чат ИИ - Система запуска
color 0F

cls
echo ================================
echo    СИСТЕМА ПОДДЕРЖКИ ОНКОПАЦИЕНТОВ
echo         ЗАПУСК ВСЕХ КОМПОНЕНТОВ
echo ================================
echo.

:: Проверяем Python
echo [1/4] Проверка Python...
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
echo [2/4] Проверка Ollama...
curl -s http://localhost:11434/api/tags >nul 2>&1
if %errorlevel% equ 0 (
    echo ✓ Ollama запущен
) else (
    echo × Ollama не запущен!
    echo Запустите Ollama вручную и повторите попытку
    pause
    exit /b
)

:: Проверяем зависимости
echo [3/4] Проверка зависимостей...
if exist "requirements.txt" (
    pip show flask >nul 2>&1
    if %errorlevel% equ 0 (
        echo ✓ Зависимости установлены
    ) else (
        echo × Зависимости не установлены!
        echo Устанавливаем зависимости...
        pip install -r requirements.txt
        if %errorlevel% equ 0 (
            echo ✓ Зависимости установлены успешно
        ) else (
            echo × Ошибка установки зависимостей!
            pause
            exit /b
        )
    )
)

:: Получаем локальный IP
echo [4/4] Получение сетевого адреса...
for /f "tokens=2 delims=[]" %%a in ('ping -4 -n 1 %ComputerName% ^| findstr "["') do set NetworkIP=%%a
if defined NetworkIP (
    echo ✓ Ваш IP адрес: %NetworkIP%
    echo Доступ с других устройств: http://%NetworkIP%:5000
) else (
    echo Локальный адрес: 127.0.0.1
)

echo.
echo ================================
echo ГОТОВО! Запускаем сервер...
echo ================================
echo.
echo Открываем браузер...
start http://localhost:5000

echo.
echo Сервер запущен на http://localhost:5000
echo Нажмите Ctrl+C для остановки
echo.

:: Запускаем Flask с правильными настройками
python -c "import app; app.app.run(debug=True, host='0.0.0.0', port=5000)"

pause
