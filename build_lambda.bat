@echo off
REM Clean previous builds
if exist mba_lambda.zip del mba_lambda.zip

REM Create zip using PowerShell
powershell -Command "Compress-Archive -Path 'src\MBA\*' -DestinationPath 'mba_lambda.zip' -Force -CompressionLevel Optimal"

echo Lambda package created: mba_lambda.zip
dir mba_lambda.zip