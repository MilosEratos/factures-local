@echo off
setlocal EnableDelayedExpansion
title Factures Local — Installation
echo.
echo  ============================================
echo   Factures Local — Installation
echo  ============================================
echo.

set "ROOT=%~dp0"
set "PYTHON_DIR=%ROOT%python"
set "LLAMA_DIR=%ROOT%llama.cpp"
set "MODEL_DIR=%ROOT%models"
set "MODEL_FILE=%MODEL_DIR%\Qwen3.5-4B-Q4_K_M.gguf"
set "PYTHON_VER=3.12.8"

REM ============================================================
REM 1. PYTHON
REM ============================================================
echo  [1/4] Python...

where python >nul 2>&1
if %errorlevel%==0 (
    echo        Python system detecte.
    set "PY=python"
    goto :pip_install
)

echo        Python system introuvable — telechargement du Python embarque...
if not exist "%PYTHON_DIR%" mkdir "%PYTHON_DIR%"

set "PY_ZIP=%ROOT%_python-embed.zip"
if not exist "%PY_ZIP%" (
    echo        Telechargement Python %PYTHON_VER% embeddable...
    powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/%PYTHON_VER%/python-%PYTHON_VER%-embed-amd64.zip' -OutFile '%PY_ZIP%'"
    if %errorlevel% neq 0 (
        echo        [ERREUR] Echec du telechargement Python.
        exit /b 1
    )
)
echo        Extraction...
powershell -NoProfile -Command "Expand-Archive -Path '%PY_ZIP%' -DestinationPath '%PYTHON_DIR%' -Force"
del "%PY_ZIP%" 2>nul

REM Activer pip dans le Python embeddable
set "PTH_FILE=%PYTHON_DIR%\python%PYTHON_VER:~0,5%._pth"
REM Le fichier s'appelle python312._pth
for %%f in ("%PYTHON_DIR%\python*._pth") do set "PTH_FILE=%%f"
powershell -NoProfile -Command "(Get-Content '%PTH_FILE%') -replace '#import site','import site' | Set-Content '%PTH_FILE%'"

REM Installer pip
set "GETPIP=%ROOT%_get-pip.py"
if not exist "%GETPIP%" (
    powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%GETPIP%'"
)
"%PYTHON_DIR%\python.exe" "%GETPIP%" >nul 2>&1
del "%GETPIP%" 2>nul

set "PY=%PYTHON_DIR%\python.exe"
echo        Python embarque installe.

:pip_install
echo        Installation des dependances (flask, reportlab, PyMuPDF)...
%PY% -m pip install -r "%ROOT%requirements.txt" --quiet
if %errorlevel% neq 0 (
    echo        [ERREUR] Echec de l'installation des dependances.
    exit /b 1
)
echo        Dependances OK.
echo.

REM ============================================================
REM 2. DETECTION GPU
REM ============================================================
echo  [2/4] Detection du GPU...

set "GPU_TYPE=cpu"
set "LLAMA_ZIP_URL="
set "LLAMA_ZIP="

REM NVIDIA ?
where nvidia-smi >nul 2>&1
if %errorlevel%==0 (
    set "GPU_TYPE=nvidia"
    set "LLAMA_ZIP=llama-b12716-bin-win-cuda-12.4.zip"
    set "LLAMA_ZIP_URL=https://github.com/ggml-org/llama.cpp/releases/download/b12716/%LLAMA_ZIP%"
    echo        GPU NVIDIA detecte — build CUDA.
    goto :download_llama
)

REM AMD ?
for /f "tokens=*" %%i in ('wmic path win32_VideoController get name 2^>nul') do (
    echo %%i | findstr /i "AMD Radeon" >nul && (
        set "GPU_TYPE=amd"
        set "LLAMA_ZIP=llama-b12716-bin-win-vulkan.zip"
        set "LLAMA_ZIP_URL=https://github.com/ggml-org/llama.cpp/releases/download/b12716/%%LLAMA_ZIP%%"
    )
)

if "%GPU_TYPE%"=="amd" (
    echo        GPU AMD detecte — build Vulkan.
    goto :download_llama
)

echo        Pas de GPU detecte — build CPU (plus lent, ~1-2 min/facture).

:download_llama
if not defined LLAMA_ZIP (
    set "LLAMA_ZIP=llama-b12716-bin-win-x64.zip"
    set "LLAMA_ZIP_URL=https://github.com/ggml-org/llama.cpp/releases/download/b12716/%LLAMA_ZIP%"
)
echo.

REM ============================================================
REM 3. LLAMA.CPP
REM ============================================================
echo  [3/4] Moteur IA (llama.cpp)...

if exist "%LLAMA_DIR%\llama-server.exe" (
    echo        llama.cpp deja present.
    goto :download_model
)

if not exist "%LLAMA_DIR%" mkdir "%LLAMA_DIR%"
set "ZIP_FILE=%ROOT%_llama.zip"

echo        Telechargement de %LLAMA_ZIP%...
powershell -NoProfile -Command "Invoke-WebRequest -Uri '%LLAMA_ZIP_URL%' -OutFile '%ZIP_FILE%'"
if %errorlevel% neq 0 (
    echo        [ERREUR] Echec du telechargement de llama.cpp.
    exit /b 1
)

echo        Extraction...
powershell -NoProfile -Command "Expand-Archive -Path '%ZIP_FILE%' -DestinationPath '%LLAMA_DIR%' -Force"
del "%ZIP_FILE%" 2>nul

REM Si le zip contient un sous-dossier, remonter les fichiers
for /d %%d in ("%LLAMA_DIR%\*") do (
    if exist "%%d\llama-server.exe" (
        move "%%d\*" "%LLAMA_DIR%\" >nul 2>&1
        rmdir "%%d" 2>nul
    )
)

if exist "%LLAMA_DIR%\llama-server.exe" (
    echo        llama.cpp installe.
) else (
    echo        [ERREUR] llama-server.exe introuvable apres extraction.
    exit /b 1
)
echo.

REM ============================================================
REM 4. MODELE
REM ============================================================
:download_model
echo  [4/4] Modele IA (Qwen3.5 4B, ~2.6 GB)...

if exist "%MODEL_FILE%" (
    echo        Modele deja present.
    goto :done
)

if not exist "%MODEL_DIR%" mkdir "%MODEL_DIR%"
echo        Telechargement du modele (peut prendre quelques minutes)...
powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/main/Qwen3.5-4B-Q4_K_M.gguf' -OutFile '%MODEL_FILE%'"
if %errorlevel% neq 0 (
    echo        [ERREUR] Echec du telechargement du modele.
    echo        Vous pouvez le telecharger manuellement depuis :
    echo        https://huggingface.co/unsloth/Qwen3.5-4B-GGUF
    echo        et le placer dans : %MODEL_DIR%
    exit /b 1
)
echo        Modele installe.
echo.

:done
echo  ============================================
echo   Installation terminee !
echo.
echo   Double-cliquez sur start.bat pour lancer
echo   l'application.
echo  ============================================
echo.
pause
