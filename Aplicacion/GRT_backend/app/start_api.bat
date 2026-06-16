bat@echo off
cd /d C:\Users\clarobot\Desktop\GRT v2\Aplicacion\GRT_backend\app
call venv\Scripts\activate.bat
uvicorn main:app --host 127.0.0.1 --port 8001
