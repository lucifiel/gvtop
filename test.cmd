@echo off
REM Automated setup and test script for gvtop on Windows
setlocal

echo Cloning gvtop repository...
git clone https://github.com/gvtop/gvtop.git || (
    echo Failed to clone repository
    exit /b 1
)

cd gvtop

echo Creating Python virtual environment...
python -m venv venv || (
    echo Failed to create virtual environment
    exit /b 1
)

echo Installing dependencies...
call venv\Scripts\activate
pip install pynvml psutil || (
    echo Failed to install dependencies
    exit /b 1
)

echo Running gvtop...
python -m gvtop.gvtop

echo Press any key to exit...
pause >nul