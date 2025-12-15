"""
Router para download e conversao de videos do YouTube.

Endpoints:
- POST /api/youtube/info - Obtem info do video
- POST /api/youtube/download - Baixa e converte trecho
- POST /api/youtube/send - Envia para Pixoo
- GET /api/youtube/thumbnail/{video_id} - Proxy para thumbnail
"""

import uuid

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from app.config import MAX_VIDEO_DURATION
from app.services.youtube_downloader import (
    get_youtube_info,
    download_and_convert_youtube,
    YouTubeInfo,
)
from app.services.pixoo_upload import upload_gif
from app.services.pixoo_connection import get_pixoo_connection
from app.services.exceptions import (
    ConversionError,
    PixooConnectionError,
    UploadError,
    ValidationError,
    VideoTooLongError,
)
from app.services.validators import validate_video_duration
from app.middleware import youtube_limiter, check_rate_limit
from app.services.upload_manager import youtube_downloads

router = APIRouter(prefix="/api/youtube", tags=["youtube"])


class InfoRequest(BaseModel):
    """Request para obter info do video."""
    url: str


class InfoResponse(BaseModel):
    """Response com info do video."""
    id: str
    title: str
    duration: float
    thumbnail: str
    channel: str
    max_duration: float


class DownloadRequest(BaseModel):
    """Request para baixar e converter."""
    url: str
    start: float
    end: float


class DownloadResponse(BaseModel):
    """Response apos download e conversao."""
    id: str
    frames: int
    preview_url: str


class SendRequest(BaseModel):
    """Request para enviar para Pixoo."""
    id: str
    speed: int | None = None


class SendResponse(BaseModel):
    """Response apos envio."""
    success: bool
    frames_sent: int
    speed_ms: int


@router.post("/info", response_model=InfoResponse)
async def get_video_info(request: InfoRequest):
    """
    Obtem informacoes do video do YouTube sem baixar.

    Retorna titulo, duracao, thumbnail (proxy local) e canal.
    """
    try:
        info = get_youtube_info(request.url)
        # Usar proxy local para evitar CSP/CORS
        thumbnail_url = f"/api/youtube/thumbnail/{info.id}"
        return InfoResponse(
            id=info.id,
            title=info.title,
            duration=info.duration,
            thumbnail=thumbnail_url,
            channel=info.channel,
            max_duration=MAX_VIDEO_DURATION
        )
    except ConversionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao obter info: {e}")


@router.post("/download", response_model=DownloadResponse)
async def download_video(request: DownloadRequest):
    """
    Baixa trecho do video e converte para GIF 64x64.

    Limite maximo de 10 segundos por trecho.

    Rate limited: 5 requisições por minuto (download + conversão).
    """
    check_rate_limit(youtube_limiter)

    # Validar duracao
    try:
        validate_video_duration(request.start, request.end, MAX_VIDEO_DURATION)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        gif_path, frames = download_and_convert_youtube(
            request.url,
            request.start,
            request.end
        )

        # Gerar ID e armazenar
        download_id = str(uuid.uuid4())[:8]
        youtube_downloads.set(download_id, {
            "path": gif_path,
            "frames": frames
        })

        return DownloadResponse(
            id=download_id,
            frames=frames,
            preview_url=f"/api/youtube/preview/{download_id}"
        )

    except VideoTooLongError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConversionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro no download: {e}")


@router.get("/preview/{download_id}")
async def get_preview(download_id: str):
    """Retorna preview do GIF convertido."""
    download = youtube_downloads.get(download_id)
    if download is None:
        raise HTTPException(status_code=404, detail="Download nao encontrado")

    path = download["path"]

    if not path.exists():
        youtube_downloads.delete(download_id)
        raise HTTPException(status_code=404, detail="Arquivo nao encontrado")

    return FileResponse(
        path,
        media_type="image/gif",
        filename=f"youtube_{download_id}.gif"
    )


@router.post("/send", response_model=SendResponse)
async def send_to_pixoo(request: SendRequest):
    """Envia GIF convertido para o Pixoo."""
    download = youtube_downloads.get(request.id)
    if download is None:
        raise HTTPException(status_code=404, detail="Download nao encontrado")

    path = download["path"]

    if not path.exists():
        youtube_downloads.delete(request.id)
        raise HTTPException(status_code=404, detail="Arquivo nao encontrado")

    # Verificar conexao
    conn = get_pixoo_connection()
    if not conn.is_connected:
        raise HTTPException(
            status_code=400,
            detail="Nao conectado ao Pixoo"
        )

    try:
        result = upload_gif(path, speed=request.speed)
        return SendResponse(
            success=result["success"],
            frames_sent=result["frames_sent"],
            speed_ms=result["speed_ms"]
        )
    except PixooConnectionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except UploadError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{download_id}")
async def delete_download(download_id: str):
    """Remove download e limpa arquivo temporario."""
    if not youtube_downloads.delete(download_id):
        raise HTTPException(status_code=404, detail="Download nao encontrado")

    return {"success": True}


@router.get("/thumbnail/{video_id}")
async def get_thumbnail(video_id: str):
    """
    Proxy para thumbnail do YouTube.

    Evita problemas de CSP/CORS ao servir a imagem localmente.
    Tenta diferentes resoluções em ordem de preferência.
    """
    # Validar video_id (11 caracteres alfanuméricos + _ e -)
    import re
    if not re.match(r'^[a-zA-Z0-9_-]{11}$', video_id):
        raise HTTPException(status_code=400, detail="ID de video invalido")

    # URLs de thumbnail em ordem de preferência (maior para menor qualidade)
    thumbnail_urls = [
        f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg",
        f"https://i.ytimg.com/vi/{video_id}/sddefault.jpg",
        f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
        f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg",
        f"https://i.ytimg.com/vi/{video_id}/default.jpg",
    ]

    async with httpx.AsyncClient(timeout=10.0) as client:
        for url in thumbnail_urls:
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    return Response(
                        content=response.content,
                        media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=3600"}
                    )
            except httpx.RequestError:
                continue

    raise HTTPException(status_code=404, detail="Thumbnail nao encontrada")
