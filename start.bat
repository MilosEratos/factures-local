@echo off
title Factures Local
echo.
echo  === Factures Local — demarrage ===
echo.

REM 1. Lancer llama-server (IA locale)
echo  [1/2] Demarrage du moteur IA (llama-server)...
start /min "llama-server" llama.cpp\llama-server.exe -m models\qwen3.5-4b-q4_k_m.gguf -ngl 99 --port 8081 --no-webui --reasoning off

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
echo   ============================================
echo.

start http://localhost:5000
python server.py
