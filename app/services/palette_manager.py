"""
Gerenciamento de paleta de cores para GIFs.

Funções compartilhadas entre gif_converter e video_converter
para criar e aplicar paletas consistentes em animações.
"""

from typing import List

from PIL import Image

from app.services.exceptions import ConversionError


def create_global_palette(
    frames: List[Image.Image],
    num_colors: int = 256,
    sample_rate: int = 4,
    pixels_per_frame: int = 1000
) -> Image.Image:
    """
    Cria paleta de cores otimizada a partir de múltiplos frames.

    Usa amostragem de pixels (não concatenação de imagens) para
    baixo consumo de memória (~10KB vs ~850KB).

    Args:
        frames: Lista de frames PIL em RGB
        num_colors: Número de cores na paleta (max 256 para GIF)
        sample_rate: Amostrar 1 a cada N frames (para performance)
        pixels_per_frame: Máximo de pixels por frame para amostragem

    Returns:
        Imagem quantizada com paleta otimizada (usar .palette)
    """
    if not frames:
        raise ConversionError("Lista de frames vazia")

    # Amostrar frames para não usar memória demais
    sampled = frames[::sample_rate] if len(frames) > sample_rate else frames

    # Coletar pixels amostrados de todos os frames
    all_pixels = []
    for frame in sampled:
        rgb_frame = frame.convert('RGB')
        pixels = list(rgb_frame.getdata())

        # Amostrar pixels uniformemente se muitos
        if len(pixels) > pixels_per_frame:
            step = len(pixels) // pixels_per_frame
            pixels = pixels[::step][:pixels_per_frame]

        all_pixels.extend(pixels)

    # Criar imagem quadrada com os pixels amostrados
    # Tamanho mínimo para conter todos os pixels
    sample_size = int(len(all_pixels) ** 0.5) + 1
    sample_image = Image.new('RGB', (sample_size, sample_size))
    sample_image.putdata(all_pixels[:sample_size * sample_size])

    # Quantizar para obter paleta otimizada
    palette_image = sample_image.quantize(
        colors=num_colors,
        method=Image.Quantize.MEDIANCUT  # Rápido e bom para animações
    )

    return palette_image


def apply_palette_to_frames(
    frames: List[Image.Image],
    palette_image: Image.Image
) -> List[Image.Image]:
    """
    Aplica mesma paleta a todos os frames para consistência.

    Usa dither=0 (sem dithering) para evitar artefatos temporais.
    Trade-off: gradientes podem ter banding, mas animação será suave.

    Args:
        frames: Lista de frames PIL (esperados em RGB)
        palette_image: Imagem quantizada com paleta (de create_global_palette)

    Returns:
        Lista de frames quantizados com paleta consistente (RGB)
    """
    result = []

    for frame in frames:
        # Evitar conversão se já está em RGB (frames de convert_image_pil já são RGB)
        rgb_frame = frame.convert('RGB') if frame.mode != 'RGB' else frame
        quantized = rgb_frame.quantize(
            palette=palette_image,
            dither=0  # Sem dithering = consistência temporal
        )
        # Converter de volta para RGB (quantize retorna modo 'P')
        result.append(quantized.convert('RGB'))

    return result
