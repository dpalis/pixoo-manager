"""
Utilitários para manipulação de arquivos em endpoints.

Adaptado do PDFTools com suporte para tipos de mídia do Pixoo Manager.
"""

import logging
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from time import time
from typing import Dict, List, Optional

from fastapi import HTTPException, UploadFile

from app.config import (
    ALLOWED_GIF_TYPES,
    ALLOWED_IMAGE_TYPES,
    ALLOWED_VIDEO_TYPES,
    MAX_FILE_SIZE,
    TEMP_DIR,
)
from app.services.exceptions import InvalidFileError


logger = logging.getLogger(__name__)


# Magic bytes para validação de tipo real de arquivo
GIF_MAGIC_BYTES = b"GIF8"  # GIF87a ou GIF89a
PNG_MAGIC_BYTES = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC_BYTES = b"\xff\xd8\xff"
WEBP_RIFF = b"RIFF"  # WebP starts with RIFF
WEBP_WEBP = b"WEBP"  # WebP has "WEBP" at bytes 8-11
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

    elif content_type == "image/webp":
        # WebP: RIFF....WEBP format
        return data.startswith(WEBP_RIFF) and WEBP_WEBP in data[:12]

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
        "image/webp": ".webp",
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


class FileTracker:
    """
    Rastreador de arquivos com reference counting para cleanup seguro.

    Evita race conditions onde um arquivo é deletado enquanto está em uso.
    """

    # TTL padrão de 1 hora para arquivos não referenciados
    DEFAULT_TTL = 3600

    def __init__(self):
        self._refs: Dict[Path, int] = {}
        self._timestamps: Dict[Path, float] = {}
        self._lock = Lock()

    def acquire(self, path: Path) -> None:
        """
        Marca um arquivo como em uso.

        Args:
            path: Caminho do arquivo
        """
        with self._lock:
            self._refs[path] = self._refs.get(path, 0) + 1
            self._timestamps[path] = time()

    def release(self, path: Path) -> bool:
        """
        Libera uma referência ao arquivo.

        Args:
            path: Caminho do arquivo

        Returns:
            True se o arquivo pode ser deletado (refs == 0)
        """
        with self._lock:
            if path not in self._refs:
                return True

            self._refs[path] = self._refs.get(path, 1) - 1

            if self._refs[path] <= 0:
                del self._refs[path]
                if path in self._timestamps:
                    del self._timestamps[path]
                return True

            return False

    def is_in_use(self, path: Path) -> bool:
        """Verifica se um arquivo está em uso."""
        with self._lock:
            return self._refs.get(path, 0) > 0

    def get_stale_files(self, ttl: int = DEFAULT_TTL) -> List[Path]:
        """
        Retorna arquivos que não são referenciados há mais de TTL segundos.

        Args:
            ttl: Time-to-live em segundos

        Returns:
            Lista de caminhos de arquivos stale
        """
        now = time()
        stale = []

        with self._lock:
            for path, timestamp in list(self._timestamps.items()):
                if now - timestamp > ttl and self._refs.get(path, 0) == 0:
                    stale.append(path)

        return stale


# Instância global do tracker
file_tracker = FileTracker()


def atomic_json_write(filepath: Path, data: dict, base_dir: Path = None) -> None:
    """
    Escreve JSON atomicamente usando temp + replace.

    Args:
        filepath: Caminho do arquivo destino
        data: Dados para serializar como JSON
        base_dir: Diretorio base para criar se nao existir (opcional)
    """
    import json
    import os
    import tempfile

    if base_dir:
        base_dir.mkdir(parents=True, exist_ok=True)

    fd, temp_path = tempfile.mkstemp(
        dir=filepath.parent, prefix=f".{filepath.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())  # Garante dados no disco antes do replace
        os.replace(temp_path, filepath)
    except Exception:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise


def cleanup_files(paths: List[Path]) -> None:
    """
    Remove lista de arquivos de forma segura.

    Verifica se os arquivos não estão em uso antes de deletar.
    Loga erros ao invés de ignorá-los silenciosamente.

    Args:
        paths: Lista de caminhos para remover
    """
    for path in paths:
        try:
            if not path:
                continue

            # Verifica se arquivo está em uso
            if file_tracker.is_in_use(path):
                logger.debug(f"Arquivo em uso, não deletado: {path}")
                continue

            if path.exists():
                path.unlink()
                logger.debug(f"Arquivo removido: {path}")

        except PermissionError as e:
            logger.warning(f"Permissão negada ao remover {path}: {e}")
        except FileNotFoundError:
            # Arquivo já foi removido, ok
            pass
        except Exception as e:
            logger.warning(f"Erro ao remover {path}: {e}")


