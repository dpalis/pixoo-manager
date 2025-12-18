"""
Serviço de conversão de imagens e GIFs para formato Pixoo 64.

Implementa Adaptive Downscaling para preservar detalhes e bordas.
Refatorado de convert_to_pixoo.py para uso como módulo reutilizável.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import imageio.v3 as iio
import numpy as np
from PIL import Image, ImageEnhance, ImageOps, ImageStat
from scipy.ndimage import uniform_filter

from app.config import MAX_CONVERT_FRAMES, PIXOO_SIZE
from app.services.exceptions import ConversionError, TooManyFramesError
from app.services.file_utils import create_temp_output
from app.services.palette_manager import apply_palette_to_frames, create_global_palette

# ============================================
# Image Processing Constants
# ============================================

# Brightness detection threshold - images below this are considered "dark"
DARK_IMAGE_THRESHOLD = 0.3

# Gamma correction for dark images (< 1.0 = lighter)
# 0.75 provides good balance: brightens without "washing out"
DARK_IMAGE_GAMMA = 0.75

# Enhancement factors for dark images (gentler than defaults)
DARK_IMAGE_CONTRAST = 1.15
DARK_IMAGE_SATURATION = 1.1

# Default enhancement factors for LED display
# NOTE: These are the "moderate" defaults - adaptive detection may override
DEFAULT_CONTRAST = 1.15
DEFAULT_SATURATION = 1.1
DEFAULT_SHARPNESS = 1.2
DEFAULT_BRIGHTNESS_BOOST = 1.0

# Dark halo removal parameters
HALO_THRESHOLD = 35
HALO_RADIUS = 1

# Background darkening parameters
BG_DARKEN_THRESHOLD = 140
BG_DARKEN_FACTOR = 0.55

# ============================================
# Adaptive Enhancement Detection
# ============================================

# Contrast detection threshold (stddev of grayscale)
# stddev >= 30 = high contrast image (clear, well-defined)
# Note: Camel reference images have stddev ~38-40
CONTRAST_HIGH_THRESHOLD = 30

# Enhancement presets for bright images with HIGH contrast
# These images already have good definition - use MINIMAL enhancement
# to preserve quality and avoid flickering.
# Based on analysis of Camel_FIRST.gif reference (stddev ~37.89)
BRIGHT_HIGH_CONTRAST_PARAMS = {
    'contrast': 1.1,      # Very gentle (was 1.15)
    'saturation': 1.05,   # Nearly unchanged (was 1.0)
    'sharpness': 1.2,     # Slight sharpening (was 1.0)
    'brightness_boost': 1.0,
}

# Enhancement presets for bright images with LOW contrast
# These images need moderate enhancement to improve definition
BRIGHT_LOW_CONTRAST_PARAMS = {
    'contrast': 1.15,     # Moderate (was 1.25)
    'saturation': 1.1,    # Gentle (was 1.15)
    'sharpness': 1.25,    # Moderate (was 1.3)
    'brightness_boost': 1.02,
}


@dataclass
class ConvertOptions:
    """Opções de conversão para GIF."""
    target_size: int = PIXOO_SIZE
    max_frames: int = MAX_CONVERT_FRAMES
    enhance: bool = True
    led_optimize: bool = True
    focus_center: bool = False
    darken_bg: bool = False
    num_colors: int = 0  # 0 = não quantizar
    auto_brightness: bool = True  # Ajuste automático para imagens escuras


@dataclass
class GifMetadata:
    """Metadados de um GIF processado."""
    width: int
    height: int
    frames: int
    duration_ms: int
    file_size: int
    path: Path


def load_gif_frames(path: Path) -> Tuple[List[Image.Image], List[int]]:
    """
    Carrega todos os frames de um GIF e suas durações.

    Args:
        path: Caminho do arquivo GIF

    Returns:
        Tupla (lista de frames PIL, lista de durações em ms)
    """
    frames = []
    durations = []

    with Image.open(path) as img:
        for frame_num in range(getattr(img, 'n_frames', 1)):
            img.seek(frame_num)
            # Converter para RGBA para consistência
            frame = img.convert('RGBA')
            frames.append(frame.copy())
            # Duração em ms (default 100ms se não especificado)
            durations.append(img.info.get('duration', 100))

    return frames, durations


def smart_crop(image: Image.Image, target_size: int = PIXOO_SIZE) -> Image.Image:
    """
    Crop inteligente que preserva aspect ratio e centraliza o conteúdo.

    1. Escala a imagem para que o MENOR lado tenha target_size
    2. Faz crop central para 64x64

    Args:
        image: Imagem PIL
        target_size: Tamanho alvo (default 64)

    Returns:
        Imagem cropada e redimensionada
    """
    w, h = image.size

    # Calcular escala para que o menor lado seja target_size
    if w < h:
        # Imagem vertical - largura é o lado menor
        scale = target_size / w
        new_w = target_size
        new_h = int(h * scale)
    else:
        # Imagem horizontal - altura é o lado menor
        scale = target_size / h
        new_h = target_size
        new_w = int(w * scale)

    # Redimensionar mantendo proporção
    # Usando BILINEAR ao invés de LANCZOS para evitar halos/ringing nas bordas
    resized = image.resize((new_w, new_h), Image.Resampling.BILINEAR)

    # Crop central para 64x64
    left = (new_w - target_size) // 2
    top = (new_h - target_size) // 2
    right = left + target_size
    bottom = top + target_size

    cropped = resized.crop((left, top, right, bottom))

    return cropped


def remove_dark_halos(image: Image.Image, threshold: int = 40, radius: int = 1) -> Image.Image:
    """
    Remove halos escuros (contornos indesejados) causados por anti-aliasing.

    Detecta pixels escuros isolados perto de transições de cor e substitui
    pela média dos vizinhos. Usa scipy.ndimage.uniform_filter para performance.

    Args:
        image: Imagem PIL em RGB
        threshold: Diferença de luminosidade para considerar halo
        radius: Raio de busca de vizinhos

    Returns:
        Imagem com halos removidos
    """
    img_array = np.array(image, dtype=np.float32)

    # Calcular luminosidade
    luminosity = np.mean(img_array, axis=2)

    # Calcular média dos vizinhos usando uniform_filter (O(n) vs O(n*k²))
    kernel_size = 2 * radius + 1
    neighbor_avg = uniform_filter(luminosity, size=kernel_size, mode='nearest')

    # Criar máscara de pixels que são halos (muito mais escuros que vizinhos)
    is_halo = luminosity < (neighbor_avg - threshold)

    # Calcular média dos vizinhos para cada canal RGB e aplicar
    result = img_array.copy()
    for c in range(3):
        channel_avg = uniform_filter(img_array[:, :, c], size=kernel_size, mode='nearest')
        result[:, :, c] = np.where(is_halo, channel_avg, img_array[:, :, c])

    # Pillow 12+ deprecou o parâmetro mode em fromarray
    img = Image.fromarray(result.astype(np.uint8))
    return img.convert('RGB') if img.mode != 'RGB' else img


def adaptive_downscale(
    frame: Image.Image,
    target_size: int = PIXOO_SIZE,
) -> Image.Image:
    """
    Downscaling adaptativo que preserva bordas e detalhes.

    Combina:
    1. Smart crop para preservar aspect ratio
    2. Remoção de halos escuros

    Args:
        frame: Frame PIL (RGBA ou RGB)
        target_size: Tamanho alvo (default 64)

    Returns:
        Frame redimensionado para target_size x target_size
    """
    rgb_frame = frame.convert('RGB')

    # Primeiro: smart crop para preservar proporções
    rgb_frame = smart_crop(rgb_frame, target_size)

    # Remover halos escuros (contornos indesejados)
    cleaned = remove_dark_halos(rgb_frame, threshold=HALO_THRESHOLD, radius=HALO_RADIUS)

    return cleaned


def enhance_contrast(image: Image.Image, factor: float = 1.1) -> Image.Image:
    """
    Aumenta levemente o contraste para compensar perda na redução.

    Args:
        image: Imagem PIL
        factor: Fator de contraste (1.0 = sem mudança)

    Returns:
        Imagem com contraste ajustado
    """
    enhancer = ImageEnhance.Contrast(image)
    return enhancer.enhance(factor)


def detect_brightness(image: Image.Image) -> float:
    """
    Detecta brilho médio da imagem.

    Usa média simples (mais rápido que RMS, suficiente para threshold).

    Args:
        image: Imagem PIL (qualquer modo)

    Returns:
        Brilho normalizado (0.0 a 1.0)
    """
    grayscale = image.convert('L')
    stat = ImageStat.Stat(grayscale)
    return stat.mean[0] / 255.0


def detect_contrast(image: Image.Image) -> float:
    """
    Detecta nível de contraste da imagem usando desvio padrão.

    Valores típicos:
    - < 30: Muito baixo contraste (flat, washed out)
    - 30-50: Baixo contraste
    - 50-80: Contraste normal
    - > 80: Alto contraste

    Args:
        image: Imagem PIL (qualquer modo)

    Returns:
        Desvio padrão da luminosidade (0-~127 para imagens típicas)
    """
    grayscale = image.convert('L')
    stat = ImageStat.Stat(grayscale)
    return stat.stddev[0]


def apply_gamma_correction(image: Image.Image, gamma: float = 0.7) -> Image.Image:
    """
    Aplica correção gamma para clarear tons escuros.

    Gamma < 1.0: Clareia (0.5-0.7 para imagens escuras)
    Gamma = 1.0: Sem mudança
    Gamma > 1.0: Escurece

    Args:
        image: Imagem PIL em RGB
        gamma: Fator de correção

    Returns:
        Imagem com gamma corrigido
    """
    # Criar lookup table para performance
    # Fórmula: output = input^gamma
    # gamma < 1.0 → clareia (levanta tons escuros)
    # gamma > 1.0 → escurece
    lut = [int((i / 255.0) ** gamma * 255.0) for i in range(256)]

    # Aplicar LUT a cada canal (RGB = 3 canais)
    return image.point(lut * 3)


def enhance_for_led_display(
    image: Image.Image,
    contrast: float = DEFAULT_CONTRAST,
    saturation: float = DEFAULT_SATURATION,
    sharpness: float = DEFAULT_SHARPNESS,
    auto_brightness: bool = True
) -> Image.Image:
    """
    Otimiza imagem para displays LED como Pixoo 64.

    Usa detecção adaptativa para escolher parâmetros:
    - Imagens escuras: gamma correction + enhancement moderado
    - Imagens claras + baixo contraste: enhancement moderado
    - Imagens claras + alto contraste: enhancement mínimo (preservar qualidade)

    A detecção adaptativa evita flickering em imagens claras e bem definidas,
    que não precisam de enhancement agressivo.

    Args:
        image: Imagem PIL
        contrast: Fator de contraste (usado apenas se auto_brightness=False)
        saturation: Fator de saturação (usado apenas se auto_brightness=False)
        sharpness: Fator de nitidez (usado apenas se auto_brightness=False)
        auto_brightness: Detectar características e ajustar automaticamente

    Returns:
        Imagem otimizada para LED
    """
    img = image
    brightness_boost = DEFAULT_BRIGHTNESS_BOOST

    if auto_brightness:
        brightness = detect_brightness(image)
        image_contrast = detect_contrast(image)

        if brightness < DARK_IMAGE_THRESHOLD:
            # Pipeline DARK: gamma correction + moderate enhancement
            img = apply_gamma_correction(img, gamma=DARK_IMAGE_GAMMA)
            contrast = DARK_IMAGE_CONTRAST
            saturation = DARK_IMAGE_SATURATION
            sharpness = 1.2  # Moderate sharpness for dark images
            brightness_boost = 1.05

        elif image_contrast >= CONTRAST_HIGH_THRESHOLD:
            # Pipeline BRIGHT_HIGH_CONTRAST: minimal enhancement
            # These images are already clear - avoid flickering
            contrast = BRIGHT_HIGH_CONTRAST_PARAMS['contrast']
            saturation = BRIGHT_HIGH_CONTRAST_PARAMS['saturation']
            sharpness = BRIGHT_HIGH_CONTRAST_PARAMS['sharpness']
            brightness_boost = BRIGHT_HIGH_CONTRAST_PARAMS['brightness_boost']

        else:
            # Pipeline BRIGHT_LOW_CONTRAST: moderate enhancement
            # These images need some boost but not aggressive
            contrast = BRIGHT_LOW_CONTRAST_PARAMS['contrast']
            saturation = BRIGHT_LOW_CONTRAST_PARAMS['saturation']
            sharpness = BRIGHT_LOW_CONTRAST_PARAMS['sharpness']
            brightness_boost = BRIGHT_LOW_CONTRAST_PARAMS['brightness_boost']

    # Apply enhancement in correct order
    # 1. Contrast - separate figure from background
    img = ImageEnhance.Contrast(img).enhance(contrast)

    # 2. Saturation - more vivid colors
    img = ImageEnhance.Color(img).enhance(saturation)

    # 3. Brightness - compensate for contrast
    img = ImageEnhance.Brightness(img).enhance(brightness_boost)

    # 4. Sharpening - more definition
    img = ImageEnhance.Sharpness(img).enhance(sharpness)

    return img


def darken_background(
    image: Image.Image,
    threshold: int = 140,
    darken_factor: float = 0.6
) -> Image.Image:
    """
    Escurece pixels mais escuros (fundo) para destacar figura clara em primeiro plano.

    Pixels com luminosidade abaixo do threshold são escurecidos.
    Pixels claros (figura principal) são preservados.

    Args:
        image: Imagem PIL
        threshold: Limiar de luminosidade
        darken_factor: Fator de escurecimento (0-1)

    Returns:
        Imagem com fundo escurecido
    """
    img_array = np.array(image, dtype=np.float32)

    # Calcular luminosidade de cada pixel
    luminosity = 0.299 * img_array[:,:,0] + 0.587 * img_array[:,:,1] + 0.114 * img_array[:,:,2]

    # Criar máscara suave: pixels escuros = 1, pixels claros = 0
    # Usando transição suave para evitar bordas duras
    mask = np.clip((threshold - luminosity) / 50, 0, 1)

    # Aplicar escurecimento baseado na máscara
    for c in range(3):
        # Quanto mais escuro o pixel, mais escurecemos
        img_array[:,:,c] = img_array[:,:,c] * (1 - mask * (1 - darken_factor))

    img_array = np.clip(img_array, 0, 255).astype(np.uint8)

    # Pillow 12+ deprecou o parâmetro mode em fromarray
    img = Image.fromarray(img_array)
    return img.convert('RGB') if img.mode != 'RGB' else img


def focus_on_center(image: Image.Image, vignette_strength: float = 0.3) -> Image.Image:
    """
    Aplica efeito sutil para destacar o centro da imagem.
    Escurece levemente as bordas para direcionar atenção ao centro.

    Args:
        image: Imagem PIL
        vignette_strength: Intensidade do efeito vinheta

    Returns:
        Imagem com efeito de foco central
    """
    img_array = np.array(image, dtype=np.float32)
    h, w = img_array.shape[:2]

    # Criar máscara de vinheta
    y, x = np.ogrid[:h, :w]
    center_y, center_x = h / 2, w / 2

    # Distância normalizada do centro
    dist = np.sqrt((x - center_x)**2 + (y - center_y)**2)
    max_dist = np.sqrt(center_x**2 + center_y**2)
    dist_normalized = dist / max_dist

    # Aplicar escurecimento nas bordas (suave)
    vignette = 1 - (dist_normalized ** 2) * vignette_strength
    vignette = np.clip(vignette, 0.7, 1.0)  # Limitar para não escurecer demais

    # Aplicar a cada canal
    for c in range(3):
        img_array[:, :, c] *= vignette

    img_array = np.clip(img_array, 0, 255).astype(np.uint8)

    # Pillow 12+ deprecou o parâmetro mode em fromarray
    img = Image.fromarray(img_array)
    return img.convert('RGB') if img.mode != 'RGB' else img


def quantize_colors(image: Image.Image, num_colors: int = 32) -> Image.Image:
    """
    Reduz paleta de cores para estética pixel art.

    Args:
        image: Imagem PIL
        num_colors: Número de cores na paleta

    Returns:
        Imagem quantizada
    """
    # Usar median cut para quantização
    quantized = image.quantize(colors=num_colors, method=Image.Quantize.MEDIANCUT)
    return quantized.convert('RGB')


def is_pixoo_ready(path: Path) -> bool:
    """
    Verifica se um GIF já está no formato correto para o Pixoo (64x64).

    Args:
        path: Caminho do arquivo GIF

    Returns:
        True se já está em 64x64
    """
    try:
        with Image.open(path) as img:
            return img.size == (PIXOO_SIZE, PIXOO_SIZE)
    except Exception:
        return False


def convert_image(
    input_path: Path,
    options: Optional[ConvertOptions] = None
) -> Tuple[Path, GifMetadata]:
    """
    Converte uma imagem para formato Pixoo 64x64.

    Args:
        input_path: Caminho da imagem de entrada
        options: Opcoes de conversao

    Returns:
        Tupla (caminho do GIF convertido, metadados)
    """
    if options is None:
        options = ConvertOptions()

    try:
        with Image.open(input_path) as img:
            # Aplicar rotação EXIF (fotos de celular podem ter orientação nos metadados)
            img = ImageOps.exif_transpose(img)
            converted = convert_image_pil(img, options)
    except Exception as e:
        raise ConversionError(f"Falha ao carregar imagem: {e}")

    # Criar arquivo de saida como GIF
    output_path = create_temp_output(".gif")

    try:
        converted.save(output_path, format="GIF")

        metadata = GifMetadata(
            width=PIXOO_SIZE,
            height=PIXOO_SIZE,
            frames=1,
            duration_ms=0,
            file_size=output_path.stat().st_size,
            path=output_path
        )

        return output_path, metadata

    except Exception as e:
        raise ConversionError(f"Falha ao salvar imagem: {e}")


def convert_image_pil(image: Image.Image, options: Optional[ConvertOptions] = None) -> Image.Image:
    """
    Converte uma imagem PIL para formato Pixoo.

    Args:
        image: Imagem PIL
        options: Opcoes de conversao

    Returns:
        Imagem convertida para 64x64
    """
    if options is None:
        options = ConvertOptions()

    # Downscale adaptativo
    converted = adaptive_downscale(image, options.target_size)

    # Melhorar contraste básico (opcional)
    if options.enhance and not options.led_optimize:
        converted = enhance_contrast(converted, factor=1.15)

    # Otimização para LED display (usa adaptive detection)
    if options.led_optimize:
        converted = enhance_for_led_display(
            converted,
            contrast=DEFAULT_CONTRAST,
            saturation=DEFAULT_SATURATION,
            sharpness=DEFAULT_SHARPNESS,
            auto_brightness=options.auto_brightness
        )

    # Escurecer fundo para destacar figura clara
    if options.darken_bg:
        converted = darken_background(converted, threshold=BG_DARKEN_THRESHOLD, darken_factor=BG_DARKEN_FACTOR)

    # Destacar centro da imagem
    if options.focus_center:
        converted = focus_on_center(converted, vignette_strength=0.25)

    # Quantizar cores (opcional)
    if options.num_colors > 0:
        converted = quantize_colors(converted, options.num_colors)

    return converted


def convert_gif(
    input_path: Path,
    options: Optional[ConvertOptions] = None,
    progress_callback: Optional[callable] = None
) -> Tuple[Path, GifMetadata]:
    """
    Converte um GIF para formato Pixoo 64.

    Args:
        input_path: Caminho do GIF de entrada
        options: Opções de conversão
        progress_callback: Callback para progresso (recebe frame atual e total)

    Returns:
        Tupla (caminho do GIF convertido, metadados)

    Raises:
        ConversionError: Se a conversão falhar
        TooManyFramesError: Se exceder limite de frames
    """
    if options is None:
        options = ConvertOptions()

    try:
        frames, durations = load_gif_frames(input_path)
    except Exception as e:
        raise ConversionError(f"Falha ao carregar GIF: {e}")

    # Limitar frames se necessário
    if len(frames) > options.max_frames:
        # Selecionar frames uniformemente distribuídos
        indices = np.linspace(0, len(frames) - 1, options.max_frames, dtype=int)
        frames = [frames[i] for i in indices]
        durations = [durations[i] for i in indices]

    # Processar cada frame
    converted_frames = []
    total_frames = len(frames)

    for i, frame in enumerate(frames):
        if progress_callback:
            progress_callback(i + 1, total_frames)

        converted = convert_image_pil(frame, options)
        converted_frames.append(converted)

    # Aplicar paleta global para consistência (anti-flickering)
    if len(converted_frames) > 1:
        global_palette = create_global_palette(converted_frames, num_colors=256, sample_rate=4)
        converted_frames = apply_palette_to_frames(converted_frames, global_palette)

    # Criar arquivo de saída
    output_path = create_temp_output(".gif")

    try:
        # Converter para arrays numpy para imageio
        frame_arrays = [np.array(f) for f in converted_frames]

        # Calcular duração média se variável
        avg_duration = sum(durations) / len(durations)
        fps = 1000 / avg_duration if avg_duration > 0 else 10

        # imageio v3 deprecou fps, usar duration (ms por frame)
        duration_ms = int(1000 / fps) if fps > 0 else 100
        iio.imwrite(
            output_path,
            frame_arrays,
            duration=duration_ms,
            loop=0  # Loop infinito
        )

        # Criar metadados
        metadata = GifMetadata(
            width=PIXOO_SIZE,
            height=PIXOO_SIZE,
            frames=len(converted_frames),
            duration_ms=int(avg_duration * len(converted_frames)),
            file_size=output_path.stat().st_size,
            path=output_path
        )

        return output_path, metadata

    except Exception as e:
        # Limpar arquivo parcial
        if output_path.exists():
            output_path.unlink()
        raise ConversionError(f"Falha ao salvar GIF: {e}")


def create_preview(input_path: Path, scale: int = 4) -> bytes:
    """
    Cria versão ampliada do GIF para preview visual.

    Args:
        input_path: Caminho do GIF
        scale: Fator de escala (default 4x)

    Returns:
        Bytes do GIF de preview
    """
    frames, durations = load_gif_frames(input_path)

    scaled_frames = []
    for frame in frames:
        w, h = frame.size
        scaled = frame.resize((w * scale, h * scale), Image.Resampling.NEAREST)
        scaled_frames.append(np.array(scaled.convert('RGB')))

    avg_duration = sum(durations) / len(durations)
    fps = 1000 / avg_duration if avg_duration > 0 else 10

    # Salvar para bytes
    import io
    buffer = io.BytesIO()
    # imageio v3 deprecou fps, usar duration (ms por frame)
    duration_ms = int(1000 / fps) if fps > 0 else 100
    iio.imwrite(buffer, scaled_frames, extension=".gif", duration=duration_ms, loop=0)
    return buffer.getvalue()
