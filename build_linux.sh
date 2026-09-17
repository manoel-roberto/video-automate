#!/usr/bin/env bash
# ==============================================================================
# build_linux.sh
# Script para compilação da versão Desktop no Linux (binário ELF autocontido)
# ==============================================================================

set -e

echo "🚀 [1/3] Verificando ambiente Python..."
if [ -d ".venv" ]; then
    echo "   Ativando ambiente virtual .venv..."
    source .venv/bin/activate
elif [ -d "venv" ]; then
    echo "   Ativando ambiente virtual venv..."
    source venv/bin/activate
fi

echo "📦 [2/3] Instalando/atualizando dependências de compilação..."
pip install -r requirements.txt

echo "⚙️ [3/3] Executando PyInstaller para compilação do executável Linux..."
pyinstaller --clean video_automate.spec

if [ -f "dist/VideoAutomate" ]; then
    chmod +x dist/VideoAutomate
    echo "=================================================================="
    echo "🎉 Compilação no Linux concluída com sucesso!"
    echo "📁 Executável gerado: dist/VideoAutomate"
    echo "▶️ Para executar:"
    echo "   ./dist/VideoAutomate"
    echo "=================================================================="
else
    echo "❌ Erro: o binário dist/VideoAutomate não foi encontrado."
    exit 1
fi
