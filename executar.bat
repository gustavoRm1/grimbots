@echo off
chcp 65001 >nul
echo.
echo ============================================================
echo    BOT MANAGER SAAS - EXECUTAR
echo ============================================================
echo.
echo Parando processos anteriores...
taskkill /F /IM python.exe >nul 2>&1

timeout /t 2 /nobreak >nul

echo Iniciando servidor Flask...
echo.
call venv\Scripts\activate
python app.py



