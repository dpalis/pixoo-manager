"""Configurações da aplicação Pixoo Manager."""

from pathlib import Path

# Servidor
HOST = "127.0.0.1"
PORT = 8000

# Pixoo 64 specs
PIXOO_SIZE = 64
MAX_UPLOAD_FRAMES = 40      # Limite seguro para envio ao Pixoo
MAX_CONVERT_FRAMES = 92     # Limite máximo de frames do Pixoo
MAX_VIDEO_DURATION = 10.0   # Segundos máximos de vídeo (normal)
MAX_SHORTS_DURATION = 30.0  # Segundos máximos para YouTube Shorts (30s para evitar picos de memória)
PREVIEW_SCALE = 64          # Escala max do preview (64 * 64 = 4096px)

# Limites de arquivo
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB em bytes

# Tipos de arquivo permitidos
# Note: WebP can be animated, so it's in both GIF and IMAGE types
ALLOWED_GIF_TYPES = ["image/gif", "image/webp"]
ALLOWED_IMAGE_TYPES = ["image/png", "image/jpeg", "image/gif", "image/webp"]
ALLOWED_VIDEO_TYPES = ["video/mp4", "video/quicktime", "video/webm"]

# Diretórios
BASE_DIR = Path(__file__).resolve().parent.parent

# Para desenvolvimento, usamos caminhos relativos ao módulo
# Para bundle (py2app), os recursos são copiados para Contents/Resources/
_DEV_STATIC_DIR = Path(__file__).parent / "static"
_DEV_TEMPLATES_DIR = Path(__file__).parent / "templates"

# Diretório temporário - usa temp do sistema
import tempfile
TEMP_DIR = Path(tempfile.gettempdir()) / "pixoo_manager"


# ============================================
# Bundled binaries (py2app/PyInstaller support)
# ============================================
import sys


def get_bundle_base() -> Path:
    """
    Retorna o diretório base para recursos bundled.

    Suporta:
    - py2app: sys.frozen == 'macosx_app'
    - PyInstaller: sys.frozen == True + sys._MEIPASS
    - Desenvolvimento: BASE_DIR
    """
    frozen = getattr(sys, 'frozen', False)

    if frozen == 'macosx_app':
        # py2app - recursos estão em Contents/Resources/
        return Path(sys.executable).parent.parent / "Resources"
    elif frozen:
        # PyInstaller
        return Path(getattr(sys, '_MEIPASS', BASE_DIR))
    else:
        # Desenvolvimento
        return BASE_DIR


def get_bundled_path(relative_path: str) -> Path:
    """
    Retorna caminho para arquivo bundled.

    Args:
        relative_path: Caminho relativo ao diretório base

    Returns:
        Path absoluto para o arquivo
    """
    return get_bundle_base() / relative_path


def is_frozen() -> bool:
    """Retorna True se executando como app empacotado."""
    return bool(getattr(sys, 'frozen', False))


# Caminhos para binários bundled (usados apenas se existirem)
FFMPEG_PATH = get_bundled_path("bin/ffmpeg")
YTDLP_PATH = get_bundled_path("bin/yt-dlp")


def _get_static_dir() -> Path:
    """Retorna diretório de arquivos estáticos."""
    if is_frozen():
        return get_bundle_base() / "static"
    return _DEV_STATIC_DIR


def _get_templates_dir() -> Path:
    """Retorna diretório de templates."""
    if is_frozen():
        return get_bundle_base() / "templates"
    return _DEV_TEMPLATES_DIR


# Diretórios dinâmicos (avaliados na importação)
STATIC_DIR = _get_static_dir()
TEMPLATES_DIR = _get_templates_dir()
