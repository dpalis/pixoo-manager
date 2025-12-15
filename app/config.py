"""Configurações da aplicação Pixoo Manager."""

from pathlib import Path

# Servidor
HOST = "127.0.0.1"
PORT = 8000

# Pixoo 64 specs
PIXOO_SIZE = 64
MAX_UPLOAD_FRAMES = 40      # Limite seguro para envio ao Pixoo
MAX_CONVERT_FRAMES = 92     # Limite máximo de frames do Pixoo
MAX_VIDEO_DURATION = 10.0   # Segundos máximos de vídeo
PREVIEW_SCALE = 32          # Escala do preview (64 * 32 = 2048px)

# Limites de arquivo
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB em bytes

# Tipos de arquivo permitidos
ALLOWED_GIF_TYPES = ["image/gif"]
ALLOWED_IMAGE_TYPES = ["image/png", "image/jpeg", "image/gif"]
ALLOWED_VIDEO_TYPES = ["video/mp4", "video/quicktime", "video/webm"]

# Diretórios
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = Path(__file__).parent / "static"
TEMPLATES_DIR = Path(__file__).parent / "templates"

# Diretório temporário - usa temp do sistema
import tempfile
TEMP_DIR = Path(tempfile.gettempdir()) / "pixoo_manager"


# ============================================
# Bundled binaries (PyInstaller support)
# ============================================
import sys


def get_bundled_path(relative_path: str) -> Path:
    """
    Retorna caminho para arquivo bundled.

    Funciona tanto em desenvolvimento quanto quando empacotado com PyInstaller.
    Em dev: usa BASE_DIR como base
    Em frozen: usa sys._MEIPASS (diretório temporário do PyInstaller)

    Args:
        relative_path: Caminho relativo ao diretório base

    Returns:
        Path absoluto para o arquivo
    """
    if getattr(sys, 'frozen', False):
        # Executando como app empacotado
        base_path = Path(sys._MEIPASS)
    else:
        # Executando em desenvolvimento
        base_path = BASE_DIR
    return base_path / relative_path


def is_frozen() -> bool:
    """Retorna True se executando como app empacotado (PyInstaller)."""
    return getattr(sys, 'frozen', False)


# Caminhos para binários bundled
FFMPEG_PATH = get_bundled_path("bin/ffmpeg")
YTDLP_PATH = get_bundled_path("bin/yt-dlp")
