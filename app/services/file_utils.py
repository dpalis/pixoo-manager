"""
Utilitários para manipulação de arquivos em endpoints.

Adaptado do PDFTools com suporte para tipos de mídia do Pixoo Manager.
"""

import re
import tempfile
from pathlib import Path
from typing import List

from fastapi import HTTPException, UploadFile

from app.config import (
    ALLOWED_GIF_TYPES,
    ALLOWED_IMAGE_TYPES,
    ALLOWED_VIDEO_TYPES,
    MAX_FILE_SIZE,
    TEMP_DIR,
)
from app.services.exceptions import InvalidFileError


# Magic bytes para validação de tipo real de arquivo
GIF_MAGIC_BYTES = b"GIF8"  # GIF87a ou GIF89a
PNG_MAGIC_BYTES = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC_BYTES = b"\xff\xd8\xff"
MP4_FTYP = b"ftyp"  # MP4 tem 'ftyp' nos bytes 4-7
WEBM_MAGIC = b"\x1a\x45\xdf\xa3"  # WebM/Matroska


def sanitize_filename(name: str) -> str:
    """
    Remove caracteres perigosos de nomes de arquivo.

    Previne path traversal e caracteres especiais.
    """
    if not name:
        return "arquivo"

    # Remove path components (previne ../ e similares)
    name = Path(name).name

    # Remove extensão para pegar só o stem
    name = Path(name).stem

    # Remove caracteres especiais, mantém apenas letras, números, espaços, hífens e underscores
    safe_name = re.sub(r'[^\w\s\-]', '', name, flags=re.UNICODE)

    # Remove espaços extras e limita tamanho
    safe_name = ' '.join(safe_name.split())[:100]

    return safe_name or "arquivo"


def validate_magic_bytes(data: bytes, content_type: str) -> bool:
    """
    Valida se os primeiros bytes do arquivo correspondem ao tipo declarado.

    Previne ataques onde um arquivo malicioso é enviado com content-type falso.
    """
    if len(data) < 12:
        return False  # Dados insuficientes para validação

    if content_type == "image/gif":
        return data.startswith(GIF_MAGIC_BYTES)

    elif content_type == "image/png":
        return data.startswith(PNG_MAGIC_BYTES)

    elif content_type in ("image/jpeg", "image/jpg"):
        return data.startswith(JPEG_MAGIC_BYTES)

    elif content_type == "video/mp4":
        # MP4 tem 'ftyp' nos bytes 4-7
        return MP4_FTYP in data[:12]

    elif content_type == "video/webm":
        return data.startswith(WEBM_MAGIC)

    elif content_type == "video/quicktime":
        # QuickTime/MOV também usa ftyp
        return MP4_FTYP in data[:12]

    # Tipo não reconhecido - falha segura
    return False


def get_extension_for_type(content_type: str) -> str:
    """Retorna extensão apropriada para o content-type."""
    extensions = {
        "image/gif": ".gif",
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "video/mp4": ".mp4",
        "video/webm": ".webm",
        "video/quicktime": ".mov",
    }
    return extensions.get(content_type, "")


def ensure_temp_dir() -> Path:
    """Garante que o diretório temporário existe."""
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    return TEMP_DIR


async def stream_upload_to_temp(
    file: UploadFile,
    allowed_types: List[str],
    max_size: int = MAX_FILE_SIZE,
    validate_magic: bool = True,
) -> Path:
    """
    Faz streaming de upload para arquivo temporário com validação.

    Args:
        file: Arquivo de upload do FastAPI
        allowed_types: Lista de MIME types permitidos
        max_size: Tamanho máximo em bytes
        validate_magic: Se deve validar magic bytes (recomendado)

    Returns:
        Path do arquivo temporário criado

    Raises:
        HTTPException: Se validação falhar (tipo, tamanho, magic bytes)
    """
    # Valida content-type
    if file.content_type not in allowed_types:
        tipos = ", ".join(t.split("/")[1].upper() for t in allowed_types)
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de arquivo inválido. Tipos aceitos: {tipos}"
        )

    # Determina extensão baseada no tipo
    extension = get_extension_for_type(file.content_type)

    # Garante que temp dir existe
    ensure_temp_dir()

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=extension,
            dir=TEMP_DIR
        ) as temp:
            temp_path = Path(temp.name)
            total_size = 0
            chunk_size = 64 * 1024  # 64KB chunks
            first_chunk = True

            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break

                # Valida magic bytes no primeiro chunk
                if first_chunk and validate_magic:
                    if not validate_magic_bytes(chunk, file.content_type):
                        raise HTTPException(
                            status_code=400,
                            detail="Conteúdo do arquivo não corresponde ao tipo declarado"
                        )
                    first_chunk = False

                total_size += len(chunk)
                if total_size > max_size:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Arquivo muito grande. Limite: {max_size // (1024 * 1024)}MB"
                    )

                temp.write(chunk)

        return temp_path

    except HTTPException:
        # Limpa arquivo parcial antes de propagar erro
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)
        raise


def create_temp_output(suffix: str = ".gif") -> Path:
    """
    Cria arquivo temporário para output.

    Args:
        suffix: Extensão do arquivo

    Returns:
        Path do arquivo temporário
    """
    ensure_temp_dir()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=TEMP_DIR) as temp:
        return Path(temp.name)


def cleanup_files(paths: List[Path]) -> None:
    """
    Remove lista de arquivos de forma segura.

    Args:
        paths: Lista de caminhos para remover
    """
    for path in paths:
        try:
            if path and path.exists():
                path.unlink()
        except Exception:
            pass  # Ignora erros de cleanup


async def cleanup_file_async(path: Path) -> None:
    """
    Remove arquivo de forma segura (para BackgroundTasks).

    Args:
        path: Caminho do arquivo para remover
    """
    try:
        if path and path.exists():
            path.unlink()
    except Exception:
        pass


def cleanup_temp_dir() -> None:
    """Remove todos os arquivos do diretório temporário."""
    if TEMP_DIR.exists():
        for file in TEMP_DIR.iterdir():
            try:
                if file.is_file():
                    file.unlink()
            except Exception:
                pass
