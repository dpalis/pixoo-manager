"""
Router para download e conversao de videos do YouTube.

Endpoints:
- POST /api/youtube/info - Obtem info do video
- POST /api/youtube/download - Baixa e converte trecho
- POST /api/youtube/send - Envia para Pixoo
"""

import uuid
from pathlib import Path
from typing import Dict

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
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
    VideoTooLongError,
)
from app.services.file_utils import cleanup_files
from app.middleware import youtube_limiter, check_rate_limit

router = APIRouter(prefix="/api/youtube", tags=["youtube"])

# Armazenamento temporario
_downloads: Dict[str, dict] = {}


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

    Retorna titulo, duracao, thumbnail e canal.
    """
    try:
        info = get_youtube_info(request.url)
        return InfoResponse(
            id=info.id,
            title=info.title,
            duration=info.duration,
            thumbnail=info.thumbnail,
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
    duration = request.end - request.start

    if duration > MAX_VIDEO_DURATION:
        raise HTTPException(
            status_code=400,
            detail=f"Duracao maxima e {MAX_VIDEO_DURATION}s"
        )

    if duration <= 0:
        raise HTTPException(
            status_code=400,
            detail="Tempo final deve ser maior que o inicial"
        )

    try:
        gif_path, frames = download_and_convert_youtube(
            request.url,
            request.start,
            request.end
        )

        # Gerar ID e armazenar
        download_id = str(uuid.uuid4())[:8]
        _downloads[download_id] = {
            "path": gif_path,
            "frames": frames
        }

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
    if download_id not in _downloads:
        raise HTTPException(status_code=404, detail="Download nao encontrado")

    download = _downloads[download_id]
    path = download["path"]

    if not path.exists():
        del _downloads[download_id]
        raise HTTPException(status_code=404, detail="Arquivo nao encontrado")

    return FileResponse(
        path,
        media_type="image/gif",
        filename=f"youtube_{download_id}.gif"
    )


@router.post("/send", response_model=SendResponse)
async def send_to_pixoo(request: SendRequest):
    """Envia GIF convertido para o Pixoo."""
    if request.id not in _downloads:
        raise HTTPException(status_code=404, detail="Download nao encontrado")

    download = _downloads[request.id]
    path = download["path"]

    if not path.exists():
        del _downloads[request.id]
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
    if download_id not in _downloads:
        raise HTTPException(status_code=404, detail="Download nao encontrado")

    download = _downloads[download_id]
    cleanup_files([download["path"]])
    del _downloads[download_id]

    return {"success": True}
