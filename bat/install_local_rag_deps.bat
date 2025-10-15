@echo off
REM ============================================================================
REM Local RAG Dependencies Installation Script
REM ============================================================================
REM This script installs all dependencies for the Local RAG Agent
REM Run this from the MBA_CT directory
REM ============================================================================

echo.
echo ============================================================================
echo LOCAL RAG DEPENDENCIES INSTALLATION
echo ============================================================================
echo.

REM Check if running in virtual environment
echo Checking virtual environment...
python -c "import sys; sys.exit(0 if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix) else 1)"
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: Not running in virtual environment
    echo It's recommended to use: uv venv
    echo.
    pause
)

echo.
echo ============================================================================
echo Step 1: Installing Python Dependencies
echo ============================================================================
echo.

REM Install Local RAG dependencies
echo Installing Local RAG dependencies from requirements.txt...
uv pip install -r requirements.txt

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo ============================================================================
echo Step 2: Checking Java Installation (Required for Tabula)
echo ============================================================================
echo.

REM Check if Java is installed
java -version 2>&1 | findstr /i "version" >nul
if %ERRORLEVEL% EQU 0 (
    echo Java is already installed!
    java -version
) else (
    echo.
    echo WARNING: Java is NOT installed!
    echo.
    echo Tabula requires Java 8 or higher for table extraction from PDFs.
    echo.
    echo Please install Java using ONE of these methods:
    echo.
    echo   Method 1 - Using Chocolatey (Recommended):
    echo     1. Open PowerShell as Administrator
    echo     2. Run: choco install openjdk
    echo.
    echo   Method 2 - Manual Installation:
    echo     1. Download from: https://adoptium.net/
    echo     2. Run the installer
    echo     3. Restart your terminal
    echo.
    echo After installing Java, run verify_local_rag.py to test everything.
    echo.
)

echo.
echo ============================================================================
echo Step 3: Downloading AI Models (First Time Only)
echo ============================================================================
echo.

echo The following models will be downloaded on first use:
echo   - Sentence Transformer (all-MiniLM-L6-v2): ~90 MB
echo   - Cross-Encoder Reranker (ms-marco-MiniLM-L-6-v2): ~80 MB
echo.
echo These models are cached locally and only downloaded once.
echo.

echo.
echo ============================================================================
echo Installation Complete!
echo ============================================================================
echo.
echo Next steps:
echo   1. If Java is not installed, install it using the methods above
echo   2. Run verification script: python verify_local_rag.py
echo   3. Start Streamlit app: uv run mba-app
echo   4. Navigate to the "Local RAG" tab
echo.
echo ============================================================================
pause
