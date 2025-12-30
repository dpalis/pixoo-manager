"""
Gerenciador de uploads com TTL e cleanup automático.

Substitui os dicts _uploads espalhados pelos routers por um
gerenciador centralizado com limpeza automática de entradas antigas.
"""

import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from time import time
from typing import Any, Dict, Optional, Tuple

from fastapi import HTTPException

from app.services.file_utils import cleanup_files


# TTL padrão: 1 hora
DEFAULT_TTL = 3600


@dataclass
class UploadEntry:
    """Entrada de upload com metadados e timestamp."""
    data: Dict[str, Any]
    created_at: float = field(default_factory=time)

    def is_expired(self, ttl: int = DEFAULT_TTL) -> bool:
        """Verifica se a entrada expirou."""
        return time() - self.created_at > ttl


class UploadManager:
    """
    Gerenciador thread-safe de uploads com TTL automático.

    Uso:
        manager = UploadManager(ttl=3600)  # 1 hora

        # Adicionar upload
        manager.set("abc123", {"path": Path(...), "metadata": {...}})

        # Obter upload
        data = manager.get("abc123")

        # Remover upload
        manager.delete("abc123")

        # Limpar expirados
        manager.cleanup_expired()
    """

    def __init__(self, ttl: int = DEFAULT_TTL, name: str = "uploads"):
        """
        Args:
            ttl: Time-to-live em segundos para entradas
            name: Nome do manager (para logging)
        """
        self.ttl = ttl
        self.name = name
        self._entries: Dict[str, UploadEntry] = {}
        self._lock = threading.RLock()

    def set(self, upload_id: str, data: Dict[str, Any]) -> None:
        """
        Adiciona ou atualiza uma entrada.

        Args:
            upload_id: ID único do upload
            data: Dados do upload (path, metadata, etc.)
        """
        with self._lock:
            self._entries[upload_id] = UploadEntry(data=data)

    def get(self, upload_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtém dados de um upload.

        Args:
            upload_id: ID do upload

        Returns:
            Dados do upload ou None se não encontrado/expirado
        """
        with self._lock:
            entry = self._entries.get(upload_id)
            if entry is None:
                return None

            # Verificar expiração
            if entry.is_expired(self.ttl):
                self._delete_entry(upload_id, entry)
                return None

            return entry.data

    def update(self, upload_id: str, **kwargs) -> bool:
        """
        Atualiza campos de um upload existente.

        Args:
            upload_id: ID do upload
            **kwargs: Campos para atualizar

        Returns:
            True se atualizado, False se não encontrado
        """
        with self._lock:
            entry = self._entries.get(upload_id)
            if entry is None or entry.is_expired(self.ttl):
                return False

            entry.data.update(kwargs)
            return True

    def delete(self, upload_id: str) -> bool:
        """
        Remove um upload e seus arquivos.

        Args:
            upload_id: ID do upload

        Returns:
            True se removido, False se não encontrado
        """
        with self._lock:
            entry = self._entries.get(upload_id)
            if entry is None:
                return False

            self._delete_entry(upload_id, entry)
            return True

    def _delete_entry(self, upload_id: str, entry: UploadEntry) -> None:
        """Remove entrada e limpa arquivos associados."""
        # Coletar paths para cleanup
        paths_to_clean = []
        if "path" in entry.data and entry.data["path"]:
            paths_to_clean.append(entry.data["path"])
        if "converted_path" in entry.data and entry.data["converted_path"]:
            paths_to_clean.append(entry.data["converted_path"])

        # Limpar arquivos
        if paths_to_clean:
            cleanup_files(paths_to_clean)

        # Remover entrada
        del self._entries[upload_id]

    def exists(self, upload_id: str) -> bool:
        """Verifica se um upload existe e não expirou."""
        return self.get(upload_id) is not None

    def cleanup_expired(self) -> int:
        """
        Remove todas as entradas expiradas.

        Returns:
            Número de entradas removidas
        """
        with self._lock:
            expired_ids = [
                uid for uid, entry in self._entries.items()
                if entry.is_expired(self.ttl)
            ]

            for uid in expired_ids:
                entry = self._entries.get(uid)
                if entry:
                    self._delete_entry(uid, entry)

            return len(expired_ids)

    def count(self) -> int:
        """Retorna número de entradas (incluindo expiradas)."""
        with self._lock:
            return len(self._entries)

    def clear(self) -> int:
        """
        Remove todas as entradas (para testes).

        Returns:
            Número de entradas removidas
        """
        with self._lock:
            count = len(self._entries)
            ids_to_delete = list(self._entries.keys())

            for uid in ids_to_delete:
                entry = self._entries.get(uid)
                if entry:
                    self._delete_entry(uid, entry)

            return count

    def __contains__(self, upload_id: str) -> bool:
        """Permite usar 'in' operator."""
        return self.exists(upload_id)


# Padrão para validação de upload_id: 8 caracteres hexadecimais
UPLOAD_ID_PATTERN = re.compile(r'^[a-f0-9]{8}$')


def validate_upload_id(upload_id: str) -> str:
    """
    Valida formato do upload_id.

    Args:
        upload_id: ID do upload (deve ser 8 caracteres hex)

    Returns:
        O upload_id validado

    Raises:
        HTTPException 400: Se formato inválido
    """
    if not UPLOAD_ID_PATTERN.match(upload_id):
        raise HTTPException(status_code=400, detail="ID de upload inválido")
    return upload_id


def get_upload_or_404(
    manager: UploadManager,
    upload_id: str,
    path_key: str = "path"
) -> Tuple[Dict[str, Any], Path]:
    """
    Obtém upload e valida que arquivo existe.

    Valida o formato do upload_id, busca no manager, e verifica
    que o arquivo ainda existe no filesystem.

    Args:
        manager: UploadManager a consultar
        upload_id: ID do upload
        path_key: Chave do path no dict (default: "path")

    Returns:
        Tupla (upload_info, path)

    Raises:
        HTTPException 400: Se upload_id inválido
        HTTPException 404: Se upload ou arquivo não encontrado
    """
    validate_upload_id(upload_id)

    upload_info = manager.get(upload_id)
    if upload_info is None:
        raise HTTPException(status_code=404, detail="Upload não encontrado")

    path = upload_info.get(path_key)
    if not path or not path.exists():
        manager.delete(upload_id)
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")

    return upload_info, path


# Instâncias globais para cada tipo de upload
gif_uploads = UploadManager(ttl=DEFAULT_TTL, name="gif_uploads")
media_uploads = UploadManager(ttl=DEFAULT_TTL, name="media_uploads")
youtube_downloads = UploadManager(ttl=DEFAULT_TTL, name="youtube_downloads")
