@echo off
title Factures Local
echo.
echo  === Factures Local - demarrage ===
echo.
echo  Le moteur IA se charge en arriere-plan (sans fenetre).
echo  Fermer cette fenetre arrete tout.
echo.

REM Utiliser le Python embarque s'il existe, sinon le Python systeme
if exist "%~dp0python\python.exe" (
    "%~dp0python\python.exe" "%~dp0server.py"
) else (
    python "%~dp0server.py"
)

echo.
echo  Factures Local est arrete.
