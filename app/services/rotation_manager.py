"""
Gerenciador de rotação automática de imagens da galeria.

Implementa rotação de GIFs no Pixoo 64 com:
- Loop asyncio em background
- Persistência de configuração para retomada
- Adição/remoção dinâmica de itens
- Pausa automática se Pixoo desconectar
"""

import asyncio
import json
import logging
import os
import random
import tempfile
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Literal, Optional, Set

from app.config import ROTATION_CONFIG_FILE, ROTATION_RECONNECT_CHECK_INTERVAL, USER_DATA_DIR

logger = logging.getLogger(__name__)

# Intervalos disponíveis (em segundos)
ROTATION_INTERVALS = {
    60: "1 minuto",
    120: "2 minutos",
    300: "5 minutos",
}


@dataclass
class RotationConfig:
    """Configuração persistida de rotação."""

    selected_ids: List[str]
    interval_seconds: int
    updated_at: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "RotationConfig":
        return cls(
            selected_ids=data["selected_ids"],
            interval_seconds=data["interval_seconds"],
            updated_at=data["updated_at"],
        )


@dataclass
class RotationStatus:
    """Status atual da rotação."""

    is_active: bool
    is_paused: bool  # True se pausado por desconexão
    selected_ids: List[str]
    selected_count: int
    interval_seconds: int
    interval_label: str
    current_index: int
    has_saved_config: bool


class RotationManager:
    """
    Singleton thread-safe para gerenciar rotação automática de imagens.

    Uso:
        manager = RotationManager()
        manager.start(["id1", "id2", "id3"], interval_seconds=120)
        manager.add_item("id4")
        manager.remove_item("id2")
        manager.stop()
    """

    _instance: Optional["RotationManager"] = None
    _instance_lock = threading.Lock()

    def __new__(cls) -> "RotationManager":
        if cls._instance is None:
            with cls._instance_lock:
                # Double-check locking
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # Estado da rotação
        self._is_active: bool = False
        self._is_paused: bool = False
        self._selected_ids: List[str] = []
        self._interval_seconds: int = 120
        self._current_index: int = 0
        self._shuffled_order: List[str] = []

        # Controle de tasks
        self._rotation_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None

        # Lock para proteger estado
        self._state_lock = threading.RLock()

        # Referência ao event loop (será setado quando iniciar)
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        logger.info("RotationManager inicializado")

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        """Obtém o event loop atual ou cria um novo."""
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.get_event_loop()

    def start(
        self,
        selected_ids: List[str],
        interval_seconds: int,
    ) -> bool:
        """
        Inicia rotação com os IDs e intervalo especificados.

        Args:
            selected_ids: Lista de IDs de itens da galeria
            interval_seconds: Intervalo entre trocas em segundos

        Returns:
            True se iniciou com sucesso
        """
        if not selected_ids:
            logger.warning("Tentativa de iniciar rotação sem IDs")
            return False

        if interval_seconds not in ROTATION_INTERVALS:
            logger.warning(f"Intervalo inválido: {interval_seconds}")
            return False

        # Validar IDs existem na galeria
        valid_ids = self._validate_ids(selected_ids)
        if not valid_ids:
            logger.warning("Nenhum ID válido para rotação")
            return False

        with self._state_lock:
            # Parar rotação anterior se existir
            if self._is_active:
                self._stop_internal()

            self._selected_ids = valid_ids
            self._interval_seconds = interval_seconds
            self._current_index = 0
            self._shuffle_order()
            self._is_active = True
            self._is_paused = False

            # Salvar configuração
            self._save_config()

            # Iniciar loop de rotação
            self._start_rotation_loop()

            logger.info(
                f"Rotação iniciada: {len(valid_ids)} imagens, "
                f"intervalo {ROTATION_INTERVALS[interval_seconds]}"
            )
            return True

    def stop(self) -> bool:
        """
        Para a rotação ativa.

        Returns:
            True se parou com sucesso
        """
        with self._state_lock:
            if not self._is_active:
                return False

            self._stop_internal()
            # Salvar config antes de parar (para poder retomar)
            self._save_config()

            logger.info("Rotação parada")
            return True

    def _stop_internal(self) -> None:
        """Para rotação sem salvar config (uso interno)."""
        self._is_active = False
        self._is_paused = False

        if self._rotation_task and not self._rotation_task.done():
            self._rotation_task.cancel()
            self._rotation_task = None

        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            self._reconnect_task = None

    def resume(self) -> bool:
        """
        Retoma última configuração salva.

        Returns:
            True se retomou com sucesso
        """
        config = self._load_config()
        if not config:
            logger.warning("Nenhuma configuração salva para retomar")
            return False

        return self.start(config.selected_ids, config.interval_seconds)

    def add_item(self, item_id: str) -> bool:
        """
        Adiciona item à rotação ativa.

        Args:
            item_id: ID do item a adicionar

        Returns:
            True se adicionou com sucesso
        """
        # Validar ID existe
        valid = self._validate_ids([item_id])
        if not valid:
            return False

        with self._state_lock:
            if not self._is_active:
                return False

            if item_id in self._selected_ids:
                return True  # Já está na lista

            self._selected_ids.append(item_id)
            # Adicionar ao final da ordem atual
            self._shuffled_order.append(item_id)
            self._save_config()

            logger.info(f"Item {item_id} adicionado à rotação")
            return True

    def remove_item(self, item_id: str) -> bool:
        """
        Remove item da rotação ativa.

        Args:
            item_id: ID do item a remover

        Returns:
            True se removeu com sucesso
        """
        with self._state_lock:
            if not self._is_active:
                return False

            if item_id not in self._selected_ids:
                return False

            self._selected_ids.remove(item_id)

            # Remover da ordem e ajustar índice
            if item_id in self._shuffled_order:
                idx = self._shuffled_order.index(item_id)
                self._shuffled_order.remove(item_id)
                # Ajustar índice se removeu item antes do atual
                if idx < self._current_index:
                    self._current_index -= 1
                # Se removeu o item atual, não precisa ajustar (próximo loop pega o próximo)

            # Se ficou sem itens, parar rotação
            if not self._selected_ids:
                self._stop_internal()
                self._delete_config()
                logger.info("Rotação parada: nenhum item restante")
                return True

            self._save_config()
            logger.info(f"Item {item_id} removido da rotação")
            return True

    def get_status(self) -> RotationStatus:
        """Retorna status atual da rotação."""
        with self._state_lock:
            saved_config = self._load_config() if not self._is_active else None
            has_saved = saved_config is not None

            # Se rotação ativa, mostrar IDs atuais
            # Se não ativa mas tem config salva, mostrar IDs da config (para badges)
            # Se não ativa e sem config, retornar lista vazia
            if self._is_active:
                ids = self._selected_ids.copy()
            elif has_saved:
                ids = saved_config.selected_ids
            else:
                ids = []

            return RotationStatus(
                is_active=self._is_active,
                is_paused=self._is_paused,
                selected_ids=ids,
                selected_count=len(ids),
                interval_seconds=self._interval_seconds,
                interval_label=ROTATION_INTERVALS.get(self._interval_seconds, ""),
                current_index=self._current_index,
                has_saved_config=has_saved,
            )

    def delete_saved_config(self) -> bool:
        """
        Deleta configuração salva (botão X no banner retomar).

        Returns:
            True se deletou
        """
        return self._delete_config()

    def _validate_ids(self, ids: List[str]) -> List[str]:
        """Valida e retorna apenas IDs que existem na galeria."""
        from app.services.gallery_manager import gallery

        valid = []
        for item_id in ids:
            if gallery.get_item(item_id) is not None:
                valid.append(item_id)
            else:
                logger.debug(f"ID inválido ignorado: {item_id}")
        return valid

    def _shuffle_order(self) -> None:
        """Embaralha ordem das imagens."""
        self._shuffled_order = self._selected_ids.copy()
        random.shuffle(self._shuffled_order)
        self._current_index = 0

    def _start_rotation_loop(self) -> None:
        """Inicia task de rotação no event loop."""
        try:
            loop = self._get_loop()
            self._rotation_task = loop.create_task(self._rotation_loop())
        except Exception as e:
            logger.error(f"Erro ao iniciar loop de rotação: {e}")

    async def _rotation_loop(self) -> None:
        """Loop principal de rotação."""
        from app.services.gallery_manager import gallery
        from app.services.pixoo_connection import get_pixoo_connection
        from app.services.pixoo_upload import upload_gif

        logger.info("Loop de rotação iniciado")
        consecutive_failures = 0
        max_failures = 3

        while self._is_active:
            try:
                # Verificar conexão
                conn = get_pixoo_connection()
                if not conn.is_connected:
                    await self._handle_disconnection()
                    continue

                # Obter próximo item
                with self._state_lock:
                    if not self._shuffled_order:
                        logger.warning("Lista de rotação vazia")
                        break

                    # Re-shuffle se completou o ciclo
                    if self._current_index >= len(self._shuffled_order):
                        self._shuffle_order()
                        logger.debug("Ciclo completo, re-shuffled")

                    current_id = self._shuffled_order[self._current_index]
                    interval = self._interval_seconds

                # Obter caminho do GIF
                gif_path = gallery.get_gif_path(current_id)
                if not gif_path:
                    logger.warning(f"GIF não encontrado: {current_id}")
                    # Remover ID inválido
                    self.remove_item(current_id)
                    continue

                # Enviar para Pixoo
                try:
                    result = upload_gif(gif_path)
                    consecutive_failures = 0
                    # Obter nome do item para log mais legível
                    item = gallery.get_item(current_id)
                    item_name = item.name if item else current_id
                    logger.info(
                        f"🔄 Rotação: '{item_name}' "
                        f"({result.get('frames_sent', '?')} frames) "
                        f"[{self._current_index + 1}/{len(self._shuffled_order)}]"
                    )
                except Exception as e:
                    consecutive_failures += 1
                    logger.warning(
                        f"Falha ao enviar {current_id}: {e} "
                        f"({consecutive_failures}/{max_failures})"
                    )
                    if consecutive_failures >= max_failures:
                        logger.error("Muitas falhas consecutivas, pulando item")
                        consecutive_failures = 0

                # Avançar índice
                with self._state_lock:
                    self._current_index += 1

                # Aguardar intervalo
                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                logger.info("Loop de rotação cancelado")
                break
            except Exception as e:
                logger.error(f"Erro no loop de rotação: {e}")
                await asyncio.sleep(5)  # Pequena pausa antes de tentar novamente

        logger.info("Loop de rotação finalizado")

    async def _handle_disconnection(self) -> None:
        """Lida com desconexão do Pixoo."""
        with self._state_lock:
            if self._is_paused:
                # Já está pausado, aguardar reconexão
                await asyncio.sleep(ROTATION_RECONNECT_CHECK_INTERVAL)
                return

            self._is_paused = True
            logger.info("Rotação pausada: Pixoo desconectado")

        # Iniciar verificação periódica de reconexão
        await self._wait_for_reconnection()

    async def _wait_for_reconnection(self) -> None:
        """Aguarda Pixoo reconectar."""
        from app.services.pixoo_connection import get_pixoo_connection

        while self._is_active and self._is_paused:
            await asyncio.sleep(ROTATION_RECONNECT_CHECK_INTERVAL)

            conn = get_pixoo_connection()
            if conn.is_connected:
                with self._state_lock:
                    self._is_paused = False
                logger.info("Rotação retomada: Pixoo reconectado")
                return

    def _save_config(self) -> None:
        """Salva configuração atual atomicamente."""
        with self._state_lock:
            if not self._selected_ids:
                return

            config = RotationConfig(
                selected_ids=self._selected_ids.copy(),
                interval_seconds=self._interval_seconds,
                updated_at=datetime.now(timezone.utc).isoformat(),
            )

        data = {"version": 1, **config.to_dict()}
        self._atomic_json_write(ROTATION_CONFIG_FILE, data)
        logger.debug("Configuração de rotação salva")

    def _load_config(self) -> Optional[RotationConfig]:
        """Carrega configuração salva."""
        if not ROTATION_CONFIG_FILE.exists():
            return None

        try:
            with open(ROTATION_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Validar versão
            if data.get("version") != 1:
                logger.warning("Versão de config incompatível")
                return None

            config = RotationConfig.from_dict(data)

            # Validar IDs ainda existem
            valid_ids = self._validate_ids(config.selected_ids)
            if not valid_ids:
                logger.warning("Config salva não tem IDs válidos")
                self._delete_config()
                return None

            # Atualizar config se alguns IDs foram removidos
            if len(valid_ids) != len(config.selected_ids):
                config.selected_ids = valid_ids

            return config

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Erro ao carregar config de rotação: {e}")
            return None

    def _delete_config(self) -> bool:
        """Deleta arquivo de configuração."""
        try:
            if ROTATION_CONFIG_FILE.exists():
                ROTATION_CONFIG_FILE.unlink()
                logger.debug("Configuração de rotação deletada")
            return True
        except Exception as e:
            logger.error(f"Erro ao deletar config: {e}")
            return False

    def _atomic_json_write(self, filepath: Path, data: dict) -> None:
        """Escreve JSON atomicamente usando temp + replace."""
        # Garantir diretório existe
        USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

        # Criar temp file no mesmo diretório
        fd, temp_path = tempfile.mkstemp(
            dir=filepath.parent, prefix=f".{filepath.name}.", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(temp_path, filepath)
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise


# Instância global (singleton)
def get_rotation_manager() -> RotationManager:
    """Retorna a instância singleton do RotationManager."""
    return RotationManager()
