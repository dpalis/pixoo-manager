#!/bin/bash
#
# Build script para Pixoo Manager
# Cria Pixoo Manager.app usando PyInstaller
#
# Uso: ./build.sh
#
# Requisitos:
#   - Python 3.10+
#   - venv com dependências instaladas
#   - FFmpeg em bin/ffmpeg
#

set -e

echo "🔨 Building Pixoo Manager.app..."
echo ""

# Diretório do script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Verificar FFmpeg
if [ ! -f "bin/ffmpeg" ]; then
    echo "❌ FFmpeg não encontrado em bin/ffmpeg"
    echo ""
    echo "Para baixar FFmpeg para Apple Silicon:"
    echo "  curl -L 'https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip' -o /tmp/ffmpeg.zip"
    echo "  unzip -o /tmp/ffmpeg.zip -d /tmp/ffmpeg_extracted"
    echo "  mv /tmp/ffmpeg_extracted/ffmpeg bin/ffmpeg"
    echo "  chmod +x bin/ffmpeg"
    echo ""
    exit 1
fi

echo "✅ FFmpeg encontrado"

# Verificar yt-dlp bundled (opcional)
if [ -f "bin/yt-dlp" ]; then
    echo "✅ yt-dlp bundled encontrado"
else
    echo "⚠️  yt-dlp bundled não encontrado (usará versão do sistema)"
fi

# Ativar virtualenv se existir
if [ -d "venv" ]; then
    echo "📦 Ativando virtualenv..."
    source venv/bin/activate
fi

# Verificar PyInstaller
if ! command -v pyinstaller &> /dev/null; then
    echo "❌ PyInstaller não encontrado"
    echo "   Instale com: pip install pyinstaller"
    exit 1
fi

echo "✅ PyInstaller encontrado: $(pyinstaller --version)"
echo ""

# Limpar builds anteriores
echo "🧹 Limpando builds anteriores..."
rm -rf build/dist build/build

# Executar PyInstaller
echo ""
echo "🏗️  Executando PyInstaller..."
cd build
pyinstaller pixoo_manager.spec --noconfirm

# Verificar resultado
if [ -d "dist/Pixoo Manager.app" ]; then
    echo ""
    echo "✅ Build concluído com sucesso!"
    echo ""
    echo "📍 App em: $(pwd)/dist/Pixoo Manager.app"
    echo ""
    echo "Para executar:"
    echo "  open 'build/dist/Pixoo Manager.app'"
    echo ""

    # Mostrar tamanho do app
    APP_SIZE=$(du -sh "dist/Pixoo Manager.app" | cut -f1)
    echo "📦 Tamanho: $APP_SIZE"
else
    echo ""
    echo "❌ Build falhou - app não foi criado"
    exit 1
fi
