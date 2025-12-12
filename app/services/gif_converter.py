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
from collections import Counter
from PIL import Image, ImageEnhance, ImageFilter

from app.config import MAX_CONVERT_FRAMES, PIXOO_SIZE
from app.services.exceptions import ConversionError, TooManyFramesError
from app.services.file_utils import create_temp_output


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


def detect_edges(image: Image.Image, threshold: int = 30) -> Image.Image:
    """
    Detecta bordas usando filtro Sobel.

    Args:
        image: Imagem PIL
        threshold: Limiar para detecção de bordas

    Returns:
        Máscara de bordas (imagem em escala de cinza)
    """
    gray = image.convert('L')

    # Sobel X e Y
    sobel_x = gray.filter(ImageFilter.Kernel(
        size=(3, 3),
        kernel=[-1, 0, 1, -2, 0, 2, -1, 0, 1],
        scale=1
    ))
    sobel_y = gray.filter(ImageFilter.Kernel(
        size=(3, 3),
        kernel=[-1, -2, -1, 0, 0, 0, 1, 2, 1],
        scale=1
    ))

    # Magnitude
    arr_x = np.array(sobel_x, dtype=np.float32)
    arr_y = np.array(sobel_y, dtype=np.float32)
    magnitude = np.sqrt(arr_x**2 + arr_y**2)

    # Threshold para criar máscara binária
    edge_mask = (magnitude > threshold).astype(np.uint8) * 255

    return Image.fromarray(edge_mask, mode='L')


def majority_color_block_sampling(image: Image.Image, target_size: int) -> Image.Image:
    """
    Divide a imagem em blocos e seleciona a cor mais frequente de cada bloco.
    Preserva detalhes melhor que interpolação simples.

    Args:
        image: Imagem PIL em RGB
        target_size: Tamanho alvo (quadrado)

    Returns:
        Imagem redimensionada
    """
    img_array = np.array(image.convert('RGB'))
    h, w = img_array.shape[:2]

    block_h = h / target_size
    block_w = w / target_size

    result = np.zeros((target_size, target_size, 3), dtype=np.uint8)

    for y in range(target_size):
        for x in range(target_size):
            # Definir limites do bloco
            y_start = int(y * block_h)
            y_end = int((y + 1) * block_h)
            x_start = int(x * block_w)
            x_end = int((x + 1) * block_w)

            # Extrair bloco
            block = img_array[y_start:y_end, x_start:x_end]

            if block.size == 0:
                continue

            # Encontrar cor mais frequente
            pixels = block.reshape(-1, 3)
            # Quantizar levemente para agrupar cores similares
            quantized = (pixels // 8) * 8
            pixel_tuples = [tuple(p) for p in quantized]
            most_common = Counter(pixel_tuples).most_common(1)[0][0]

            result[y, x] = most_common

    return Image.fromarray(result, mode='RGB')


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
    pela cor do vizinho mais próximo.

    Args:
        image: Imagem PIL em RGB
        threshold: Diferença de luminosidade para considerar halo
        radius: Raio de busca de vizinhos

    Returns:
        Imagem com halos removidos
    """
    img_array = np.array(image, dtype=np.float32)
    h, w = img_array.shape[:2]

    # Trabalhar com luminosidade (simplificado: usar média RGB)
    luminosity = np.mean(img_array, axis=2)

    result = img_array.copy()

    for y in range(radius, h - radius):
        for x in range(radius, w - radius):
            current_lum = luminosity[y, x]

            # Pegar luminosidade dos vizinhos
            neighbors_lum = []
            neighbors_colors = []
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if dy == 0 and dx == 0:
                        continue
                    ny, nx = y + dy, x + dx
                    neighbors_lum.append(luminosity[ny, nx])
                    neighbors_colors.append(img_array[ny, nx])

            avg_neighbor_lum = np.mean(neighbors_lum)

            # Se o pixel atual é muito mais escuro que os vizinhos, é um halo
            if current_lum < avg_neighbor_lum - threshold:
                # Substituir pela média dos vizinhos mais claros
                bright_neighbors = [c for c, l in zip(neighbors_colors, neighbors_lum)
                                   if l > current_lum + 10]
                if bright_neighbors:
                    result[y, x] = np.mean(bright_neighbors, axis=0)

    return Image.fromarray(result.astype(np.uint8), mode='RGB')


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
    cleaned = remove_dark_halos(rgb_frame, threshold=35, radius=1)

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


def enhance_for_led_display(
    image: Image.Image,
    contrast: float = 1.4,
    saturation: float = 1.3,
    sharpness: float = 1.5
) -> Image.Image:
    """
    Otimiza imagem para displays LED como Pixoo 64.

    - Aumenta contraste para separar figura do fundo
    - Aumenta saturação para cores mais vivas no LED
    - Aplica sharpening para definição

    Args:
        image: Imagem PIL
        contrast: Fator de contraste
        saturation: Fator de saturação
        sharpness: Fator de nitidez

    Returns:
        Imagem otimizada para LED
    """
    # 1. Contraste - separa figura do fundo
    img = ImageEnhance.Contrast(image).enhance(contrast)

    # 2. Saturação - cores mais vivas
    img = ImageEnhance.Color(img).enhance(saturation)

    # 3. Brilho leve - compensa o contraste
    img = ImageEnhance.Brightness(img).enhance(1.05)

    # 4. Sharpening - mais definição
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

    return Image.fromarray(img_array, mode='RGB')


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

    return Image.fromarray(img_array, mode='RGB')


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

    # Otimização para LED display (mais agressiva)
    if options.led_optimize:
        converted = enhance_for_led_display(converted, contrast=1.4, saturation=1.3, sharpness=1.5)

    # Escurecer fundo para destacar figura clara
    if options.darken_bg:
        converted = darken_background(converted, threshold=140, darken_factor=0.55)

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

    # Criar arquivo de saída
    output_path = create_temp_output(".gif")

    try:
        # Converter para arrays numpy para imageio
        frame_arrays = [np.array(f) for f in converted_frames]

        # Calcular duração média se variável
        avg_duration = sum(durations) / len(durations)
        fps = 1000 / avg_duration if avg_duration > 0 else 10

        iio.imwrite(
            output_path,
            frame_arrays,
            fps=fps,
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
    iio.imwrite(buffer, scaled_frames, extension=".gif", fps=fps, loop=0)
    return buffer.getvalue()


def image_to_single_frame_gif(
    image: Image.Image,
    options: Optional[ConvertOptions] = None
) -> Tuple[Path, GifMetadata]:
    """
    Converte uma imagem estática para GIF de um frame.

    Args:
        image: Imagem PIL
        options: Opções de conversão

    Returns:
        Tupla (caminho do GIF, metadados)
    """
    if options is None:
        options = ConvertOptions()

    converted = convert_image(image, options)

    output_path = create_temp_output(".gif")

    try:
        frame_array = np.array(converted)
        iio.imwrite(output_path, [frame_array], fps=1, loop=0)

        metadata = GifMetadata(
            width=PIXOO_SIZE,
            height=PIXOO_SIZE,
            frames=1,
            duration_ms=1000,
            file_size=output_path.stat().st_size,
            path=output_path
        )

        return output_path, metadata

    except Exception as e:
        if output_path.exists():
            output_path.unlink()
        raise ConversionError(f"Falha ao criar GIF: {e}")
