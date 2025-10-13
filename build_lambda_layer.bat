@echo off
REM ====== BUILD LAMBDA LAYER FOR LINUX (USING UV) ======
REM This script uses uv pip's --platform flag to download Linux-compatible wheels

setlocal enabledelayedexpansion

REM ====== CONFIG ======
set LAYER_NAME=py311-mba-core
set RUNTIME=python3.11
for /f "tokens=*" %%i in ('aws configure get region') do set REGION=%%i
if "%REGION%"=="" set REGION=us-east-1

echo ========================================
echo Building Lambda Layer for Linux (using UV)
echo ========================================

REM ====== PREP WORKDIR ======
set BUILD_DIR=%CD%\layer_build
if not exist "%BUILD_DIR%" mkdir "%BUILD_DIR%"
cd /d "%BUILD_DIR%"

REM Clean previous build
if exist python rmdir /s /q python
if exist layer.zip del /q layer.zip
if exist requirements.txt del /q requirements.txt

REM ====== CREATE REQUIREMENTS ======
echo Creating requirements.txt...
(
echo boto3^>=1.40.0
echo python-dotenv^>=1.0.0
echo pydantic^>=2.0.0
echo pydantic-settings^>=2.0.0
echo pandas^>=2.0.0
echo pymysql^>=1.0.0
echo cryptography^>=41.0.0
) > requirements.txt

echo.
echo Installing packages for Linux ^(manylinux^)...
echo.

REM ====== INSTALL FOR LINUX PLATFORM USING UV ======
REM KEY FIX: Use uv pip with --python-platform to get Linux-compatible wheels
uv pip install ^
    -r requirements.txt ^
    --target python ^
    --python-platform x86_64-manylinux_2_17 ^
    --python 3.11 ^
    --no-cache

if errorlevel 1 (
    echo.
    echo ERROR: uv pip install failed
    echo.
    echo Trying with system Python pip instead...
    echo.
    
    REM Fallback to system python
    python -m pip install ^
        -r requirements.txt ^
        --platform manylinux2014_x86_64 ^
        --target python ^
        --implementation cp ^
        --python-version 3.11 ^
        --only-binary=:all: ^
        --upgrade
    
    if errorlevel 1 (
        echo.
        echo ERROR: Both uv and pip failed to install packages
        echo.
        echo Please ensure you have either:
        echo   1. uv installed: pip install uv
        echo   2. System Python with pip available
        exit /b 1
    )
)

echo.
echo Packages installed successfully!

REM ====== CLEAN UP ======
echo.
echo Cleaning up unnecessary files...

REM Remove __pycache__ directories
for /d /r python %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul

REM Remove tests directories
for /d /r python %%d in (tests) do @if exist "%%d" rd /s /q "%%d" 2>nul

REM Remove .pyc and .pyo files
del /s /q python\*.pyc 2>nul
del /s /q python\*.pyo 2>nul

REM Remove boto3/botocore (already in Lambda runtime)
if exist python\boto3 rmdir /s /q python\boto3 2>nul
if exist python\boto3-* rmdir /s /q python\boto3-* 2>nul
if exist python\botocore rmdir /s /q python\botocore 2>nul
if exist python\botocore-* rmdir /s /q python\botocore-* 2>nul
if exist python\s3transfer rmdir /s /q python\s3transfer 2>nul
if exist python\s3transfer-* rmdir /s /q python\s3transfer-* 2>nul

REM Remove .dist-info directories (metadata only)
for /d /r python %%d in (*.dist-info) do @if exist "%%d" rd /s /q "%%d" 2>nul

REM ====== CHECK SIZE ======
echo.
echo Checking layer size...
powershell -Command "$size = (Get-ChildItem -Path 'python' -Recurse | Measure-Object -Property Length -Sum).Sum; $sizeMB = [math]::Round($size / 1MB, 2); Write-Host \"   Unzipped size: $sizeMB MB / 250 MB\"; if ($size -gt 262144000) { Write-Host '   WARNING: Layer size exceeds 250MB limit!' -ForegroundColor Yellow } else { Write-Host '   Layer size OK' -ForegroundColor Green }"

REM ====== ZIP THE LAYER ======
echo.
echo Creating layer.zip...

powershell -Command "Compress-Archive -Path 'python' -DestinationPath 'layer.zip' -Force"

if not exist layer.zip (
    echo ERROR: Failed to create layer.zip
    exit /b 1
)

for %%A in (layer.zip) do set ZIP_SIZE=%%~zA
set /a ZIP_MB=!ZIP_SIZE! / 1048576
echo Created layer.zip ^(!ZIP_MB! MB^)

REM ====== PUBLISH LAYER ======
echo.
echo Publishing layer to AWS Lambda...

for /f "tokens=*" %%i in ('aws lambda publish-layer-version --layer-name %LAYER_NAME% --description "MBA dependencies for Python 3.11 (Linux compatible)" --zip-file fileb://layer.zip --compatible-runtimes %RUNTIME% --region %REGION% --query LayerVersionArn --output text') do set LAYER_ARN=%%i

if errorlevel 1 (
    echo ERROR: Failed to publish layer
    echo.
    echo The layer.zip file is at: %BUILD_DIR%\layer.zip
    echo You can manually upload it to AWS Lambda Console
    exit /b 1
)

echo.
echo ========================================
echo SUCCESS!
echo ========================================
echo Layer ARN: %LAYER_ARN%
echo ========================================
echo.
echo Next steps:
echo 1. Go to Lambda Console
echo 2. Select your function
echo 3. Scroll to 'Layers' section
echo 4. Click 'Add a layer'
echo 5. Choose 'Custom layers'
echo 6. Select: %LAYER_NAME%
echo 7. Version: Latest
echo 8. Click 'Add'
echo.
echo Build directory: %BUILD_DIR%
echo.

REM Return to original directory
cd /d %~dp0

echo Layer build complete!
pause

endlocal