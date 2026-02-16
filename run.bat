@echo off
cd /d "%~dp0"
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo Erstelle virtuelle Umgebung...
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
)
python src\main.py %*
