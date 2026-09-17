@echo off
rem ==============================================================================
rem build_windows.bat
rem Script Batch para compilação da versão Desktop no Windows (.exe)
rem ==============================================================================

echo ------------------------------------------------------------------
echo Compilando VideoAutomate para Windows (.exe)
echo ------------------------------------------------------------------

if exist ".venv\Scripts\activate.bat" (
    echo Ativando ambiente virtual .venv...
    call .venv\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    echo Ativando ambiente virtual venv...
    call venv\Scripts\activate.bat
)

echo [1/2] Instalando requisitos...
pip install -r requirements.txt

echo [2/2] Gerando executavel com PyInstaller...
pyinstaller --clean video_automate.spec

if exist "dist\VideoAutomate.exe" (
    echo ==================================================================
    echo Compilacao concluida com sucesso!
    echo Executavel gerado em: dist\VideoAutomate.exe
    echo ==================================================================
) else (
    echo Ocorreu um erro durante a compilacao.
    exit /b 1
)

pause
