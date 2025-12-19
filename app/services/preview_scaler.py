"""
Service para escalar previews de GIF.

Centraliza a logica de scaling que era duplicada em 3 routers.
Inclui cache LRU para evitar recomputacao.

Usa imageio para salvar GIFs (preserva cores melhor que PIL).
"""

import io
from functools import lru_cache
from pathlib import Path

import imageio.v3 as iio
import numpy as np
from PIL import Image

from app.config import PREVIEW_SCALE

# Limite de frames para scaling (alinhado com MAX_CONVERT_FRAMES)
MAX_FRAMES_FOR_SCALING = 92


@lru_cache(maxsize=32)
def _get_scaled_bytes(path_str: str, scale: int, mtime: float) -> bytes:
    """
    Versao cacheavel do scaling. Usa mtime para invalidar cache se arquivo mudar.

    Cache de 32 entradas (~500MB max no pior caso).
    """
    path = Path(path_str)
    return _scale_gif_impl(path, scale).getvalue()


def _scale_gif_impl(path: Path, scale: int) -> io.BytesIO:
    """Implementacao interna do scaling usando imageio."""
    scale = min(max(scale, 1), PREVIEW_SCALE)

    with Image.open(path) as img:
        new_size = (img.size[0] * scale, img.size[1] * scale)
        n_frames = getattr(img, 'n_frames', 1)

        # Obter duracao do primeiro frame
        duration = img.info.get('duration', 100)

        # Limitar frames
        frames_to_process = min(n_frames, MAX_FRAMES_FOR_SCALING)

        scaled_frames = []
        for frame_idx in range(frames_to_process):
            img.seek(frame_idx)
            frame = img.convert('RGB')
            scaled_frame = frame.resize(new_size, Image.Resampling.NEAREST)
            scaled_frames.append(np.array(scaled_frame))

        # Salvar com imageio (preserva cores melhor)
        output = io.BytesIO()
        iio.imwrite(
            output,
            scaled_frames,
            extension=".gif",
            duration=duration,
            loop=0
        )
        output.seek(0)
        return output


def scale_gif(path: Path, scale: int = 16) -> io.BytesIO:
    """
    Escala um GIF/imagem para preview maior.

    Usa cache LRU para evitar recomputacao. GIFs com mais de 60 frames
    sao truncados para evitar uso excessivo de memoria.

    Args:
        path: Caminho do arquivo GIF/imagem
        scale: Fator de escala (1-32, padrao 16)

    Returns:
        BytesIO com o GIF escalado

    Raises:
        FileNotFoundError: Se o arquivo não existe
        ValueError: Se o arquivo não pode ser processado
    """
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    try:
        # Usar cache com mtime para invalidar se arquivo mudar
        mtime = path.stat().st_mtime
        cached_bytes = _get_scaled_bytes(str(path), scale, mtime)
        return io.BytesIO(cached_bytes)
    except Exception as e:
        raise ValueError(f"Erro ao escalar imagem: {e}")
