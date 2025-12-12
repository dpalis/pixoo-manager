"""
Router para upload e conversao de fotos/videos.

Endpoints:
- POST /api/media/upload - Upload de foto ou video
- GET /api/media/info/{upload_id} - Info do arquivo
- POST /api/media/convert - Converte video para GIF
- POST /api/media/send - Envia para Pixoo
"""

import asyncio
import uuid

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from app.config import (
    ALLOWED_IMAGE_TYPES,
    ALLOWED_VIDEO_TYPES,
    MAX_FILE_SIZE,
    MAX_VIDEO_DURATION,
)
from app.services.file_utils import stream_upload_to_temp, cleanup_files
from app.services.gif_converter import convert_image, GifMetadata
from app.services.video_converter import (
    get_video_info,
    convert_video_to_gif,
    VideoMetadata,
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
from app.middleware import convert_limiter, upload_limiter, check_rate_limit
from app.services.upload_manager import media_uploads

router = APIRouter(prefix="/api/media", tags=["media"])


class MediaUploadResponse(BaseModel):
    """Response apos upload de midia."""
    id: str
    type: str  # "image" ou "video"
    width: int
    height: int
    duration: float | None = None  # Apenas para video
    fps: float | None = None  # Apenas para video
    preview_url: str | None = None  # Preview (para imagem ja convertida)


class ConvertRequest(BaseModel):
    """Request para converter video."""
    id: str
    start: float
    end: float


class ConvertResponse(BaseModel):
    """Response apos conversao de video."""
    id: str
    frames: int
    preview_url: str


class SendRequest(BaseModel):
    """Request para enviar para Pixoo."""
    id: str
    speed: int | None = None


class SendResponse(BaseModel):
    """Response apos envio para Pixoo."""
    success: bool
    frames_sent: int
    speed_ms: int


@router.post("/upload", response_model=MediaUploadResponse)
async def upload_media(file: UploadFile = File(...)):
    """
    Upload de foto ou video.

    Imagens sao convertidas automaticamente para 64x64.
    Videos retornam metadados para selecao de trecho.

    Rate limited: 10 requisições por minuto.
    """
    check_rate_limit(upload_limiter)
    # Determinar tipo do arquivo
    content_type = file.content_type or ""
    is_image = content_type in ALLOWED_IMAGE_TYPES
    is_video = content_type in ALLOWED_VIDEO_TYPES

    if not is_image and not is_video:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de arquivo nao suportado: {content_type}"
        )

    # Salvar arquivo temporario
    allowed_types = ALLOWED_IMAGE_TYPES if is_image else ALLOWED_VIDEO_TYPES
    try:
        temp_path = await stream_upload_to_temp(
            file,
            allowed_types=allowed_types,
            max_size=MAX_FILE_SIZE
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro no upload: {e}")

    upload_id = str(uuid.uuid4())[:8]

    try:
        if is_image:
            # Converter imagem para 64x64
            output_path, metadata = convert_image(temp_path)
            cleanup_files([temp_path])

            media_uploads.set(upload_id, {
                "type": "image",
                "path": output_path,
                "metadata": metadata,
                "converted": True
            })

            return MediaUploadResponse(
                id=upload_id,
                type="image",
                width=metadata.width,
                height=metadata.height,
                preview_url=f"/api/media/preview/{upload_id}"
            )

        else:
            # Obter info do video
            video_info = get_video_info(temp_path)

            media_uploads.set(upload_id, {
                "type": "video",
                "path": temp_path,
                "metadata": video_info,
                "converted": False
            })

            return MediaUploadResponse(
                id=upload_id,
                type="video",
                width=video_info.width,
                height=video_info.height,
                duration=video_info.duration,
                fps=video_info.fps
            )

    except ConversionError as e:
        cleanup_files([temp_path])
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        cleanup_files([temp_path])
        raise HTTPException(status_code=500, detail=f"Erro ao processar: {e}")


@router.get("/info/{upload_id}")
async def get_media_info(upload_id: str):
    """Retorna informacoes do arquivo enviado."""
    upload = media_uploads.get(upload_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload nao encontrado")

    metadata = upload["metadata"]

    if upload["type"] == "video":
        return {
            "type": "video",
            "duration": metadata.duration,
            "width": metadata.width,
            "height": metadata.height,
            "fps": metadata.fps,
            "max_duration": MAX_VIDEO_DURATION
        }
    else:
        return {
            "type": "image",
            "width": metadata.width,
            "height": metadata.height,
            "frames": metadata.frames
        }


@router.get("/preview/{upload_id}")
async def get_media_preview(upload_id: str):
    """Retorna preview do arquivo convertido."""
    upload = media_uploads.get(upload_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload nao encontrado")

    path = upload.get("converted_path") or upload.get("path")

    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="Arquivo nao encontrado")

    return FileResponse(
        path,
        media_type="image/gif",
        filename=f"preview_{upload_id}.gif"
    )


@router.post("/convert")
async def convert_video(request: ConvertRequest):
    """
    Converte segmento de video para GIF 64x64.

    Retorna SSE com progresso da conversao.

    Rate limited: 5 requisições por minuto (CPU intensivo).
    """
    check_rate_limit(convert_limiter)
    upload = media_uploads.get(request.id)
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload nao encontrado")

    if upload["type"] != "video":
        raise HTTPException(status_code=400, detail="Arquivo nao e um video")

    path = upload["path"]
    if not path.exists():
        media_uploads.delete(request.id)
        raise HTTPException(status_code=404, detail="Arquivo nao encontrado")

    # Validar duracao
    try:
        validate_video_duration(request.start, request.end, MAX_VIDEO_DURATION)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    async def generate_progress():
        """Gera eventos SSE durante conversao."""
        progress_state = {"phase": "starting", "progress": 0}
        conversion_done = asyncio.Event()
        result = {"path": None, "frames": 0, "error": None}

        def progress_callback(phase: str, progress: float):
            progress_state["phase"] = phase
            progress_state["progress"] = progress

        def run_conversion():
            try:
                output_path, frames = convert_video_to_gif(
                    path,
                    request.start,
                    request.end,
                    progress_callback=progress_callback
                )
                result["path"] = output_path
                result["frames"] = frames
            except Exception as e:
                result["error"] = str(e)
            finally:
                conversion_done.set()

        # Iniciar conversao em thread separada
        import threading
        thread = threading.Thread(target=run_conversion)
        thread.start()

        # Enviar atualizacoes de progresso
        import json
        last_progress = -1
        while not conversion_done.is_set():
            await asyncio.sleep(0.2)
            current = int(progress_state["progress"] * 100)
            if current != last_progress:
                data = json.dumps({"phase": progress_state["phase"], "progress": current})
                yield f"data: {data}\n\n"
                last_progress = current

        thread.join()

        if result["error"]:
            data = json.dumps({"error": result["error"]})
            yield f"data: {data}\n\n"
        else:
            # Atualizar upload com resultado
            media_uploads.update(
                request.id,
                converted_path=result["path"],
                converted=True,
                frames=result["frames"]
            )

            data = json.dumps({
                "done": True,
                "frames": result["frames"],
                "preview_url": f"/api/media/preview/{request.id}"
            })
            yield f"data: {data}\n\n"

    return StreamingResponse(
        generate_progress(),
        media_type="text/event-stream"
    )


@router.post("/convert-sync", response_model=ConvertResponse)
async def convert_video_sync(request: ConvertRequest):
    """
    Converte segmento de video para GIF 64x64 (sincrono).

    Alternativa ao endpoint SSE para clientes simples.

    Rate limited: 5 requisições por minuto (CPU intensivo).
    """
    check_rate_limit(convert_limiter)
    upload = media_uploads.get(request.id)
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload nao encontrado")

    if upload["type"] != "video":
        raise HTTPException(status_code=400, detail="Arquivo nao e um video")

    path = upload["path"]
    if not path.exists():
        media_uploads.delete(request.id)
        raise HTTPException(status_code=404, detail="Arquivo nao encontrado")

    try:
        output_path, frames = convert_video_to_gif(
            path,
            request.start,
            request.end
        )

        media_uploads.update(
            request.id,
            converted_path=output_path,
            converted=True,
            frames=frames
        )

        return ConvertResponse(
            id=request.id,
            frames=frames,
            preview_url=f"/api/media/preview/{request.id}"
        )

    except VideoTooLongError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConversionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na conversao: {e}")


@router.post("/send", response_model=SendResponse)
async def send_to_pixoo(request: SendRequest):
    """Envia arquivo convertido para o Pixoo."""
    upload = media_uploads.get(request.id)
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload nao encontrado")

    if not upload.get("converted"):
        raise HTTPException(status_code=400, detail="Arquivo nao foi convertido")

    # Verificar conexao
    conn = get_pixoo_connection()
    if not conn.is_connected:
        raise HTTPException(
            status_code=400,
            detail="Nao conectado ao Pixoo"
        )

    # Obter caminho do arquivo convertido
    path = upload.get("converted_path") or upload.get("path")
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="Arquivo nao encontrado")

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


@router.delete("/{upload_id}")
async def delete_upload(upload_id: str):
    """Remove upload e limpa arquivos temporarios."""
    if not media_uploads.delete(upload_id):
        raise HTTPException(status_code=404, detail="Upload nao encontrado")

    return {"success": True}
