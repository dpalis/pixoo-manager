"""
Service para escalar previews de GIF.

Centraliza a logica de scaling que era duplicada em 3 routers.
"""

import io
from pathlib import Path

from PIL import Image

from app.config import PREVIEW_SCALE


def scale_gif(path: Path, scale: int = 16) -> io.BytesIO:
    """
    Escala um GIF/imagem para preview maior.

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

    # Limitar scale para evitar imagens muito grandes
    scale = min(max(scale, 1), PREVIEW_SCALE)

    try:
        with Image.open(path) as img:
            new_size = (img.size[0] * scale, img.size[1] * scale)

            # GIF animado: escalar cada frame
            if hasattr(img, 'n_frames') and img.n_frames > 1:
                frames = []
                durations = []

                for frame_idx in range(img.n_frames):
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

    except Exception as e:
        raise ValueError(f"Erro ao escalar imagem: {e}")
