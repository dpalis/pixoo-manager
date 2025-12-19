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

from fastapi import APIRouter, HTTPException, UploadFile, File, Query, Response
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
from app.services.preview_scaler import scale_gif
from app.services.validators import validate_video_duration
from app.middleware import convert_limiter, upload_limiter, check_rate_limit
from app.services.upload_manager import (
    media_uploads,
    get_upload_or_404,
    validate_upload_id,
)

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


class CropRequest(BaseModel):
    """Request para crop de imagem via API."""
    x: int
    y: int
    width: int
    height: int


class CropResponse(BaseModel):
    """Response apos crop de imagem."""
    id: str
    width: int
    height: int
    preview_url: str


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
            # Verificar se é imagem animada (GIF ou WebP animado)
            from PIL import Image
            from app.services.gif_converter import convert_gif, ConvertOptions

            with Image.open(temp_path) as img:
                is_animated = hasattr(img, 'n_frames') and img.n_frames > 1

            # Usar função apropriada para imagem estática ou animada (CPU-bound)
            options = ConvertOptions(led_optimize=True)
            if is_animated:
                output_path, metadata = await asyncio.to_thread(
                    convert_gif, temp_path, options
                )
            else:
                output_path, metadata = await asyncio.to_thread(
                    convert_image, temp_path, options
                )

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
            # Obter info do video (CPU-bound)
            video_info = await asyncio.to_thread(get_video_info, temp_path)

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
    validate_upload_id(upload_id)
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


@router.head("/preview/{upload_id}")
async def head_media_preview(upload_id: str):
    """Verifica se preview existe (para validacao de estado)."""
    validate_upload_id(upload_id)
    upload = media_uploads.get(upload_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload nao encontrado")

    path = upload.get("converted_path") or upload.get("path")

    if not path or not path.exists():
        media_uploads.delete(upload_id)
        raise HTTPException(status_code=404, detail="Arquivo nao encontrado")

    return Response(status_code=200)


@router.get("/preview/{upload_id}")
async def get_media_preview(upload_id: str):
    """Retorna preview do arquivo convertido."""
    validate_upload_id(upload_id)
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


@router.get("/preview/{upload_id}/scaled")
async def get_media_preview_scaled(
    upload_id: str,
    scale: int = Query(default=16, ge=1, le=64)
):
    """
    Retorna o GIF escalado para melhor visualização.

    Cada pixel do original (64x64) é ampliado para scale x scale pixels.
    Por padrão scale=16, resultando em 1024x1024 pixels.
    Usa nearest-neighbor para manter pixels nítidos.
    """
    validate_upload_id(upload_id)
    upload = media_uploads.get(upload_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload nao encontrado")

    path = upload.get("converted_path") or upload.get("path")

    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="Arquivo nao encontrado")

    try:
        output = scale_gif(path, scale)
        return StreamingResponse(
            output,
            media_type="image/gif",
            headers={
                "Content-Disposition": f"inline; filename=media_scaled_{upload_id}.gif",
                "Cache-Control": "public, max-age=3600",
                "ETag": f'"{upload_id}:{scale}"'
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao escalar imagem: {e}")


@router.post("/convert")
async def convert_video(request: ConvertRequest):
    """
    Converte segmento de video para GIF 64x64.

    Retorna SSE com progresso da conversao.

    Rate limited: 5 requisições por minuto (CPU intensivo).
    """
    check_rate_limit(convert_limiter)
    validate_upload_id(request.id)
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
    validate_upload_id(request.id)
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
        # Operação bloqueante (conversão CPU-intensiva) - move para thread
        output_path, frames = await asyncio.to_thread(
            convert_video_to_gif,
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
    validate_upload_id(request.id)
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
        result = await asyncio.to_thread(upload_gif, path, request.speed)
        return SendResponse(
            success=result["success"],
            frames_sent=result["frames_sent"],
            speed_ms=result["speed_ms"]
        )
    except PixooConnectionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except UploadError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/{upload_id}")
async def download_media(upload_id: str):
    """
    Download do GIF processado (64x64).

    Permite ao usuário salvar o GIF convertido em seu computador.

    Rate limited: 10 requisições por minuto.
    """
    check_rate_limit(upload_limiter)
    validate_upload_id(upload_id)
    upload = media_uploads.get(upload_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload nao encontrado")

    if not upload.get("converted"):
        raise HTTPException(status_code=400, detail="Arquivo nao foi convertido")

    path = upload.get("converted_path") or upload.get("path")

    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="Arquivo nao encontrado")

    filename = f"pixoo_{upload_id}.gif"
    return FileResponse(
        path,
        media_type="image/gif",
        filename=filename,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.delete("/{upload_id}")
async def delete_upload(upload_id: str):
    """Remove upload e limpa arquivos temporarios."""
    validate_upload_id(upload_id)
    if not media_uploads.delete(upload_id):
        raise HTTPException(status_code=404, detail="Upload nao encontrado")

    return {"success": True}


@router.post("/crop", response_model=CropResponse)
async def crop_image(
    file: UploadFile = File(...),
    x: int = 0,
    y: int = 0,
    width: int = 0,
    height: int = 0
):
    """
    Recorta imagem na regiao especificada e converte para 64x64.

    Endpoint agent-native para recorte de imagens sem necessidade de UI.
    Aceita coordenadas de recorte e redimensiona para Pixoo 64.

    Args:
        file: Arquivo de imagem (PNG, JPEG, GIF)
        x: Coordenada X do canto superior esquerdo
        y: Coordenada Y do canto superior esquerdo
        width: Largura da regiao de recorte
        height: Altura da regiao de recorte

    Returns:
        ID do upload e URL do preview

    Rate limited: 10 requisições por minuto.
    """
    check_rate_limit(upload_limiter)

    content_type = file.content_type or ""
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de arquivo nao suportado: {content_type}"
        )

    # Salvar arquivo temporario
    try:
        temp_path = await stream_upload_to_temp(
            file,
            allowed_types=ALLOWED_IMAGE_TYPES,
            max_size=MAX_FILE_SIZE
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro no upload: {e}")

    upload_id = str(uuid.uuid4())[:8]

    try:
        from PIL import Image
        from app.config import PIXOO_SIZE
        from app.services.file_utils import create_temp_output

        with Image.open(temp_path) as img:
            img = img.convert('RGBA')
            img_width, img_height = img.size

            # Se width/height nao especificados, usar imagem inteira
            if width <= 0 or height <= 0:
                width = img_width
                height = img_height

            # Validar coordenadas
            if x < 0 or y < 0:
                raise HTTPException(status_code=400, detail="Coordenadas nao podem ser negativas")
            if x + width > img_width or y + height > img_height:
                raise HTTPException(
                    status_code=400,
                    detail=f"Regiao de recorte excede dimensoes da imagem ({img_width}x{img_height})"
                )

            # Recortar
            cropped = img.crop((x, y, x + width, y + height))

            # Redimensionar para 64x64 com alta qualidade
            resized = cropped.resize(
                (PIXOO_SIZE, PIXOO_SIZE),
                Image.Resampling.LANCZOS
            )

            # Converter para RGB (Pixoo nao suporta alpha)
            if resized.mode == 'RGBA':
                background = Image.new('RGB', resized.size, (0, 0, 0))
                background.paste(resized, mask=resized.split()[3])
                resized = background

            # Salvar como GIF
            output_path = create_temp_output("cropped", ".gif")
            resized.save(output_path, format='GIF')

        cleanup_files([temp_path])

        # Armazenar resultado
        metadata = GifMetadata(
            width=PIXOO_SIZE,
            height=PIXOO_SIZE,
            frames=1,
            duration_ms=0,
            file_size=output_path.stat().st_size,
            path=output_path
        )

        media_uploads.set(upload_id, {
            "type": "image",
            "path": output_path,
            "metadata": metadata,
            "converted": True
        })

        return CropResponse(
            id=upload_id,
            width=PIXOO_SIZE,
            height=PIXOO_SIZE,
            preview_url=f"/api/media/preview/{upload_id}"
        )

    except HTTPException:
        cleanup_files([temp_path])
        raise
    except ConversionError as e:
        cleanup_files([temp_path])
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        cleanup_files([temp_path])
        raise HTTPException(status_code=500, detail=f"Erro ao processar: {e}")
