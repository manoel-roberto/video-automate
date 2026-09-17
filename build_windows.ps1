# ==============================================================================
# build_windows.ps1
# Script PowerShell para compilação da versão Desktop no Windows (.exe)
# ==============================================================================

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host " Compilando VideoAutomate para Windows (.exe)" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

if (Test-Path ".venv\Scripts\Activate.ps1") {
    Write-Host "Ativando ambiente virtual .venv..." -ForegroundColor Yellow
    & .venv\Scripts\Activate.ps1
} elseif (Test-Path "venv\Scripts\Activate.ps1") {
    Write-Host "Ativando ambiente virtual venv..." -ForegroundColor Yellow
    & venv\Scripts\Activate.ps1
}

Write-Host "[1/2] Verificando dependências..." -ForegroundColor Green
pip install -r requirements.txt

Write-Host "[2/2] Compilando executável com PyInstaller..." -ForegroundColor Green
pyinstaller --clean video_automate.spec

if (Test-Path "dist\VideoAutomate.exe") {
    Write-Host "==================================================================" -ForegroundColor Green
    Write-Host "🎉 Compilação concluída com sucesso!" -ForegroundColor Green
    Write-Host "📁 Executável gerado: dist\VideoAutomate.exe" -ForegroundColor Green
    Write-Host "==================================================================" -ForegroundColor Green
} else {
    Write-Host "❌ Falha na compilação do executável." -ForegroundColor Red
    exit 1
}
