"""
Service para escalar previews de GIF.

Centraliza a logica de scaling que era duplicada em 3 routers.
Inclui cache LRU para evitar recomputacao.
"""

import io
from functools import lru_cache
from pathlib import Path

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
    """Implementacao interna do scaling."""
    scale = min(max(scale, 1), PREVIEW_SCALE)

    with Image.open(path) as img:
        new_size = (img.size[0] * scale, img.size[1] * scale)
        n_frames = getattr(img, 'n_frames', 1)

        # GIF animado
        if n_frames > 1:
            # Limitar frames para evitar uso excessivo de memoria
            frames_to_process = min(n_frames, MAX_FRAMES_FOR_SCALING)

            frames = []
            durations = []

            for frame_idx in range(frames_to_process):
                img.seek(frame_idx)
                frame = img.convert('RGBA')
                scaled_frame = frame.resize(new_size, Image.Resampling.NEAREST)
                frames.append(scaled_frame)
                durations.append(img.info.get('duration', 100))

            output = io.BytesIO()
            frames[0].save(
                output,
                format='GIF',
                save_all=True,
                append_images=frames[1:],
                duration=durations,
                loop=img.info.get('loop', 0),
                disposal=2
            )
            output.seek(0)
            return output

        else:
            # Imagem estatica
            frame = img.convert('RGBA')
            scaled_frame = frame.resize(new_size, Image.Resampling.NEAREST)

            output = io.BytesIO()
            scaled_frame.save(output, format='GIF')
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
        FileNotFoundError: Se o arquivo nao existe
        ValueError: Se o arquivo nao pode ser processado
    """
    if not path.exists():
        raise FileNotFoundError(f"Arquivo nao encontrado: {path}")

    try:
        # Usar cache com mtime para invalidar se arquivo mudar
        mtime = path.stat().st_mtime
        cached_bytes = _get_scaled_bytes(str(path), scale, mtime)
        return io.BytesIO(cached_bytes)
    except Exception as e:
        raise ValueError(f"Erro ao escalar imagem: {e}")
