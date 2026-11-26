@echo off
title Factures Local
echo.
echo  === Factures Local — demarrage ===
echo.

set "ROOT=%~dp0"

REM 1. Lancer llama-server (IA locale)
echo  [1/2] Demarrage du moteur IA (llama-server)...
start /min "llama-server" "%ROOT%llama.cpp\llama-server.exe" -m "%ROOT%models\Qwen3.5-4B-Q4_K_M.gguf" -ngl 99 --port 8081 --no-webui --reasoning off -c 2048

REM Attendre que le modele soit charge
echo        Attente du chargement du modele...
timeout /t 15 /nobreak >nul

REM 2. Lancer l'application web
echo  [2/2] Demarrage de l'application web...
echo.
echo  ============================================
echo   L'application est prete !
echo   Ouvrez : http://localhost:5000
echo.
echo   Pour arreter : fermer cette fenetre
echo  ============================================
echo.

start http://localhost:5000

REM Utiliser le Python embarque s'il existe, sinon le Python systeme
if exist "%ROOT%python\python.exe" (
    "%ROOT%python\python.exe" "%ROOT%server.py"
) else (
    python "%ROOT%server.py"
)
