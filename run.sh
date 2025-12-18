#!/bin/bash
#
# Script para executar o Pixoo Manager em modo desenvolvimento
#
# Uso: ./run.sh
#

set -e

# Diretório do projeto
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "🚀 Iniciando Pixoo Manager..."
echo ""

# Verificar se venv existe (.venv ou venv)
if [ -d ".venv" ]; then
    VENV_DIR=".venv"
elif [ -d "venv" ]; then
    VENV_DIR="venv"
else
    echo "❌ Virtualenv não encontrado"
    echo ""
    echo "Para criar:"
    echo "  python3 -m venv .venv"
    echo "  source .venv/bin/activate"
    echo "  pip install -r requirements.txt"
    echo ""
    exit 1
fi

# Ativar virtualenv
echo "📦 Ativando virtualenv ($VENV_DIR)..."
source "$VENV_DIR/bin/activate"

# Verificar dependências
if ! python -c "import fastapi" 2>/dev/null; then
    echo "❌ Dependências não instaladas"
    echo ""
    echo "Execute:"
    echo "  pip install -r requirements.txt"
    echo ""
    exit 1
fi

echo "✅ Dependências OK"
echo ""

# Matar processo anterior na porta 8000 (se existir)
if lsof -ti:8000 > /dev/null 2>&1; then
    echo "🔄 Parando servidor anterior na porta 8000..."
    kill $(lsof -ti:8000) 2>/dev/null || true
    sleep 1
fi

# Executar aplicação
echo "🌐 Servidor iniciando em http://127.0.0.1:8000"
echo "   (Ctrl+C para parar)"
echo ""

python -m app.main
