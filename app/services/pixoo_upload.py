"""
Serviço de upload de GIFs para o Pixoo 64.

Implementa a conversão de frames para o formato esperado pela API HTTP do Pixoo
e o envio frame-by-frame.
"""

import base64
from pathlib import Path
from typing import Callable, Optional

from PIL import Image

from app.config import MAX_UPLOAD_FRAMES, PIXOO_SIZE
from app.services.exceptions import PixooConnectionError, TooManyFramesError, UploadError
from app.services.gif_converter import load_gif_frames
from app.services.pixoo_connection import get_pixoo_connection


def frame_to_base64(frame: Image.Image) -> str:
    """
    Converte um frame PIL para base64 no formato esperado pelo Pixoo.

    O Pixoo espera dados RGB em formato flat: [R, G, B, R, G, B, ...]
    com exatamente 64*64*3 = 12288 bytes, codificados em base64.

    Args:
        frame: Imagem PIL (será convertida para RGB e redimensionada se necessário)

    Returns:
        String base64 dos dados RGB
    """
    # Garantir que está em RGB e no tamanho correto
    if frame.mode != 'RGB':
        frame = frame.convert('RGB')

    if frame.size != (PIXOO_SIZE, PIXOO_SIZE):
        frame = frame.resize((PIXOO_SIZE, PIXOO_SIZE), Image.Resampling.NEAREST)

    # Extrair pixels como lista flat [R, G, B, R, G, B, ...]
    pixels = list(frame.getdata())
    pixel_bytes = bytearray()
    for r, g, b in pixels:
        pixel_bytes.extend([r, g, b])

    return base64.b64encode(pixel_bytes).decode('utf-8')


def reset_gif_buffer() -> None:
    """
    Reseta o buffer de GIF no Pixoo.

    Deve ser chamado antes de enviar um novo GIF.
    """
    conn = get_pixoo_connection()
    conn.send_command({"Command": "Draw/ResetHttpGifId"})


def send_gif_frame(
    pic_num: int,
    pic_offset: int,
    speed: int,
    data: str
) -> dict:
    """
    Envia um único frame do GIF para o Pixoo.

    Args:
        pic_num: Número total de frames no GIF
        pic_offset: Índice deste frame (0-based)
        speed: Velocidade em ms entre frames
        data: Dados do frame em base64

    Returns:
        Resposta do Pixoo
    """
    conn = get_pixoo_connection()

    payload = {
        "Command": "Draw/SendHttpGif",
        "PicNum": pic_num,
        "PicOffset": pic_offset,
        "PicWidth": PIXOO_SIZE,
        "PicSpeed": speed,
        "PicData": data
    }

    return conn.send_command(payload)


def upload_gif(
    path: Path,
    speed: Optional[int] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> dict:
    """
    Envia um GIF completo para o Pixoo.

    Args:
        path: Caminho do arquivo GIF
        speed: Velocidade em ms entre frames (None = usa duração original)
        progress_callback: Callback para progresso (recebe frame_atual, total_frames)

    Returns:
        Dict com resultado do upload

    Raises:
        PixooConnectionError: Se não estiver conectado
        TooManyFramesError: Se GIF tiver mais frames que o limite
        UploadError: Se upload falhar
    """
    conn = get_pixoo_connection()

    if not conn.is_connected:
        raise PixooConnectionError("Não conectado ao Pixoo")

    # Carregar frames do GIF
    frames, durations = load_gif_frames(path)
    total_frames = len(frames)

    # Verificar limite de frames
    if total_frames > MAX_UPLOAD_FRAMES:
        raise TooManyFramesError(
            f"GIF tem {total_frames} frames, máximo permitido é {MAX_UPLOAD_FRAMES}"
        )

    # Calcular velocidade se não especificada
    if speed is None:
        avg_duration = sum(durations) // len(durations)
        speed = max(avg_duration, 50)  # Mínimo 50ms

    # Resetar buffer antes de enviar
    try:
        reset_gif_buffer()
    except Exception as e:
        raise UploadError(f"Falha ao resetar buffer: {e}")

    # Enviar cada frame
    for offset, frame in enumerate(frames):
        if progress_callback:
            progress_callback(offset + 1, total_frames)

        try:
            data = frame_to_base64(frame)
            result = send_gif_frame(
                pic_num=total_frames,
                pic_offset=offset,
                speed=speed,
                data=data
            )

            if result.get("error_code", 0) != 0:
                raise UploadError(f"Erro no frame {offset}: {result}")

        except PixooConnectionError:
            raise
        except Exception as e:
            raise UploadError(f"Falha ao enviar frame {offset}: {e}")

    return {
        "success": True,
        "frames_sent": total_frames,
        "speed_ms": speed
    }


def upload_single_frame(frame: Image.Image) -> dict:
    """
    Envia uma única imagem estática para o Pixoo.

    Args:
        frame: Imagem PIL

    Returns:
        Dict com resultado do upload
    """
    conn = get_pixoo_connection()

    if not conn.is_connected:
        raise PixooConnectionError("Não conectado ao Pixoo")

    try:
        reset_gif_buffer()
        data = frame_to_base64(frame)
        result = send_gif_frame(
            pic_num=1,
            pic_offset=0,
            speed=1000,  # 1 segundo (não importa para imagem estática)
            data=data
        )

        if result.get("error_code", 0) != 0:
            raise UploadError(f"Erro ao enviar imagem: {result}")

        return {"success": True, "frames_sent": 1}

    except PixooConnectionError:
        raise
    except Exception as e:
        raise UploadError(f"Falha ao enviar imagem: {e}")
