@echo off
setlocal EnableDelayedExpansion
title Factures Local - Installation
echo.
echo  ============================================
echo   Factures Local - Installation
echo  ============================================
echo.

set "ROOT=%~dp0"
set "PYTHON_DIR=%ROOT%python"
set "LLAMA_DIR=%ROOT%llama.cpp"
set "MODEL_DIR=%ROOT%models"
set "PYTHON_VER=3.12.8"

REM ============================================================
REM 1. PYTHON
REM ============================================================
echo  [1/5] Python...

REM Verifier si un vrai Python system est present (pas l'alias Microsoft Store)
python --version >nul 2>&1
if %errorlevel%==0 (
    echo        Python system detecte.
    set "PY=python"
    goto :pip_install
)

REM Verifier si le Python embarque est deja present
if exist "%PYTHON_DIR%\python.exe" (
    echo        Python embarque deja present.
    set "PY=%PYTHON_DIR%\python.exe"
    goto :pip_install
)

echo        Python system introuvable - telechargement du Python embarque...
if not exist "%PYTHON_DIR%" mkdir "%PYTHON_DIR%"

set "PY_ZIP=%ROOT%_python-embed.zip"
if not exist "%PY_ZIP%" (
    echo        Telechargement Python %PYTHON_VER% embeddable...
    curl.exe -L -C - -o "%PY_ZIP%" "https://www.python.org/ftp/python/%PYTHON_VER%/python-%PYTHON_VER%-embed-amd64.zip"
    if !errorlevel! neq 0 (
        echo.
        echo        [ERREUR] Echec du telechargement Python.
        echo        Verifiez votre connexion internet.
        pause
        exit /b 1
    )
)
echo        Extraction...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Path '%PY_ZIP%' -DestinationPath '%PYTHON_DIR%' -Force"
del "%PY_ZIP%" 2>nul

REM Activer pip dans le Python embeddable
for %%f in ("%PYTHON_DIR%\python*._pth") do (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-Content '%%f') -replace '#import site','import site' | Set-Content '%%f'"
)

REM Installer pip
set "GETPIP=%ROOT%_get-pip.py"
if not exist "%GETPIP%" (
    curl.exe -L -C - -o "%GETPIP%" "https://bootstrap.pypa.io/get-pip.py"
)
"%PYTHON_DIR%\python.exe" "%GETPIP%" >nul 2>&1
del "%GETPIP%" 2>nul

set "PY=%PYTHON_DIR%\python.exe"
echo        Python embarque installe.

:pip_install
echo        Installation des dependances (flask, reportlab, PyMuPDF)...
%PY% -m pip install -r "%ROOT%requirements.txt" --quiet --no-warn-script-location
if %errorlevel% neq 0 (
    echo.
    echo        [ERREUR] Echec de l'installation des dependances.
    echo        Verifiez votre connexion internet.
    pause
    exit /b 1
)
echo        Dependances OK.
echo.

REM ============================================================
REM 2. DETECTION GPU
REM ============================================================
echo  [2/5] Detection du GPU...

set "GPU_TYPE=cpu"
set "LLAMA_ZIP="
set "GPU_OLD="
set "VRAM_MB=0"

REM NVIDIA ?
if exist "C:\Windows\System32\nvidia-smi.exe" (
    for /f "tokens=*" %%g in ('nvidia-smi --query-gpu=name --format=csv,noheader 2^>nul') do (
        echo %%g | findstr /i /c:"GTX 6" /c:"GTX 7" /c:"GT 6" /c:"GT 7" >nul && set "GPU_OLD=1"
    )
    if "!GPU_OLD!"=="1" (
        echo        GPU NVIDIA detecte mais trop ancien pour CUDA 12 - utilisation du CPU.
        goto :download_llama
    )
    set "GPU_TYPE=nvidia"
    set "LLAMA_ZIP=llama-b12716-bin-win-cuda-12.4-x64.zip"
    set "LLAMA_ZIP_URL=https://github.com/ggml-org/llama.cpp/releases/download/b12716/llama-b12716-bin-win-cuda-12.4-x64.zip"
    echo        GPU NVIDIA detecte - build CUDA.
    REM Lire la VRAM (en Mo) - fichier temp + set /p pour une valeur propre
    nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits > "%ROOT%_vram.txt" 2>nul
    if exist "%ROOT%_vram.txt" (
        set /p VRAM_MB=<"%ROOT%_vram.txt"
        del "%ROOT%_vram.txt" 2>nul
    )
    if "%VRAM_MB%"=="" set "VRAM_MB=0"
    goto :download_llama
)

REM AMD ?
set "AMD_FOUND=0"
for /f "tokens=*" %%i in ('powershell -NoProfile -Command "(Get-CimInstance Win32_VideoController).Name" 2^>nul') do (
    echo %%i | findstr /i "AMD Radeon" >nul && set "AMD_FOUND=1"
)
if "%AMD_FOUND%"=="1" (
    set "GPU_TYPE=amd"
    set "LLAMA_ZIP=llama-b12716-bin-win-vulkan-x64.zip"
    set "LLAMA_ZIP_URL=https://github.com/ggml-org/llama.cpp/releases/download/b12716/llama-b12716-bin-win-vulkan-x64.zip"
    echo        GPU AMD detecte - build Vulkan.
    goto :download_llama
)

echo        Pas de GPU compatible detecte (NVIDIA/AMD) - utilisation du CPU.

:download_llama
if not defined LLAMA_ZIP (
    set "LLAMA_ZIP=llama-b12716-bin-win-cpu-x64.zip"
    set "LLAMA_ZIP_URL=https://github.com/ggml-org/llama.cpp/releases/download/b12716/llama-b12716-bin-win-cpu-x64.zip"
)
echo.

REM ============================================================
REM 3. VISUAL C++ REDIST + LLAMA.CPP
REM ============================================================
echo  [3/5] Moteur IA (llama.cpp)...

REM Verifier le Visual C++ Redistributable (dependance de llama-server.exe)
if not exist "C:\Windows\System32\VCRUNTIME140.dll" (
    echo        Installation du Visual C++ Redistributable...
    set "VCREDIST=%ROOT%_vc_redist.exe"
    curl.exe -L -C - -o "!VCREDIST!" "https://aka.ms/vs/17/release/vc_redist.x64.exe" -s
    if !errorlevel! neq 0 (
        echo.
        echo        [ERREUR] Echec du telechargement du Visual C++ Redistributable.
        echo        Telechargez-le manuellement depuis :
        echo        https://aka.ms/vs/17/release/vc_redist.x64.exe
        pause
        exit /b 1
    )
    start /wait "" "!VCREDIST!" /install /quiet /norestart
    del "!VCREDIST!" 2>nul
    echo        Visual C++ Redistributable installe.
)

if exist "%LLAMA_DIR%\llama-server.exe" (
    echo        llama.cpp deja present.
    goto :model_choice
)

if not exist "%LLAMA_DIR%" mkdir "%LLAMA_DIR%"
set "ZIP_FILE=%ROOT%_llama.zip"
set "CUDART_ZIP=%ROOT%_cudart.zip"

REM Les builds CUDA necessitent aussi les DLLs CUDA (cuBLAS + runtime)
if "!GPU_TYPE!"=="nvidia" (
    if not exist "%LLAMA_DIR%\cudart64_12.dll" (
        echo        Telechargement des DLLs CUDA...
        curl.exe -L -C - -o "!CUDART_ZIP!" "https://github.com/ggml-org/llama.cpp/releases/download/b12716/cudart-llama-bin-win-cuda-12.4-x64.zip"
        if !errorlevel! neq 0 (
            echo.
            echo        [ERREUR] Echec du telechargement des DLLs CUDA.
            echo        Verifiez votre connexion internet.
            pause
            exit /b 1
        )
    )
)

echo        Telechargement de %LLAMA_ZIP%...
curl.exe -L -C - -o "%ZIP_FILE%" "%LLAMA_ZIP_URL%"
if %errorlevel% neq 0 (
    echo.
    echo        [ERREUR] Echec du telechargement de llama.cpp.
    echo        Verifiez votre connexion internet.
    pause
    exit /b 1
)

echo        Extraction...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Path '%ZIP_FILE%' -DestinationPath '%LLAMA_DIR%' -Force"
del "%ZIP_FILE%" 2>nul

if "!GPU_TYPE!"=="nvidia" (
    if exist "!CUDART_ZIP!" (
        powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Path '!CUDART_ZIP!' -DestinationPath '%LLAMA_DIR%' -Force"
        del "!CUDART_ZIP!" 2>nul
    )
)

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
    echo.
    echo        [ERREUR] llama-server.exe introuvable apres extraction.
    pause
    exit /b 1
)
echo.

REM ============================================================
REM 4. CHOIX DU MODELE
REM ============================================================
:model_choice
echo  [4/5] Modele IA...
echo.

REM Determiner le modele par defaut selon la VRAM
set "MODEL_DEFAULT=1"
if not "%VRAM_MB%"=="0" if %VRAM_MB% GTR 8191 (
    set "MODEL_DEFAULT=2"
)

echo        Deux modeles sont disponibles :
echo.
echo          [1] Petit  - Qwen3.5 4B  (~2,6 Go)
echo              Compatible avec toutes les machines (CPU, GPU 4 Go+)
echo.
echo          [2] Moyen  - Qwen3.5 9B  (~6 Go)
echo              Plus precise, GPU 8 Go minimum recommande
echo.
if not "%VRAM_MB%"=="0" if %VRAM_MB% GTR 8191 (
    echo        GPU avec %VRAM_MB% Mo de VRAM detecte - le modele Moyen est recommande.
)
echo.
set /p "MODEL_CHOICE=        Votre choix [1/2] (defaut %MODEL_DEFAULT%) : "
if "%MODEL_CHOICE%"=="" set "MODEL_CHOICE=%MODEL_DEFAULT%"

if "%MODEL_CHOICE%"=="2" (
    set "MODEL_FILE=%MODEL_DIR%\Qwen3.5-9B-Q4_K_M.gguf"
    set "MODEL_URL=https://huggingface.co/unsloth/Qwen3.5-9B-GGUF/resolve/main/Qwen3.5-9B-Q4_K_M.gguf"
    set "MODEL_SIZE=~6 Go"
) else (
    set "MODEL_CHOICE=1"
    set "MODEL_FILE=%MODEL_DIR%\Qwen3.5-4B-Q4_K_M.gguf"
    set "MODEL_URL=https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/main/Qwen3.5-4B-Q4_K_M.gguf"
    set "MODEL_SIZE=~2,6 Go"
)

echo.

REM ============================================================
REM 5. TELECHARGEMENT DU MODELE
REM ============================================================
echo  [5/5] Telechargement du modele (%MODEL_SIZE%)...

if exist "%MODEL_FILE%" (
    echo        Modele deja present.
    goto :done
)

if not exist "%MODEL_DIR%" mkdir "%MODEL_DIR%"
echo.
echo        Telechargement depuis HuggingFace...
curl.exe -L -C - --progress-bar -o "%MODEL_FILE%" "%MODEL_URL%"
if %errorlevel% neq 0 (
    echo.
    echo        [ERREUR] Echec du telechargement du modele.
    echo        Relancez install.bat pour reprendre le telechargement,
    echo        ou telechargez manuellement depuis :
    echo        %MODEL_URL%
    echo        et placez le fichier dans : %MODEL_DIR%
    pause
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
