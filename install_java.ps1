# ============================================================================
# Java Installation Script (Chocolatey)
# ============================================================================
# This script installs OpenJDK using Chocolatey package manager
# Run this in PowerShell as Administrator
# ============================================================================

Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "JAVA INSTALLATION SCRIPT" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please:" -ForegroundColor Yellow
    Write-Host "  1. Right-click PowerShell" -ForegroundColor Yellow
    Write-Host "  2. Select 'Run as Administrator'" -ForegroundColor Yellow
    Write-Host "  3. Run this script again" -ForegroundColor Yellow
    Write-Host ""
    pause
    exit 1
}

# Check if Java is already installed
Write-Host "Checking for existing Java installation..." -ForegroundColor Yellow
try {
    $javaVersion = & java -version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Java is already installed:" -ForegroundColor Green
        Write-Host $javaVersion[0] -ForegroundColor Green
        Write-Host ""
        Write-Host "Do you want to reinstall/upgrade Java? (Y/N)" -ForegroundColor Yellow
        $response = Read-Host
        if ($response -ne "Y" -and $response -ne "y") {
            Write-Host "Installation cancelled." -ForegroundColor Yellow
            exit 0
        }
    }
} catch {
    Write-Host "Java is not currently installed." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "Step 1: Installing/Updating Chocolatey" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# Check if Chocolatey is installed
$chocoInstalled = Get-Command choco -ErrorAction SilentlyContinue

if (-not $chocoInstalled) {
    Write-Host "Chocolatey is not installed. Installing Chocolatey..." -ForegroundColor Yellow
    Write-Host ""

    # Install Chocolatey
    Set-ExecutionPolicy Bypass -Scope Process -Force
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072

    try {
        Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
        Write-Host "Chocolatey installed successfully!" -ForegroundColor Green
    } catch {
        Write-Host "ERROR: Failed to install Chocolatey" -ForegroundColor Red
        Write-Host $_.Exception.Message -ForegroundColor Red
        Write-Host ""
        Write-Host "Please install Chocolatey manually from: https://chocolatey.org/install" -ForegroundColor Yellow
        pause
        exit 1
    }

    # Refresh environment variables
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
} else {
    Write-Host "Chocolatey is already installed." -ForegroundColor Green
    Write-Host "Upgrading Chocolatey to latest version..." -ForegroundColor Yellow
    choco upgrade chocolatey -y
}

Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "Step 2: Installing OpenJDK" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Installing OpenJDK (this may take a few minutes)..." -ForegroundColor Yellow
choco install openjdk -y

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "OpenJDK installed successfully!" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "ERROR: Failed to install OpenJDK" -ForegroundColor Red
    Write-Host "Please try manual installation from: https://adoptium.net/" -ForegroundColor Yellow
    pause
    exit 1
}

Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "Step 3: Verifying Installation" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# Refresh environment variables
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

# Verify Java installation
Write-Host "Verifying Java installation..." -ForegroundColor Yellow
try {
    $javaVersion = & java -version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "SUCCESS! Java is now installed:" -ForegroundColor Green
        Write-Host $javaVersion[0] -ForegroundColor Green
        Write-Host $javaVersion[1] -ForegroundColor Green
        Write-Host $javaVersion[2] -ForegroundColor Green
    } else {
        throw "Java command failed"
    }
} catch {
    Write-Host ""
    Write-Host "WARNING: Java may not be properly configured in PATH" -ForegroundColor Yellow
    Write-Host "Please restart your terminal and try: java -version" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "Installation Complete!" -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. RESTART YOUR TERMINAL (important!)" -ForegroundColor Yellow
Write-Host "  2. Navigate to: C:\Users\ROHIT\Work\HMA\MBA_CT" -ForegroundColor Yellow
Write-Host "  3. Run: python verify_local_rag.py" -ForegroundColor Yellow
Write-Host "  4. Start Streamlit: uv run mba-app" -ForegroundColor Yellow
Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""
pause
