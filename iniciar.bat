@echo off
REM SkillMatrix - arranque en Windows
cd /d "%~dp0"
if not exist .env (
    copy .env.example .env >nul
    echo.
    echo  Se ha creado el archivo .env. Abrelo, pon los datos de conexion a PostgreSQL
    echo  en DATABASE_URL y vuelve a ejecutar iniciar.bat.
    echo.
    notepad .env
    pause
    exit /b 0
)
if not exist .venv (
    echo Creando entorno virtual...
    python -m venv .venv || (echo No se encuentra Python. Instalalo desde https://www.python.org/downloads/ & pause & exit /b 1)
    .venv\Scripts\python -m pip install --upgrade pip >nul
    .venv\Scripts\pip install -r requirements.txt || (pause & exit /b 1)
)
start "" http://localhost:5000
.venv\Scripts\python app.py
pause
