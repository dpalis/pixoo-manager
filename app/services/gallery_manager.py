"""
Gerenciador de galeria persistente de GIFs.

Armazena GIFs convertidos permanentemente em ~/.pixoo_manager/gallery/
com metadados em JSON e thumbnails para preview rápido.
"""

import json
import os
import re
import shutil
import tempfile
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from PIL import Image

from app.config import GALLERY_DIR


@dataclass
class GalleryItem:
    """Item da galeria com metadados."""

    id: str
    name: str
    filename: str
    source_type: str  # "gif", "image", "video", "youtube"
    created_at: str
    file_size_bytes: int
    frame_count: int
    is_favorite: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário serializável."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GalleryItem":
        """Cria instância a partir de dicionário."""
        return cls(**data)


# Padrão para nomes válidos: alfanumérico, espaço, hífen, underscore, parênteses, ponto
NAME_PATTERN = re.compile(r"^[\w\s\-_().]+$", re.UNICODE)
MAX_NAME_LENGTH = 100


class GalleryManager:
    """
    Gerenciador thread-safe de galeria com persistência em JSON.

    Estrutura no disco:
        ~/.pixoo_manager/gallery/
        ├── gifs/           # GIFs salvos (UUID.gif)
        ├── thumbnails/     # Thumbnails 128x128 JPEG
        ├── metadata.json   # Índice com metadados
        └── metadata.json.bak # Backup automático
    """

    def __init__(self, gallery_dir: Path = GALLERY_DIR):
        """
        Args:
            gallery_dir: Diretório raiz da galeria
        """
        self.gallery_dir = gallery_dir
        self.gifs_dir = gallery_dir / "gifs"
        self.thumbnails_dir = gallery_dir / "thumbnails"
        self.metadata_path = gallery_dir / "metadata.json"
        self.backup_path = gallery_dir / "metadata.json.bak"

        self._lock = threading.RLock()
        self._items: Dict[str, GalleryItem] = {}

        self._ensure_directories()
        self._load_metadata()

    def _ensure_directories(self) -> None:
        """Cria estrutura de diretórios se não existir."""
        self.gallery_dir.mkdir(parents=True, exist_ok=True)
        self.gifs_dir.mkdir(exist_ok=True)
        self.thumbnails_dir.mkdir(exist_ok=True)

    def _load_metadata(self) -> None:
        """Carrega metadados do JSON, com fallback para backup."""
        if not self.metadata_path.exists():
            if self.backup_path.exists():
                # Tenta recuperar do backup
                if self._recover_from_backup():
                    return
            # Nenhum arquivo existe, começar vazio
            self._items = {}
            return

        try:
            with open(self.metadata_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            items_data = data.get("items", {})
            self._items = {
                item_id: GalleryItem.from_dict(item_data)
                for item_id, item_data in items_data.items()
            }
        except (json.JSONDecodeError, KeyError, TypeError):
            # Arquivo corrompido, tenta backup
            if self._recover_from_backup():
                return
            # Backup também falhou, reconstrói do disco
            self._rebuild_from_files()

    def _save_metadata(self) -> None:
        """Salva metadados atomicamente com backup."""
        data = {
            "items": {item_id: item.to_dict() for item_id, item in self._items.items()},
        }
        self._atomic_json_write(self.metadata_path, data)

    def _atomic_json_write(self, filepath: Path, data: dict) -> None:
        """Escreve JSON atomicamente usando temp + replace."""
        # Backup antes de escrever
        if filepath.exists():
            shutil.copy2(filepath, self.backup_path)

        # Criar temp file no mesmo diretório (mesmo filesystem para atomic replace)
        fd, temp_path = tempfile.mkstemp(
            dir=filepath.parent, prefix=f".{filepath.name}.", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(temp_path, filepath)  # Atômico no mesmo filesystem
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    def _recover_from_backup(self) -> bool:
        """Tenta recuperar metadados do backup."""
        if not self.backup_path.exists():
            return False

        try:
            with open(self.backup_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            items_data = data.get("items", {})
            self._items = {
                item_id: GalleryItem.from_dict(item_data)
                for item_id, item_data in items_data.items()
            }

            # Restaura o arquivo principal
            shutil.copy2(self.backup_path, self.metadata_path)
            return True
        except Exception:
            return False

    def _rebuild_from_files(self) -> int:
        """Reconstrói metadados escaneando arquivos GIF no disco."""
        self._items = {}
        count = 0

        for gif_path in self.gifs_dir.glob("*.gif"):
            item_id = gif_path.stem
            try:
                # Extrair informações do GIF
                with Image.open(gif_path) as img:
                    frame_count = getattr(img, "n_frames", 1)

                stat = gif_path.stat()
                item = GalleryItem(
                    id=item_id,
                    name=f"Recovered {item_id[:8]}",
                    filename=gif_path.name,
                    source_type="unknown",
                    created_at=datetime.fromtimestamp(
                        stat.st_ctime, tz=timezone.utc
                    ).isoformat(),
                    file_size_bytes=stat.st_size,
                    frame_count=frame_count,
                    is_favorite=False,
                )
                self._items[item_id] = item

                # Regenerar thumbnail se não existir
                thumb_path = self.thumbnails_dir / f"{item_id}.jpg"
                if not thumb_path.exists():
                    self._generate_thumbnail(gif_path, thumb_path)

                count += 1
            except Exception:
                # Arquivo inválido, ignorar
                continue

        if self._items:
            self._save_metadata()

        return count

    def _generate_thumbnail(self, gif_path: Path, output_path: Path) -> None:
        """Gera thumbnail 128x128 com NEAREST para pixel art."""
        with Image.open(gif_path) as img:
            img.seek(0)  # Primeiro frame
            frame = img.convert("RGB")
            # 2x scale para retina (64->128) com NEAREST para preservar pixels
            scaled = frame.resize((128, 128), Image.Resampling.NEAREST)
            scaled.save(output_path, "JPEG", quality=85, optimize=True)

    def _sanitize_name(self, name: str) -> str:
        """Remove caracteres inválidos do nome."""
        if not name or not name.strip():
            # Gerar nome baseado em timestamp
            return datetime.now().strftime("gif_%Y%m%d_%H%M%S")

        # Limitar tamanho
        name = name.strip()[:MAX_NAME_LENGTH]

        # Remover caracteres inválidos
        sanitized = "".join(c for c in name if c.isalnum() or c in " -_().")
        sanitized = sanitized.strip()

        if not sanitized:
            return datetime.now().strftime("gif_%Y%m%d_%H%M%S")

        return sanitized

    def _generate_unique_name(self, name: str) -> str:
        """Gera nome único adicionando (2), (3), etc se necessário."""
        existing_names = {item.name.lower() for item in self._items.values()}

        if name.lower() not in existing_names:
            return name

        # Encontrar próximo número disponível
        base_name = name
        counter = 2
        while True:
            new_name = f"{base_name} ({counter})"
            if new_name.lower() not in existing_names:
                return new_name
            counter += 1

    def save_gif(
        self,
        source_path: Path,
        name: str,
        source_type: str,
        frame_count: Optional[int] = None,
    ) -> Tuple[GalleryItem, Optional[str]]:
        """
        Salva GIF na galeria.

        Args:
            source_path: Caminho do GIF a salvar
            name: Nome para o item
            source_type: Tipo de origem ("gif", "image", "video", "youtube")
            frame_count: Número de frames (opcional, detectado automaticamente)

        Returns:
            (GalleryItem criado, warning message ou None)

        Raises:
            FileNotFoundError: Se arquivo fonte não existe
        """
        if not source_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {source_path}")

        file_size = source_path.stat().st_size

        # Detectar frame count fora do lock (I/O)
        if frame_count is None:
            with Image.open(source_path) as img:
                frame_count = getattr(img, "n_frames", 1)

        with self._lock:
            # Gerar ID único
            item_id = uuid4().hex[:8]

            # Sanitizar e garantir nome único
            safe_name = self._sanitize_name(name)
            unique_name = self._generate_unique_name(safe_name)

            # Preparar caminhos
            gif_filename = f"{item_id}.gif"
            gif_path = self.gifs_dir / gif_filename
            thumb_path = self.thumbnails_dir / f"{item_id}.jpg"

            try:
                # Copiar GIF
                shutil.copy2(source_path, gif_path)

                # Criar item
                item = GalleryItem(
                    id=item_id,
                    name=unique_name,
                    filename=gif_filename,
                    source_type=source_type,
                    created_at=datetime.now(timezone.utc).isoformat(),
                    file_size_bytes=file_size,
                    frame_count=frame_count,
                    is_favorite=False,
                )

                self._items[item_id] = item
                self._save_metadata()
            except Exception:
                # Rollback: limpar arquivos criados em caso de falha
                if gif_path.exists():
                    gif_path.unlink()
                if item_id in self._items:
                    del self._items[item_id]
                raise

        # Gerar thumbnail FORA do lock (I/O pesado, não crítico)
        try:
            self._generate_thumbnail(gif_path, thumb_path)
        except Exception:
            # Thumbnail falhou mas item foi salvo - será regenerado sob demanda
            pass

        return item, None

    def list_items(
        self,
        page: int = 1,
        per_page: int = 50,
        favorites_only: bool = False,
        search: Optional[str] = None,
    ) -> Tuple[List[GalleryItem], int]:
        """
        Lista itens da galeria com paginação.

        Args:
            page: Número da página (1-indexed)
            per_page: Itens por página
            favorites_only: Filtrar apenas favoritos
            search: Termo de busca no nome

        Returns:
            (lista de itens, total de itens filtrados)
        """
        with self._lock:
            items = list(self._items.values())

            # Filtrar
            if favorites_only:
                items = [i for i in items if i.is_favorite]
            if search:
                search_lower = search.lower()
                items = [i for i in items if search_lower in i.name.lower()]

            total = len(items)

            # Ordenar: favoritos primeiro, depois alfabético
            items.sort(key=lambda i: (not i.is_favorite, i.name.lower()))

            # Paginar
            start = (page - 1) * per_page
            end = start + per_page
            items = items[start:end]

            return items, total

    def get_item(self, item_id: str) -> Optional[GalleryItem]:
        """Obtém item por ID."""
        with self._lock:
            return self._items.get(item_id)

    def delete_item(self, item_id: str) -> bool:
        """
        Remove item da galeria.

        Returns:
            True se removido, False se não encontrado
        """
        with self._lock:
            item = self._items.get(item_id)
            if item is None:
                return False

            gif_path = self.gifs_dir / item.filename
            thumb_path = self.thumbnails_dir / f"{item_id}.jpg"

            # PRIMEIRO: Atualizar metadata (operação reversível via backup)
            del self._items[item_id]
            self._save_metadata()

            # DEPOIS: Deletar arquivos (sem necessidade de rollback)
            if gif_path.exists():
                gif_path.unlink()
            if thumb_path.exists():
                thumb_path.unlink()

            return True

    def delete_items(self, item_ids: List[str]) -> int:
        """
        Remove múltiplos itens da galeria.

        Args:
            item_ids: Lista de IDs a remover

        Returns:
            Quantidade de itens removidos
        """
        with self._lock:
            deleted = 0
            files_to_delete: List[Path] = []

            for item_id in item_ids:
                item = self._items.get(item_id)
                if item is None:
                    continue

                # Coletar arquivos para deletar
                gif_path = self.gifs_dir / item.filename
                thumb_path = self.thumbnails_dir / f"{item_id}.jpg"
                files_to_delete.append(gif_path)
                files_to_delete.append(thumb_path)

                del self._items[item_id]
                deleted += 1

            if deleted > 0:
                # PRIMEIRO: Salvar metadata
                self._save_metadata()

                # DEPOIS: Deletar arquivos
                for path in files_to_delete:
                    if path.exists():
                        path.unlink()

            return deleted

    def delete_all(self) -> int:
        """
        Remove TODOS os itens da galeria.

        ⚠️ AÇÃO IRREVERSÍVEL

        Returns:
            Quantidade de itens removidos
        """
        with self._lock:
            count = len(self._items)

            if count == 0:
                return 0

            # PRIMEIRO: Limpar metadata
            self._items.clear()
            self._save_metadata()

            # DEPOIS: Limpar diretórios
            for gif in self.gifs_dir.glob("*.gif"):
                gif.unlink()
            for thumb in self.thumbnails_dir.glob("*.jpg"):
                thumb.unlink()

            return count

    def update_item(
        self,
        item_id: str,
        name: Optional[str] = None,
        is_favorite: Optional[bool] = None,
    ) -> Optional[GalleryItem]:
        """
        Atualiza metadados de um item.

        Returns:
            Item atualizado ou None se não encontrado
        """
        with self._lock:
            item = self._items.get(item_id)
            if item is None:
                return None

            if name is not None:
                safe_name = self._sanitize_name(name)
                # Verificar unicidade excluindo o próprio item
                existing_names = {
                    i.name.lower() for i in self._items.values() if i.id != item_id
                }
                if safe_name.lower() in existing_names:
                    # Gerar nome único
                    safe_name = self._generate_unique_name(safe_name)
                item.name = safe_name

            if is_favorite is not None:
                item.is_favorite = is_favorite

            self._save_metadata()
            return item

    def get_gif_path(self, item_id: str) -> Optional[Path]:
        """Retorna caminho do GIF."""
        with self._lock:
            item = self._items.get(item_id)
            if item is None:
                return None
            path = self.gifs_dir / item.filename
            return path if path.exists() else None

    def get_thumbnail_path(self, item_id: str) -> Optional[Path]:
        """Retorna caminho do thumbnail, regenerando se necessário."""
        with self._lock:
            item = self._items.get(item_id)
            if item is None:
                return None

        thumb_path = self.thumbnails_dir / f"{item_id}.jpg"
        if thumb_path.exists():
            return thumb_path

        # Regenerar thumbnail se GIF existe mas thumbnail não
        gif_path = self.gifs_dir / item.filename
        if gif_path.exists():
            try:
                self._generate_thumbnail(gif_path, thumb_path)
                return thumb_path
            except Exception:
                pass

        return None

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas da galeria."""
        with self._lock:
            return {
                "item_count": len(self._items),
                "favorites_count": sum(1 for i in self._items.values() if i.is_favorite),
            }


# Instância global
gallery = GalleryManager()
