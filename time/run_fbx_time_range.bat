@echo off
setlocal

cd /d "%~dp0"

set "PYTHON_EXE=%USERPROFILE%\.pyenv\pyenv-win\versions\3.10.11\python.exe"

if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=python"
)

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set "PYTHON_CMD=py"
) else (
    where python >nul 2>nul
    if %ERRORLEVEL% EQU 0 (
        set "PYTHON_CMD=python"
    ) else (
        echo Python was not found on PATH.
        echo Install Python and make sure either py or python is available.
        pause
        exit /b 1
    )
)

if "%~1"=="" (
    echo Drag and drop an .fbx file onto this batch file.
    echo Example: %~nx0 "C:\path\to\file.fbx"
    pause
    exit /b 1
)

set "FBX_PATH=%~f1"

"%PYTHON_CMD%" "%SCRIPT_PATH%" --fbx "%FBX_PATH%"

if errorlevel 1 (
    echo.
    echo The script failed. Check the output above for details.
    pause
    exit /b %errorlevel%
)

pause
