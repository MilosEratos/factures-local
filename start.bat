@echo off
title Factures Local
echo.
echo  === Factures Local - demarrage ===
echo.
echo  Le moteur IA se demarre en arriere-plan (meme console).
echo  Fermer cette fenetre arrete tout, moteur IA inclus.
echo.

start /b "" "%~dp0llama.cpp\llama-server.exe" -m "%~dp0models\Qwen3.5-4B-Q4_K_M.gguf" -ngl 99 --port 8081 --no-webui --reasoning off

if exist "%~dp0python\python.exe" (
    "%~dp0python\python.exe" "%~dp0server.py"
) else (
    python "%~dp0server.py"
)

echo.
echo  Factures Local est arrete.
