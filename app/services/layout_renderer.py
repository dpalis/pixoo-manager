"""
Serviço para renderização de fundos para layouts do Pixoo 64.

Gera imagens 64x64 para uso como fundo de layouts com múltiplas linhas de texto.
Suporta cores sólidas, gradientes e padrões geométricos.
"""

from enum import Enum
from typing import Tuple

from PIL import Image

from app.config import PIXOO_SIZE


class GradientDirection(str, Enum):
    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"
    DIAGONAL = "diagonal"


class PatternType(str, Enum):
    CHECKERBOARD = "checkerboard"
    STRIPES_H = "stripes_h"
    STRIPES_V = "stripes_v"
    DOTS = "dots"


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Converte cor hex #RRGGBB para tupla RGB."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def render_solid(color: str) -> Image.Image:
    """
    Gera imagem 64x64 com cor sólida.

    Args:
        color: Cor em formato hex #RRGGBB

    Returns:
        Imagem PIL RGB 64x64
    """
    rgb = hex_to_rgb(color)
    return Image.new('RGB', (PIXOO_SIZE, PIXOO_SIZE), rgb)


def render_gradient(
    color_start: str,
    color_end: str,
    direction: GradientDirection = GradientDirection.VERTICAL
) -> Image.Image:
    """
    Gera imagem 64x64 com gradiente entre duas cores.

    Args:
        color_start: Cor inicial em hex #RRGGBB
        color_end: Cor final em hex #RRGGBB
        direction: Direção do gradiente

    Returns:
        Imagem PIL RGB 64x64
    """
    rgb_start = hex_to_rgb(color_start)
    rgb_end = hex_to_rgb(color_end)

    img = Image.new('RGB', (PIXOO_SIZE, PIXOO_SIZE))
    pixels = img.load()

    for y in range(PIXOO_SIZE):
        for x in range(PIXOO_SIZE):
            # Calcular fator de interpolação baseado na direção
            if direction == GradientDirection.VERTICAL:
                t = y / (PIXOO_SIZE - 1)
            elif direction == GradientDirection.HORIZONTAL:
                t = x / (PIXOO_SIZE - 1)
            else:  # DIAGONAL
                t = (x + y) / (2 * (PIXOO_SIZE - 1))

            # Interpolar cores
            r = int(rgb_start[0] + (rgb_end[0] - rgb_start[0]) * t)
            g = int(rgb_start[1] + (rgb_end[1] - rgb_start[1]) * t)
            b = int(rgb_start[2] + (rgb_end[2] - rgb_start[2]) * t)

            pixels[x, y] = (r, g, b)

    return img


def render_pattern(
    pattern_type: PatternType,
    color1: str,
    color2: str,
    cell_size: int = 8
) -> Image.Image:
    """
    Gera imagem 64x64 com padrão geométrico.

    Args:
        pattern_type: Tipo de padrão
        color1: Primeira cor em hex #RRGGBB
        color2: Segunda cor em hex #RRGGBB
        cell_size: Tamanho das células do padrão em pixels

    Returns:
        Imagem PIL RGB 64x64
    """
    rgb1 = hex_to_rgb(color1)
    rgb2 = hex_to_rgb(color2)

    img = Image.new('RGB', (PIXOO_SIZE, PIXOO_SIZE), rgb1)
    pixels = img.load()

    for y in range(PIXOO_SIZE):
        for x in range(PIXOO_SIZE):
            use_color2 = False

            if pattern_type == PatternType.CHECKERBOARD:
                # Xadrez: alterna baseado em célula
                cell_x = x // cell_size
                cell_y = y // cell_size
                use_color2 = (cell_x + cell_y) % 2 == 1

            elif pattern_type == PatternType.STRIPES_H:
                # Listras horizontais
                use_color2 = (y // cell_size) % 2 == 1

            elif pattern_type == PatternType.STRIPES_V:
                # Listras verticais
                use_color2 = (x // cell_size) % 2 == 1

            elif pattern_type == PatternType.DOTS:
                # Pontos: círculos em grid
                cell_x = x % cell_size
                cell_y = y % cell_size
                center = cell_size // 2
                # Raio do ponto é 1/3 do tamanho da célula
                radius = cell_size // 3
                dist_sq = (cell_x - center) ** 2 + (cell_y - center) ** 2
                use_color2 = dist_sq <= radius ** 2

            if use_color2:
                pixels[x, y] = rgb2

    return img


# Tipo de fundo para uso externo
class BackgroundType(str, Enum):
    SOLID = "solid"
    GRADIENT = "gradient"
    PATTERN = "pattern"
    IMAGE = "image"  # Preparado para expansão futura


def render_background(
    bg_type: BackgroundType,
    color: str = "#000000",
    gradient_start: str = "#000000",
    gradient_end: str = "#333333",
    gradient_direction: GradientDirection = GradientDirection.VERTICAL,
    pattern_type: PatternType = PatternType.CHECKERBOARD,
    pattern_color1: str = "#000000",
    pattern_color2: str = "#1a1a2e",
    pattern_cell_size: int = 8,
) -> Image.Image:
    """
    Renderiza fundo baseado no tipo e configurações.

    Args:
        bg_type: Tipo de fundo (solid, gradient, pattern)
        color: Cor para fundo sólido
        gradient_start: Cor inicial do gradiente
        gradient_end: Cor final do gradiente
        gradient_direction: Direção do gradiente
        pattern_type: Tipo de padrão
        pattern_color1: Primeira cor do padrão
        pattern_color2: Segunda cor do padrão
        pattern_cell_size: Tamanho das células do padrão

    Returns:
        Imagem PIL RGB 64x64
    """
    if bg_type == BackgroundType.SOLID:
        return render_solid(color)

    elif bg_type == BackgroundType.GRADIENT:
        return render_gradient(gradient_start, gradient_end, gradient_direction)

    elif bg_type == BackgroundType.PATTERN:
        return render_pattern(pattern_type, pattern_color1, pattern_color2, pattern_cell_size)

    elif bg_type == BackgroundType.IMAGE:
        # Placeholder para expansão futura
        # Por enquanto, retorna preto sólido
        return render_solid("#000000")

    # Fallback
    return render_solid("#000000")
