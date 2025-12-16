"""
Router para upload e envio de GIFs.

Endpoints:
- POST /api/gif/upload - Upload e processamento de GIF
- POST /api/gif/send - Envia GIF processado para o Pixoo
- GET /api/gif/preview/{upload_id} - Retorna preview do GIF
"""

import uuid
from pathlib import Path
from typing import Dict

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from app.config import ALLOWED_GIF_TYPES, ALLOWED_IMAGE_TYPES, MAX_FILE_SIZE
from app.services.file_utils import stream_upload_to_temp, cleanup_files
from app.services.gif_converter import (
    convert_gif,
    convert_image,
    is_pixoo_ready,
    ConvertOptions,
    GifMetadata,
)
from app.services.pixoo_upload import upload_gif
from app.services.pixoo_connection import get_pixoo_connection
from app.services.exceptions import (
    ConversionError,
    PixooConnectionError,
    UploadError,
)
from app.services.preview_scaler import scale_gif
from app.middleware import upload_limiter, check_rate_limit
from app.services.upload_manager import gif_uploads

router = APIRouter(prefix="/api/gif", tags=["gif"])


class UploadResponse(BaseModel):
    """Response após upload de GIF."""
    id: str
    width: int
    height: int
    frames: int
    file_size: int
    converted: bool
    preview_url: str


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
        # Verificar se já está no tamanho correto
        needs_conversion = not is_pixoo_ready(temp_path)

        if needs_conversion:
            # Determinar se é GIF animado ou imagem estática
            from PIL import Image
            with Image.open(temp_path) as img:
                is_animated_gif = (
                    temp_path.suffix.lower() == '.gif' and
                    hasattr(img, 'n_frames') and
                    img.n_frames > 1
                )

            # Converter para 64x64 usando função apropriada
            options = ConvertOptions(led_optimize=True)
            if is_animated_gif:
                output_path, metadata = convert_gif(temp_path, options)
            else:
                # Imagens estáticas (JPEG, PNG, WebP, GIF estático)
                # convert_image aplica rotação EXIF automaticamente
                output_path, metadata = convert_image(temp_path, options)

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
            "converted": needs_conversion
        })

        return UploadResponse(
            id=upload_id,
            width=metadata.width,
            height=metadata.height,
            frames=metadata.frames,
            file_size=metadata.file_size,
            converted=needs_conversion,
            preview_url=f"/api/gif/preview/{upload_id}"
        )

    except ConversionError as e:
        cleanup_files([temp_path])
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        cleanup_files([temp_path])
        raise HTTPException(status_code=500, detail=f"Erro ao processar GIF: {e}")


@router.get("/preview/{upload_id}")
async def get_gif_preview(upload_id: str):
    """
    Retorna o GIF processado para preview (versão original 64x64).
    """
    upload_info = gif_uploads.get(upload_id)
    if upload_info is None:
        raise HTTPException(status_code=404, detail="Upload não encontrado")

    path = upload_info["path"]

    if not path.exists():
        gif_uploads.delete(upload_id)
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")

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
    upload_info = gif_uploads.get(upload_id)
    if upload_info is None:
        raise HTTPException(status_code=404, detail="Upload não encontrado")

    path = upload_info["path"]

    if not path.exists():
        gif_uploads.delete(upload_id)
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")

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
    upload_info = gif_uploads.get(request.id)
    if upload_info is None:
        raise HTTPException(status_code=404, detail="Upload não encontrado")

    # Verificar conexão
    conn = get_pixoo_connection()
    if not conn.is_connected:
        raise HTTPException(
            status_code=400,
            detail="Não conectado ao Pixoo. Conecte primeiro via /api/connect"
        )

    path = upload_info["path"]

    if not path.exists():
        gif_uploads.delete(request.id)
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")

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
    upload_info = gif_uploads.get(upload_id)
    if upload_info is None:
        raise HTTPException(status_code=404, detail="Upload não encontrado")

    path = upload_info["path"]

    if not path.exists():
        gif_uploads.delete(upload_id)
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")

    filename = f"pixoo_{upload_id}.gif"
    return FileResponse(
        path,
        media_type="image/gif",
        filename=filename,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.delete("/{upload_id}")
async def delete_upload(upload_id: str):
    """Remove um upload da memória e limpa arquivos temporários."""
    if not gif_uploads.delete(upload_id):
        raise HTTPException(status_code=404, detail="Upload não encontrado")

    return {"success": True}
