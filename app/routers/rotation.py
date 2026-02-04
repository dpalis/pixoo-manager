"""
Router para rotação automática de imagens da galeria.

Endpoints:
- POST /api/rotation/start - Inicia rotação com IDs e intervalo
- POST /api/rotation/stop - Para rotação ativa
- POST /api/rotation/resume - Retoma última configuração
- POST /api/rotation/add/{item_id} - Adiciona item à rotação
- POST /api/rotation/remove/{item_id} - Remove item da rotação
- GET /api/rotation/status - Retorna status atual
- DELETE /api/rotation/config - Deleta configuração salva
"""

from typing import Annotated, List, Literal

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field

from app.services.rotation_manager import (
    ROTATION_INTERVALS,
    get_rotation_manager,
)
from app.services.gallery_manager import gallery

router = APIRouter(prefix="/api/rotation", tags=["rotation"])

# ID de item da galeria (8 caracteres hex)
GalleryItemId = Annotated[
    str,
    Path(
        pattern=r"^[a-f0-9]{8}$",
        min_length=8,
        max_length=8,
        description="ID do item da galeria (8 caracteres hexadecimais)",
    ),
]


# ============================================
# Pydantic Models
# ============================================


class StartRotationRequest(BaseModel):
    """Request para iniciar rotação."""

    selected_ids: List[str] = Field(..., min_length=1)
    interval_seconds: int = Field(..., description="Intervalo em segundos")


class RotationStatusResponse(BaseModel):
    """Response com status da rotação."""

    is_active: bool
    is_paused: bool
    selected_ids: List[str]
    selected_count: int
    interval_seconds: int
    interval_label: str
    current_index: int
    has_saved_config: bool


class RotationIntervalsResponse(BaseModel):
    """Response com intervalos disponíveis."""

    intervals: dict


class SuccessResponse(BaseModel):
    """Response genérico de sucesso."""

    success: bool
    message: str


# ============================================
# Endpoints
# ============================================


@router.post("/start", response_model=SuccessResponse)
async def start_rotation(request: StartRotationRequest):
    """
    Inicia rotação automática de imagens.

    - Valida que os IDs existem na galeria
    - Valida intervalo é um dos permitidos
    - Para rotação anterior se existir
    - Inicia nova rotação
    """
    # Validar intervalo
    if request.interval_seconds not in ROTATION_INTERVALS:
        raise HTTPException(
            status_code=400,
            detail=f"Intervalo inválido. Permitidos: {list(ROTATION_INTERVALS.keys())}",
        )

    # Validar IDs existem
    invalid_ids = []
    for item_id in request.selected_ids:
        if gallery.get_item(item_id) is None:
            invalid_ids.append(item_id)

    if invalid_ids:
        raise HTTPException(
            status_code=400,
            detail=f"IDs não encontrados na galeria: {invalid_ids}",
        )

    manager = get_rotation_manager()
    success = manager.start(request.selected_ids, request.interval_seconds)

    if not success:
        raise HTTPException(status_code=500, detail="Falha ao iniciar rotação")

    return SuccessResponse(
        success=True,
        message=f"Rotação iniciada com {len(request.selected_ids)} imagens",
    )


@router.post("/stop", response_model=SuccessResponse)
async def stop_rotation():
    """
    Para a rotação ativa.

    Salva configuração para possível retomada posterior.
    """
    manager = get_rotation_manager()
    success = manager.stop()

    if not success:
        raise HTTPException(status_code=400, detail="Nenhuma rotação ativa para parar")

    return SuccessResponse(success=True, message="Rotação parada")


@router.post("/resume", response_model=SuccessResponse)
async def resume_rotation():
    """
    Retoma última configuração salva.

    Valida que a configuração existe e os IDs ainda são válidos.
    """
    manager = get_rotation_manager()
    success = manager.resume()

    if not success:
        raise HTTPException(
            status_code=400, detail="Nenhuma configuração salva ou IDs inválidos"
        )

    status = manager.get_status()
    return SuccessResponse(
        success=True,
        message=f"Rotação retomada com {status.selected_count} imagens",
    )


@router.post("/add/{item_id}", response_model=SuccessResponse)
async def add_to_rotation(item_id: GalleryItemId):
    """
    Adiciona item à rotação ativa.

    O item é adicionado ao final da fila atual.
    """
    # Validar item existe
    if gallery.get_item(item_id) is None:
        raise HTTPException(status_code=404, detail="Item não encontrado na galeria")

    manager = get_rotation_manager()

    # Verificar se rotação está ativa
    status = manager.get_status()
    if not status.is_active:
        raise HTTPException(status_code=400, detail="Nenhuma rotação ativa")

    success = manager.add_item(item_id)
    if not success:
        raise HTTPException(status_code=400, detail="Falha ao adicionar item")

    return SuccessResponse(success=True, message="Item adicionado à rotação")


@router.post("/remove/{item_id}", response_model=SuccessResponse)
async def remove_from_rotation(item_id: GalleryItemId):
    """
    Remove item da rotação ativa.

    Se for o último item, a rotação é parada automaticamente.
    """
    manager = get_rotation_manager()

    # Verificar se rotação está ativa
    status = manager.get_status()
    if not status.is_active:
        raise HTTPException(status_code=400, detail="Nenhuma rotação ativa")

    success = manager.remove_item(item_id)
    if not success:
        raise HTTPException(status_code=400, detail="Item não está na rotação")

    # Verificar se rotação foi parada por ficar sem itens
    new_status = manager.get_status()
    if not new_status.is_active:
        return SuccessResponse(
            success=True, message="Item removido. Rotação parada (sem itens restantes)"
        )

    return SuccessResponse(success=True, message="Item removido da rotação")


@router.get("/status", response_model=RotationStatusResponse)
async def get_rotation_status():
    """
    Retorna status atual da rotação.

    Inclui informação sobre configuração salva para banner de retomada.
    """
    manager = get_rotation_manager()
    status = manager.get_status()

    return RotationStatusResponse(
        is_active=status.is_active,
        is_paused=status.is_paused,
        selected_ids=status.selected_ids,
        selected_count=status.selected_count,
        interval_seconds=status.interval_seconds,
        interval_label=status.interval_label,
        current_index=status.current_index,
        has_saved_config=status.has_saved_config,
    )


@router.delete("/config", response_model=SuccessResponse)
async def delete_saved_config():
    """
    Deleta configuração salva (botão X no banner retomar).

    Usado quando usuário não quer mais ver o banner de retomada.
    """
    manager = get_rotation_manager()

    # Não permitir deletar se rotação está ativa
    status = manager.get_status()
    if status.is_active:
        raise HTTPException(
            status_code=400, detail="Não é possível deletar config com rotação ativa"
        )

    success = manager.delete_saved_config()
    if not success:
        raise HTTPException(status_code=500, detail="Falha ao deletar configuração")

    return SuccessResponse(success=True, message="Configuração deletada")


@router.get("/intervals", response_model=RotationIntervalsResponse)
async def get_intervals():
    """
    Retorna intervalos disponíveis para rotação.

    Útil para popular dropdown no frontend.
    """
    return RotationIntervalsResponse(intervals=ROTATION_INTERVALS)
