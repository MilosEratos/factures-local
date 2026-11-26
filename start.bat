@echo off
title Factures Local
echo.
echo  === Factures Local - demarrage ===
echo.
echo  Le moteur IA se demarre en arriere-plan (meme console).
echo  Fermer cette fenetre arrete tout, moteur IA inclus.
echo.

REM Lancer llama-server en arriere-plan, dans la meme console,
REM sortie redirigee vers un log (pas de warnings a l'ecran).
start /b "" "%~dp0llama.cpp\llama-server.exe" -m "%~dp0models\Qwen3.5-4B-Q4_K_M.gguf" -ngl 99 --port 8081 --no-webui --reasoning off > "%~dp0llama.log" 2>&1

REM Lancer l'application web (elle attend que le moteur IA soit pret).
if exist "%~dp0python\python.exe" (
    "%~dp0python\python.exe" "%~dp0server.py"
) else (
    python "%~dp0server.py"
)

echo.
echo  Factures Local est arrete.
