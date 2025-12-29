"""
Router para upload e envio de GIFs.

Endpoints:
- POST /api/gif/upload - Upload e processamento de GIF
- POST /api/gif/send - Envia GIF processado para o Pixoo
- GET /api/gif/preview/{upload_id} - Retorna preview do GIF
"""

import asyncio
import uuid
from pathlib import Path
from typing import Dict

from fastapi import APIRouter, HTTPException, UploadFile, File, Query, Response
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from app.config import ALLOWED_GIF_TYPES, ALLOWED_IMAGE_TYPES, MAX_FILE_SIZE, MAX_UPLOAD_FRAMES
from app.services.file_utils import stream_upload_to_temp, cleanup_files
from app.services.gif_converter import (
    convert_gif,
    convert_image,
    get_first_frame,
    get_frame_by_index,
    is_pixoo_ready,
    trim_gif,
    ConvertOptions,
    GifMetadata,
)
from app.services.pixoo_upload import upload_gif
from app.services.pixoo_connection import get_pixoo_connection
from app.services.exceptions import (
    ConversionError,
    PixooConnectionError,
    TooManyFramesError,
    UploadError,
)
from app.services.preview_scaler import scale_gif
from app.middleware import upload_limiter, check_rate_limit
from app.services.upload_manager import (
    gif_uploads,
    get_upload_or_404,
    validate_upload_id,
)

router = APIRouter(prefix="/api/gif", tags=["gif"])


class UploadResponse(BaseModel):
    """Response após upload de GIF."""
    id: str
    width: int
    height: int
    frames: int
    duration_ms: int
    file_size: int
    converted: bool
    needs_trim: bool
    preview_url: str


class RawUploadResponse(BaseModel):
    """Response após upload sem conversão (para cropper)."""
    id: str
    width: int
    height: int
    frames: int
    duration_ms: int
    file_size: int
    first_frame_url: str


class CropAndConvertRequest(BaseModel):
    """Request para crop e conversão de GIF."""
    id: str
    crop_x: int
    crop_y: int
    crop_width: int
    crop_height: int


class TrimRequest(BaseModel):
    """Request para recortar GIF."""
    id: str
    start_frame: int
    end_frame: int


class SendRequest(BaseModel):
    """Request para enviar GIF ao Pixoo."""
    id: str
    speed: int | None = None


class SendResponse(BaseModel):
    """Response após envio para Pixoo."""
    success: bool
    frames_sent: int
    speed_ms: int


@router.post("/upload", response_model=UploadResponse)
async def upload_gif_file(file: UploadFile = File(...)):
    """
    Upload de arquivo GIF.

    Se o GIF não estiver em 64x64, será convertido automaticamente.
    Retorna um ID para uso posterior no envio.

    Rate limited: 10 requisições por minuto.
    """
    check_rate_limit(upload_limiter)
    # Validar e salvar arquivo temporário
    try:
        temp_path = await stream_upload_to_temp(
            file,
            allowed_types=ALLOWED_GIF_TYPES + ALLOWED_IMAGE_TYPES,
            max_size=MAX_FILE_SIZE
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro no upload: {e}")

    try:
        # Verificar se já está no tamanho correto (CPU-bound, move para thread)
        is_ready = await asyncio.to_thread(is_pixoo_ready, temp_path)

        if not is_ready:
            # Determinar se é imagem animada (GIF ou WebP animado)
            from PIL import Image
            with Image.open(temp_path) as img:
                is_animated = (
                    hasattr(img, 'n_frames') and
                    img.n_frames > 1
                )

            # Converter para 64x64 usando função apropriada (CPU-bound)
            # Não limitar frames aqui - deixar o usuário escolher via trim
            options = ConvertOptions(led_optimize=True, max_frames=1000)
            if is_animated:
                output_path, metadata = await asyncio.to_thread(
                    convert_gif, temp_path, options
                )
            else:
                # Imagens estáticas (JPEG, PNG, WebP, GIF estático)
                # convert_image aplica rotação EXIF automaticamente
                output_path, metadata = await asyncio.to_thread(
                    convert_image, temp_path, options
                )

            # Limpar arquivo original
            cleanup_files([temp_path])
            temp_path = output_path
        else:
            # Carregar metadados do GIF original
            from PIL import Image
            with Image.open(temp_path) as img:
                metadata = GifMetadata(
                    width=img.size[0],
                    height=img.size[1],
                    frames=getattr(img, 'n_frames', 1),
                    duration_ms=img.info.get('duration', 100) * getattr(img, 'n_frames', 1),
                    file_size=temp_path.stat().st_size,
                    path=temp_path
                )

        # Gerar ID único
        upload_id = str(uuid.uuid4())[:8]

        # Armazenar info do upload (com TTL automático)
        gif_uploads.set(upload_id, {
            "path": temp_path,
            "metadata": metadata,
            "converted": not is_ready
        })

        return UploadResponse(
            id=upload_id,
            width=metadata.width,
            height=metadata.height,
            frames=metadata.frames,
            duration_ms=metadata.duration_ms,
            file_size=metadata.file_size,
            converted=not is_ready,
            needs_trim=metadata.frames > MAX_UPLOAD_FRAMES,
            preview_url=f"/api/gif/preview/{upload_id}"
        )

    except ConversionError as e:
        cleanup_files([temp_path])
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        cleanup_files([temp_path])
        raise HTTPException(status_code=500, detail=f"Erro ao processar GIF: {e}")


@router.head("/preview/{upload_id}")
async def head_gif_preview(upload_id: str):
    """Verifica se preview existe (para validacao de estado)."""
    get_upload_or_404(gif_uploads, upload_id)
    return Response(status_code=200)


@router.get("/preview/{upload_id}")
async def get_gif_preview(upload_id: str):
    """Retorna o GIF processado para preview (versão original 64x64)."""
    _, path = get_upload_or_404(gif_uploads, upload_id)

    return FileResponse(
        path,
        media_type="image/gif",
        filename=f"pixoo_preview_{upload_id}.gif"
    )


@router.get("/preview/{upload_id}/scaled")
async def get_gif_preview_scaled(
    upload_id: str,
    scale: int = Query(default=16, ge=1, le=64)
):
    """
    Retorna o GIF escalado para melhor visualização.

    Cada pixel do original (64x64) é ampliado para scale x scale pixels.
    Por padrão scale=16, resultando em 1024x1024 pixels.
    Usa nearest-neighbor para manter pixels nítidos.
    """
    _, path = get_upload_or_404(gif_uploads, upload_id)

    try:
        output = scale_gif(path, scale)
        return StreamingResponse(
            output,
            media_type="image/gif",
            headers={
                "Content-Disposition": f"inline; filename=pixoo_scaled_{upload_id}.gif",
                "Cache-Control": "public, max-age=3600",
                "ETag": f'"{upload_id}:{scale}"'
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao escalar imagem: {e}")


@router.post("/send", response_model=SendResponse)
async def send_gif_to_pixoo(request: SendRequest):
    """
    Envia o GIF processado para o Pixoo conectado.

    Requer conexão prévia com o Pixoo via /api/connect.
    """
    _, path = get_upload_or_404(gif_uploads, request.id)

    # Verificar conexão
    conn = get_pixoo_connection()
    if not conn.is_connected:
        raise HTTPException(
            status_code=400,
            detail="Não conectado ao Pixoo. Conecte primeiro via /api/connect"
        )

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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao enviar: {e}")


@router.get("/download/{upload_id}")
async def download_gif(upload_id: str):
    """
    Download do GIF processado (64x64).

    Permite ao usuário salvar o GIF convertido em seu computador.

    Rate limited: 10 requisições por minuto.
    """
    check_rate_limit(upload_limiter)
    _, path = get_upload_or_404(gif_uploads, upload_id)

    filename = f"pixoo_{upload_id}.gif"
    return FileResponse(
        path,
        media_type="image/gif",
        filename=filename,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.post("/trim", response_model=UploadResponse)
async def trim_gif_endpoint(request: TrimRequest):
    """
    Recorta um GIF para incluir apenas os frames especificados.

    Útil quando o GIF tem mais de 40 frames e precisa ser
    reduzido para envio ao Pixoo.

    Returns:
        Novo upload com o GIF recortado
    """
    check_rate_limit(upload_limiter)

    # Obter upload original
    upload_data, original_path = get_upload_or_404(gif_uploads, request.id)

    try:
        # Recortar GIF (CPU-bound, move para thread)
        output_path, metadata = await asyncio.to_thread(
            trim_gif,
            original_path,
            request.start_frame,
            request.end_frame
        )

        # Gerar novo ID para o GIF recortado
        new_upload_id = str(uuid.uuid4())[:8]

        # Armazenar novo upload
        gif_uploads.set(new_upload_id, {
            "path": output_path,
            "metadata": metadata,
            "converted": True,
            "trimmed_from": request.id
        })

        return UploadResponse(
            id=new_upload_id,
            width=metadata.width,
            height=metadata.height,
            frames=metadata.frames,
            duration_ms=metadata.duration_ms,
            file_size=metadata.file_size,
            converted=True,
            needs_trim=metadata.frames > MAX_UPLOAD_FRAMES,
            preview_url=f"/api/gif/preview/{new_upload_id}"
        )

    except TooManyFramesError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConversionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao recortar GIF: {e}")


@router.post("/upload-raw", response_model=RawUploadResponse)
async def upload_gif_raw(file: UploadFile = File(...)):
    """
    Upload de GIF sem conversão automática (para uso com cropper).

    O GIF é armazenado como está, permitindo que o usuário
    selecione a área de crop antes da conversão.

    Rate limited: 10 requisições por minuto.
    """
    check_rate_limit(upload_limiter)

    # Validar e salvar arquivo temporário
    try:
        temp_path = await stream_upload_to_temp(
            file,
            allowed_types=ALLOWED_GIF_TYPES,
            max_size=MAX_FILE_SIZE
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro no upload: {e}")

    try:
        from PIL import Image

        # Carregar metadados do GIF
        with Image.open(temp_path) as img:
            metadata = GifMetadata(
                width=img.size[0],
                height=img.size[1],
                frames=getattr(img, 'n_frames', 1),
                duration_ms=img.info.get('duration', 100) * getattr(img, 'n_frames', 1),
                file_size=temp_path.stat().st_size,
                path=temp_path
            )

        # Gerar ID único
        upload_id = str(uuid.uuid4())[:8]

        # Armazenar info do upload (sem conversão)
        gif_uploads.set(upload_id, {
            "path": temp_path,
            "metadata": metadata,
            "converted": False,
            "raw": True  # Marca como upload raw (para cropper)
        })

        return RawUploadResponse(
            id=upload_id,
            width=metadata.width,
            height=metadata.height,
            frames=metadata.frames,
            duration_ms=metadata.duration_ms,
            file_size=metadata.file_size,
            first_frame_url=f"/api/gif/first-frame/{upload_id}"
        )

    except Exception as e:
        cleanup_files([temp_path])
        raise HTTPException(status_code=500, detail=f"Erro ao processar GIF: {e}")


@router.get("/first-frame/{upload_id}")
async def get_first_frame_endpoint(upload_id: str):
    """
    Retorna o primeiro frame do GIF como imagem PNG.

    Usado pelo cropper para mostrar a área de seleção.
    """
    _, path = get_upload_or_404(gif_uploads, upload_id)

    try:
        import io

        # Extrair primeiro frame
        first_frame = await asyncio.to_thread(get_first_frame, path)

        # Converter para PNG
        buffer = io.BytesIO()
        first_frame.convert('RGB').save(buffer, format='PNG')
        buffer.seek(0)

        return StreamingResponse(
            buffer,
            media_type="image/png",
            headers={
                "Content-Disposition": f"inline; filename=first_frame_{upload_id}.png",
                "Cache-Control": "public, max-age=3600"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao extrair frame: {e}")


@router.get("/frame/{upload_id}/{frame_num}")
async def get_frame_endpoint(upload_id: str, frame_num: int):
    """
    Retorna um frame específico do GIF como imagem PNG.

    Usado para preview de frames durante seleção de trim.

    Args:
        upload_id: ID do upload
        frame_num: Número do frame (0-indexed)
    """
    _, path = get_upload_or_404(gif_uploads, upload_id)

    try:
        import io

        # Extrair frame específico
        frame = await asyncio.to_thread(get_frame_by_index, path, frame_num)

        # Converter para PNG
        buffer = io.BytesIO()
        frame.convert('RGB').save(buffer, format='PNG')
        buffer.seek(0)

        return StreamingResponse(
            buffer,
            media_type="image/png",
            headers={
                "Content-Disposition": f"inline; filename=frame_{upload_id}_{frame_num}.png",
                "Cache-Control": "public, max-age=3600"
            }
        )
    except ConversionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao extrair frame: {e}")


@router.post("/crop-and-convert", response_model=UploadResponse)
async def crop_and_convert_gif(request: CropAndConvertRequest):
    """
    Aplica crop em todos os frames do GIF e converte para 64x64.

    Recebe coordenadas de crop e aplica em todos os frames,
    depois redimensiona para o formato Pixoo 64x64.

    Rate limited: 10 requisições por minuto.
    """
    check_rate_limit(upload_limiter)

    # Obter upload original
    upload_data, original_path = get_upload_or_404(gif_uploads, request.id)

    # Validar coordenadas
    metadata = upload_data.get("metadata")
    if metadata:
        if request.crop_x < 0 or request.crop_y < 0:
            raise HTTPException(status_code=400, detail="Coordenadas não podem ser negativas")
        if request.crop_x + request.crop_width > metadata.width:
            raise HTTPException(status_code=400, detail="Crop excede largura da imagem")
        if request.crop_y + request.crop_height > metadata.height:
            raise HTTPException(status_code=400, detail="Crop excede altura da imagem")
        if request.crop_width <= 0 or request.crop_height <= 0:
            raise HTTPException(status_code=400, detail="Dimensões de crop devem ser positivas")

    try:
        # Converter com crop (CPU-bound, move para thread)
        options = ConvertOptions(led_optimize=True, max_frames=1000)
        output_path, new_metadata = await asyncio.to_thread(
            convert_gif,
            original_path,
            options,
            None,  # progress_callback
            request.crop_x,
            request.crop_y,
            request.crop_width,
            request.crop_height
        )

        # Gerar novo ID para o GIF convertido
        new_upload_id = str(uuid.uuid4())[:8]

        # Armazenar novo upload
        gif_uploads.set(new_upload_id, {
            "path": output_path,
            "metadata": new_metadata,
            "converted": True,
            "cropped_from": request.id
        })

        return UploadResponse(
            id=new_upload_id,
            width=new_metadata.width,
            height=new_metadata.height,
            frames=new_metadata.frames,
            duration_ms=new_metadata.duration_ms,
            file_size=new_metadata.file_size,
            converted=True,
            needs_trim=new_metadata.frames > MAX_UPLOAD_FRAMES,
            preview_url=f"/api/gif/preview/{new_upload_id}"
        )

    except ConversionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao converter GIF: {e}")


@router.delete("/{upload_id}")
async def delete_upload(upload_id: str):
    """Remove um upload da memória e limpa arquivos temporários."""
    validate_upload_id(upload_id)
    if not gif_uploads.delete(upload_id):
        raise HTTPException(status_code=404, detail="Upload não encontrado")

    return {"success": True}
