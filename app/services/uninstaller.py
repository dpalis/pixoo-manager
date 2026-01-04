"""
Uninstaller service.

Remove dados do usuário (~/.pixoo_manager/) durante a desinstalação.
"""

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from app.config import USER_DATA_DIR

logger = logging.getLogger(__name__)


@dataclass
class UninstallResult:
    """Resultado da desinstalação."""

    success: bool
    deleted_path: str
    deleted_size_bytes: int = 0
    failed_files: List[str] = field(default_factory=list)
    error: Optional[str] = None


class Uninstaller:
    """
    Remove dados do usuário durante a desinstalação.

    Limpa ~/.pixoo_manager/ com seus subdiretórios (gallery, temp, etc.)
    """

    def __init__(self, data_dir: Path = USER_DATA_DIR):
        self.data_dir = data_dir

    def cleanup_user_data(self) -> UninstallResult:
        """
        Remove todos os dados do usuário.

        Desconecta do Pixoo antes de remover.
        Trata diretório inexistente como sucesso.

        Returns:
            UninstallResult com detalhes da operação
        """
        # Desconectar do Pixoo se conectado
        self._disconnect_pixoo()

        if not self.data_dir.exists():
            # Diretório não existe = sucesso (nada a remover)
            return UninstallResult(
                success=True,
                deleted_path=str(self.data_dir),
                deleted_size_bytes=0,
            )

        # Calcular tamanho antes de remover
        total_size = self._calculate_size(self.data_dir)

        # Remover diretório
        success, failed_files = self._safe_rmtree(self.data_dir)

        if success:
            return UninstallResult(
                success=True,
                deleted_path=str(self.data_dir),
                deleted_size_bytes=total_size,
            )
        else:
            return UninstallResult(
                success=False,
                deleted_path=str(self.data_dir),
                deleted_size_bytes=total_size,
                failed_files=failed_files,
                error="Sem permissão para remover alguns arquivos.",
            )

    def _disconnect_pixoo(self) -> None:
        """Desconecta do Pixoo se conectado."""
        try:
            from app.services.pixoo_connection import get_pixoo_connection

            conn = get_pixoo_connection()
            if conn.is_connected:
                conn.disconnect()
                logger.info("Pixoo desconectado antes da desinstalação")
        except Exception as e:
            logger.warning(f"Erro ao desconectar Pixoo: {e}")

    def _calculate_size(self, path: Path) -> int:
        """
        Calcula tamanho total de um diretório.

        Returns:
            Tamanho em bytes
        """
        total = 0
        try:
            for item in path.rglob("*"):
                if item.is_file():
                    try:
                        total += item.stat().st_size
                    except OSError:
                        pass
        except Exception:
            pass
        return total

    def _safe_rmtree(self, path: Path) -> tuple[bool, List[str]]:
        """
        Remove diretório de forma segura, coletando erros.

        Returns:
            (success, list of failed file paths)
        """
        failed_files: List[str] = []

        def on_error(func, path, exc_info):
            """Callback para erros durante remoção."""
            failed_files.append(str(path))
            logger.warning(f"Falha ao remover {path}: {exc_info[1]}")

        try:
            shutil.rmtree(path, onerror=on_error)
        except Exception as e:
            logger.error(f"Erro fatal ao remover {path}: {e}")
            return False, failed_files

        # Se ainda existem arquivos que falharam, não é sucesso completo
        if failed_files:
            return False, failed_files

        return True, []


# Instância singleton
uninstaller = Uninstaller()
