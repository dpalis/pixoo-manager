"""
Router para operações de sistema.

Endpoints:
- POST /api/system/check-update - Verifica atualizações no GitHub
- POST /api/system/uninstall - Remove dados do usuário
"""

import asyncio
from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.updater import update_checker
from app.services.uninstaller import uninstaller

router = APIRouter(prefix="/api/system", tags=["system"])


# ============================================
# Pydantic Models
# ============================================


class CheckUpdateResponse(BaseModel):
    """Response para verificação de atualização."""

    update_available: bool
    current_version: str
    latest_version: Optional[str] = None
    changelog: Optional[str] = None
    release_url: Optional[str] = None
    error: Optional[str] = None


class UninstallResponse(BaseModel):
    """Response para desinstalação."""

    success: bool
    deleted_path: str
    deleted_size_bytes: int = 0
    failed_files: List[str] = []
    error: Optional[str] = None


# ============================================
# Endpoints
# ============================================


@router.post("/check-update", response_model=CheckUpdateResponse)
async def check_update():
    """
    Verifica se há atualização disponível no GitHub.

    Compara a versão atual com a última release usando semantic versioning.
    """
    result = await asyncio.to_thread(update_checker.check_for_update)

    return CheckUpdateResponse(
        update_available=result.update_available,
        current_version=result.current_version,
        latest_version=result.latest_version,
        changelog=result.changelog,
        release_url=result.release_url,
        error=result.error,
    )


@router.post("/uninstall", response_model=UninstallResponse)
async def uninstall():
    """
    Remove dados do usuário (~/.pixoo_manager/).

    Desconecta do Pixoo antes de remover.
    Diretório inexistente é tratado como sucesso.
    """
    result = await asyncio.to_thread(uninstaller.cleanup_user_data)

    return UninstallResponse(
        success=result.success,
        deleted_path=result.deleted_path,
        deleted_size_bytes=result.deleted_size_bytes,
        failed_files=result.failed_files,
        error=result.error,
    )
