@echo off
setlocal
title Factures Local
echo.
echo  === Factures Local - demarrage ===
echo.

set "ROOT=%~dp0"

REM Detecter le modele .gguf dans le dossier models
set "MODEL_FILE="
for %%f in ("%ROOT%models\*.gguf") do set "MODEL_FILE=%%f"
if "%MODEL_FILE%"=="" (
    echo  [ERREUR] Aucun modele trouve dans le dossier models\
    echo  Lancez install.bat d'abord.
    pause
    exit /b 1
)
echo  [0/2] Modele detecte : %MODEL_FILE%

REM 1. Lancer llama-server (IA locale)
echo  [1/2] Demarrage du moteur IA (llama-server)...
start /min "llama-server" "%ROOT%llama.cpp\llama-server.exe" -m "%MODEL_FILE%" -ngl 99 --port 8081 --no-webui --reasoning off -c 2048

REM Attendre que le modele soit charge (boucle sur le port 8081)
echo        Attente du chargement du modele...
set "TRY=0"
:wait_llama
powershell -NoProfile -Command "try{$c=New-Object Net.Sockets.TcpClient;$c.Connect('127.0.0.1',8081);$c.Close();exit 0}catch{exit 1}" >nul 2>&1
if %errorlevel%==0 goto :llama_ready
set /a TRY+=1
if %TRY% GEQ 120 (
    echo        Erreur: llama-server n'a pas demarre dans le delai.
    echo        Verifiez que le modele est present dans le dossier models\
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto :wait_llama
:llama_ready
echo        Modele charge.

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

REM Ouvrir le navigateur en fond des que Flask sera pret
start "" /min powershell -NoProfile -Command "while($true){try{$c=New-Object Net.Sockets.TcpClient;$c.Connect('127.0.0.1',5000);$c.Close();break}catch{Start-Sleep -Milliseconds 500}}; Start-Process 'http://localhost:5000'"

REM Utiliser le Python embarque s'il existe, sinon le Python systeme
if exist "%ROOT%python\python.exe" (
    "%ROOT%python\python.exe" "%ROOT%server.py"
) else (
    python "%ROOT%server.py"
)
