"""
Router para galeria persistente de GIFs.

Endpoints:
- GET /api/gallery/list - Lista itens paginados (inclui stats)
- GET /api/gallery/thumbnail/{id} - Retorna thumbnail JPEG
- GET /api/gallery/{id} - Retorna GIF completo
- POST /api/gallery/save - Salva GIF do upload atual
- PATCH /api/gallery/{id} - Atualiza metadados (nome, favorito)
- DELETE /api/gallery/{id} - Remove item
- POST /api/gallery/{id}/send - Envia para Pixoo
"""

import asyncio
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.services.gallery_manager import gallery, GalleryItem
from app.services.pixoo_upload import upload_gif
from app.services.pixoo_connection import get_pixoo_connection
from app.services.upload_manager import (
    gif_uploads,
    media_uploads,
    youtube_downloads,
    get_upload_or_404,
)
from app.services.exceptions import PixooConnectionError, UploadError
from app.middleware import upload_limiter, check_rate_limit

router = APIRouter(prefix="/api/gallery", tags=["gallery"])


# ============================================
# Pydantic Models
# ============================================


class GalleryItemResponse(BaseModel):
    """Response para um item da galeria."""

    id: str
    name: str
    filename: str
    source_type: str
    created_at: str
    file_size_bytes: int
    frame_count: int
    is_favorite: bool
    thumbnail_url: str
    gif_url: str

    @classmethod
    def from_item(cls, item: GalleryItem) -> "GalleryItemResponse":
        """Cria response a partir de GalleryItem."""
        return cls(
            id=item.id,
            name=item.name,
            filename=item.filename,
            source_type=item.source_type,
            created_at=item.created_at,
            file_size_bytes=item.file_size_bytes,
            frame_count=item.frame_count,
            is_favorite=item.is_favorite,
            thumbnail_url=f"/api/gallery/thumbnail/{item.id}",
            gif_url=f"/api/gallery/{item.id}",
        )


class GalleryListResponse(BaseModel):
    """Response para listagem de galeria."""

    items: List[GalleryItemResponse]
    total: int
    page: int
    per_page: int
    has_more: bool
    # Stats incluídos para evitar chamada extra
    total_count: int
    favorites_count: int


class SaveRequest(BaseModel):
    """Request para salvar GIF na galeria."""

    upload_id: str = Field(..., description="ID do upload temporário")
    name: str = Field(..., min_length=1, max_length=100, description="Nome do item")
    source_type: str = Field(
        ..., description="Tipo de origem: gif, image, video, youtube"
    )


class SaveResponse(BaseModel):
    """Response após salvar na galeria."""

    id: str
    name: str
    warning: Optional[str] = None


class UpdateRequest(BaseModel):
    """Request para atualizar item."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    is_favorite: Optional[bool] = None


class SendResponse(BaseModel):
    """Response após envio para Pixoo."""

    success: bool
    frames_sent: int
    speed_ms: int


class BulkDeleteRequest(BaseModel):
    """Request para deletar múltiplos itens."""

    item_ids: List[str] = Field(..., min_length=1, max_length=500)


class BulkDeleteResponse(BaseModel):
    """Response após deleção em massa."""

    deleted_count: int


# ============================================
# Endpoints
# ============================================


@router.get("/list", response_model=GalleryListResponse)
async def list_gallery(
    page: int = Query(default=1, ge=1, description="Número da página"),
    per_page: int = Query(default=50, ge=1, le=100, description="Itens por página"),
    favorites_only: bool = Query(default=False, description="Filtrar apenas favoritos"),
    search: Optional[str] = Query(default=None, description="Busca por nome"),
):
    """
    Lista itens da galeria com paginação.

    Ordenação: favoritos primeiro, depois alfabético por nome.
    Inclui stats para evitar chamada extra.
    """
    items, total = await asyncio.to_thread(
        gallery.list_items, page, per_page, favorites_only, search
    )
    stats = await asyncio.to_thread(gallery.get_stats)

    return GalleryListResponse(
        items=[GalleryItemResponse.from_item(item) for item in items],
        total=total,
        page=page,
        per_page=per_page,
        has_more=(page * per_page) < total,
        total_count=stats["item_count"],
        favorites_count=stats["favorites_count"],
    )


@router.get("/thumbnail/{item_id}")
async def get_thumbnail(item_id: str):
    """
    Retorna thumbnail JPEG do item.

    Inclui cache headers para otimização.
    """
    path = gallery.get_thumbnail_path(item_id)
    if path is None:
        raise HTTPException(status_code=404, detail="Item não encontrado")

    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "public, max-age=86400",  # 24 horas
            "ETag": f'"{item_id}"',
        },
    )


@router.get("/{item_id}")
async def get_gif(item_id: str):
    """
    Retorna o GIF completo.

    Inclui cache headers para otimização.
    """
    path = gallery.get_gif_path(item_id)
    if path is None:
        raise HTTPException(status_code=404, detail="Item não encontrado")

    item = gallery.get_item(item_id)
    filename = f"{item.name}.gif" if item else f"{item_id}.gif"

    return FileResponse(
        path,
        media_type="image/gif",
        filename=filename,
        headers={
            "Cache-Control": "public, max-age=86400",  # 24 horas
            "ETag": f'"{item_id}"',
        },
    )


@router.post("/save", response_model=SaveResponse)
async def save_to_gallery(request: SaveRequest):
    """
    Salva um GIF do upload temporário na galeria permanente.

    O GIF é copiado para ~/.pixoo_manager/gallery/ e um
    thumbnail é gerado automaticamente.

    Rate limited: 10 requisições por minuto.
    """
    check_rate_limit(upload_limiter)

    # Tentar encontrar o upload em qualquer manager
    upload_info = None
    path = None

    # Verificar gif_uploads
    upload_info = gif_uploads.get(request.upload_id)
    if upload_info:
        path = upload_info.get("path") or upload_info.get("converted_path")

    # Verificar media_uploads
    if not path:
        upload_info = media_uploads.get(request.upload_id)
        if upload_info:
            path = upload_info.get("converted_path") or upload_info.get("path")

    # Verificar youtube_downloads
    if not path:
        upload_info = youtube_downloads.get(request.upload_id)
        if upload_info:
            path = upload_info.get("converted_path") or upload_info.get("path")

    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="Upload não encontrado ou expirado")

    # Obter frame_count do metadata se disponível
    frame_count = None
    if upload_info and "metadata" in upload_info:
        metadata = upload_info["metadata"]
        if hasattr(metadata, "frames"):
            frame_count = metadata.frames
        elif isinstance(metadata, dict):
            frame_count = metadata.get("frames")

    try:
        item, warning = await asyncio.to_thread(
            gallery.save_gif, path, request.name, request.source_type, frame_count
        )

        return SaveResponse(id=item.id, name=item.name, warning=warning)

    except ValueError as e:
        # Limite atingido
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao salvar: {e}")


@router.patch("/{item_id}", response_model=GalleryItemResponse)
async def update_item(item_id: str, request: UpdateRequest):
    """
    Atualiza metadados de um item (nome e/ou favorito).
    """
    if request.name is None and request.is_favorite is None:
        raise HTTPException(status_code=400, detail="Nenhum campo para atualizar")

    item = await asyncio.to_thread(
        gallery.update_item, item_id, request.name, request.is_favorite
    )

    if item is None:
        raise HTTPException(status_code=404, detail="Item não encontrado")

    return GalleryItemResponse.from_item(item)


@router.delete("/{item_id}")
async def delete_item(item_id: str):
    """
    Remove item da galeria.

    Remove o GIF, thumbnail e metadados associados.
    """
    success = await asyncio.to_thread(gallery.delete_item, item_id)

    if not success:
        raise HTTPException(status_code=404, detail="Item não encontrado")

    return {"success": True}


@router.post("/delete-batch", response_model=BulkDeleteResponse)
async def delete_batch(request: BulkDeleteRequest):
    """
    Remove múltiplos itens da galeria.

    Aceita até 500 IDs por requisição.
    """
    count = await asyncio.to_thread(gallery.delete_items, request.item_ids)
    return BulkDeleteResponse(deleted_count=count)


@router.delete("/all", response_model=BulkDeleteResponse)
async def delete_all():
    """
    Remove TODOS os itens da galeria.

    ⚠️ AÇÃO IRREVERSÍVEL - Use com cuidado!
    """
    count = await asyncio.to_thread(gallery.delete_all)
    return BulkDeleteResponse(deleted_count=count)


@router.post("/{item_id}/send", response_model=SendResponse)
async def send_to_pixoo(item_id: str, speed: Optional[int] = None):
    """
    Envia GIF da galeria para o Pixoo conectado.

    Requer conexão prévia com o Pixoo.

    Args:
        item_id: ID do item na galeria
        speed: Velocidade em ms entre frames (opcional)
    """
    path = gallery.get_gif_path(item_id)
    if path is None:
        raise HTTPException(status_code=404, detail="Item não encontrado")

    # Verificar conexão
    conn = get_pixoo_connection()
    if not conn.is_connected:
        raise HTTPException(
            status_code=400,
            detail="Não conectado ao Pixoo. Conecte primeiro.",
        )

    try:
        result = await asyncio.to_thread(upload_gif, path, speed)

        return SendResponse(
            success=result["success"],
            frames_sent=result["frames_sent"],
            speed_ms=result["speed_ms"],
        )

    except PixooConnectionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except UploadError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao enviar: {e}")
