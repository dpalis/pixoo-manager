"""
Update checker service.

Verifica atualizações no GitHub Releases e compara versões
usando semantic versioning.
"""

import logging
import plistlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import json

from packaging.version import Version, InvalidVersion

from app.config import (
    GITHUB_OWNER,
    GITHUB_REPO,
    UPDATE_CHECK_TIMEOUT,
    is_frozen,
    get_bundle_base,
)

logger = logging.getLogger(__name__)


@dataclass
class UpdateResult:
    """Resultado da verificação de atualização."""

    update_available: bool
    current_version: str
    latest_version: Optional[str] = None
    changelog: Optional[str] = None
    release_url: Optional[str] = None
    error: Optional[str] = None


class UpdateChecker:
    """
    Verifica atualizações no GitHub Releases.

    Compara a versão atual com a última release usando semantic versioning.
    """

    GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
    MAX_CHANGELOG_LENGTH = 500

    def get_current_version(self) -> str:
        """
        Obtém a versão atual do app.

        Em bundle: lê CFBundleShortVersionString do Info.plist
        Em desenvolvimento: importa __version__ do módulo
        """
        if is_frozen():
            return self._get_version_from_plist()
        return self._get_version_from_module()

    def _get_version_from_plist(self) -> str:
        """Lê versão do Info.plist (bundle py2app)."""
        try:
            # Info.plist está em Contents/ (um nível acima de Resources/)
            plist_path = get_bundle_base().parent / "Info.plist"
            if plist_path.exists():
                with open(plist_path, "rb") as f:
                    plist = plistlib.load(f)
                return plist.get("CFBundleShortVersionString", "0.0.0")
        except Exception as e:
            logger.warning(f"Erro ao ler Info.plist: {e}")

        # Fallback para módulo
        return self._get_version_from_module()

    def _get_version_from_module(self) -> str:
        """Lê versão do módulo __version__.py."""
        try:
            from app.__version__ import __version__

            return __version__
        except ImportError:
            return "0.0.0"

    def check_for_update(self) -> UpdateResult:
        """
        Verifica se há atualização disponível.

        Returns:
            UpdateResult com informações sobre a atualização
        """
        current = self.get_current_version()

        try:
            release_data = self._fetch_latest_release()
        except Exception as e:
            return UpdateResult(
                update_available=False,
                current_version=current,
                error=str(e),
            )

        # Nenhuma release encontrada = usuário está atualizado
        if release_data is None:
            return UpdateResult(
                update_available=False,
                current_version=current,
            )

        latest = release_data.get("tag_name", "")
        # Remove 'v' prefix se existir
        if latest.startswith("v"):
            latest = latest[1:]

        try:
            is_newer = self._compare_versions(current, latest)
        except InvalidVersion:
            return UpdateResult(
                update_available=False,
                current_version=current,
                error="Versão inválida no GitHub",
            )

        changelog = release_data.get("body", "") or ""
        if len(changelog) > self.MAX_CHANGELOG_LENGTH:
            changelog = changelog[: self.MAX_CHANGELOG_LENGTH] + "..."

        return UpdateResult(
            update_available=is_newer,
            current_version=current,
            latest_version=latest,
            changelog=changelog,
            release_url=release_data.get("html_url"),
        )

    def _fetch_latest_release(self) -> dict:
        """
        Busca informações da última release no GitHub.

        Raises:
            Exception com mensagem apropriada para cada erro
        """
        request = Request(
            self.GITHUB_API_URL,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": f"PixooManager/{self.get_current_version()}",
            },
        )

        try:
            with urlopen(request, timeout=UPDATE_CHECK_TIMEOUT) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data

        except HTTPError as e:
            if e.code == 403:
                raise Exception(
                    "Limite de verificações atingido. Tente novamente em 1 hora."
                )
            elif e.code == 404:
                # Nenhuma release ainda = usuário está atualizado
                return None
            else:
                raise Exception(f"Erro ao conectar ao GitHub: {e.code}")

        except URLError as e:
            if "timed out" in str(e.reason).lower():
                raise Exception("A verificação demorou muito. Tente novamente.")
            raise Exception("Sem conexão com a internet. Verifique sua rede.")

        except json.JSONDecodeError:
            raise Exception("Resposta inválida do GitHub.")

        except Exception as e:
            raise Exception(f"Não foi possível conectar ao GitHub: {e}")

    def _compare_versions(self, current: str, latest: str) -> bool:
        """
        Compara versões usando semantic versioning.

        Returns:
            True se latest > current
        """
        current_v = Version(current)
        latest_v = Version(latest)
        return latest_v > current_v


# Instância singleton
update_checker = UpdateChecker()
