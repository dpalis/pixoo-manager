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
