#!/usr/bin/env python3
"""
Conversor de GIFs para Pixoo 64
Implementa Adaptive Downscaling para preservar detalhes e bordas
"""

import sys
from pathlib import Path
from PIL import Image, ImageFilter
import imageio.v3 as iio
import numpy as np
from collections import Counter

# Background removal
try:
    from backgroundremover.bg import remove as remove_bg
    HAS_BG_REMOVER = True
except ImportError:
    HAS_BG_REMOVER = False


def load_gif_frames(path: Path) -> tuple[list[Image.Image], list[int]]:
    """Carrega todos os frames de um GIF e suas durações."""
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
    """Detecta bordas usando filtro Sobel."""
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


def smart_crop(image: Image.Image, target_size: int = 64) -> Image.Image:
    """
    Crop inteligente que preserva aspect ratio e centraliza o conteudo.

    1. Escala a imagem para que o MENOR lado tenha target_size
    2. Faz crop central para 64x64
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

    Detecta pixels escuros isolados perto de transicoes de cor e substitui
    pela cor do vizinho mais proximo.
    """
    img_array = np.array(image, dtype=np.float32)
    h, w = img_array.shape[:2]

    # Converter para LAB para melhor deteccao de luminosidade
    from PIL import ImageCms

    # Trabalhar com luminosidade (simplificado: usar media RGB)
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

            # Se o pixel atual e muito mais escuro que os vizinhos, e um halo
            if current_lum < avg_neighbor_lum - threshold:
                # Substituir pela media dos vizinhos mais claros
                bright_neighbors = [c for c, l in zip(neighbors_colors, neighbors_lum)
                                   if l > current_lum + 10]
                if bright_neighbors:
                    result[y, x] = np.mean(bright_neighbors, axis=0)

    return Image.fromarray(result.astype(np.uint8), mode='RGB')


def adaptive_downscale(
    frame: Image.Image,
    target_size: int = 64,
    edge_threshold: int = 25,
    edge_weight: float = 0.6
) -> Image.Image:
    """
    Downscaling adaptativo que preserva bordas e detalhes.

    Combina:
    1. Smart crop para preservar aspect ratio
    2. Majority Color Block Sampling para detalhes
    3. Detecção de bordas para preservar contornos
    """
    rgb_frame = frame.convert('RGB')

    # Primeiro: smart crop para preservar proporções
    rgb_frame = smart_crop(rgb_frame, target_size)
    w, h = rgb_frame.size

    # A imagem já está em 64x64 após o smart_crop
    # Remover halos escuros (contornos indesejados)
    cleaned = remove_dark_halos(rgb_frame, threshold=35, radius=1)

    return cleaned


def enhance_contrast(image: Image.Image, factor: float = 1.1) -> Image.Image:
    """Aumenta levemente o contraste para compensar perda na redução."""
    from PIL import ImageEnhance
    enhancer = ImageEnhance.Contrast(image)
    return enhancer.enhance(factor)


def enhance_for_led_display(image: Image.Image, contrast: float = 1.4, saturation: float = 1.3, sharpness: float = 1.5) -> Image.Image:
    """
    Otimiza imagem para displays LED como Pixoo 64.

    - Aumenta contraste para separar figura do fundo
    - Aumenta saturacao para cores mais vivas no LED
    - Aplica sharpening para definicao
    """
    from PIL import ImageEnhance, ImageFilter

    # 1. Contraste - separa figura do fundo
    img = ImageEnhance.Contrast(image).enhance(contrast)

    # 2. Saturacao - cores mais vivas
    img = ImageEnhance.Color(img).enhance(saturation)

    # 3. Brilho leve - compensa o contraste
    img = ImageEnhance.Brightness(img).enhance(1.05)

    # 4. Sharpening - mais definicao
    img = ImageEnhance.Sharpness(img).enhance(sharpness)

    return img


def darken_background(image: Image.Image, threshold: int = 140, darken_factor: float = 0.6) -> Image.Image:
    """
    Escurece pixels mais escuros (fundo) para destacar figura clara em primeiro plano.

    Pixels com luminosidade abaixo do threshold sao escurecidos.
    Pixels claros (figura principal) sao preservados.
    """
    img_array = np.array(image, dtype=np.float32)

    # Calcular luminosidade de cada pixel
    luminosity = 0.299 * img_array[:,:,0] + 0.587 * img_array[:,:,1] + 0.114 * img_array[:,:,2]

    # Criar mascara suave: pixels escuros = 1, pixels claros = 0
    # Usando transicao suave para evitar bordas duras
    mask = np.clip((threshold - luminosity) / 50, 0, 1)

    # Aplicar escurecimento baseado na mascara
    for c in range(3):
        # Quanto mais escuro o pixel, mais escurecemos
        img_array[:,:,c] = img_array[:,:,c] * (1 - mask * (1 - darken_factor))

    img_array = np.clip(img_array, 0, 255).astype(np.uint8)

    return Image.fromarray(img_array, mode='RGB')


def focus_on_center(image: Image.Image, vignette_strength: float = 0.3) -> Image.Image:
    """
    Aplica efeito sutil para destacar o centro da imagem.
    Escurece levemente as bordas para direcionar atencao ao centro.
    """
    import numpy as np

    img_array = np.array(image, dtype=np.float32)
    h, w = img_array.shape[:2]

    # Criar mascara de vinheta
    y, x = np.ogrid[:h, :w]
    center_y, center_x = h / 2, w / 2

    # Distancia normalizada do centro
    dist = np.sqrt((x - center_x)**2 + (y - center_y)**2)
    max_dist = np.sqrt(center_x**2 + center_y**2)
    dist_normalized = dist / max_dist

    # Aplicar escurecimento nas bordas (suave)
    vignette = 1 - (dist_normalized ** 2) * vignette_strength
    vignette = np.clip(vignette, 0.7, 1.0)  # Limitar para nao escurecer demais

    # Aplicar a cada canal
    for c in range(3):
        img_array[:, :, c] *= vignette

    img_array = np.clip(img_array, 0, 255).astype(np.uint8)

    return Image.fromarray(img_array, mode='RGB')


def quantize_colors(image: Image.Image, num_colors: int = 32) -> Image.Image:
    """Reduz paleta de cores para estética pixel art."""
    # Usar median cut para quantização
    quantized = image.quantize(colors=num_colors, method=Image.Quantize.MEDIANCUT)
    return quantized.convert('RGB')


def remove_background_and_replace(image: Image.Image, bg_color: tuple = (30, 30, 40)) -> Image.Image:
    """
    Remove o fundo da imagem e substitui por uma cor solida.

    Args:
        image: Imagem PIL em RGB
        bg_color: Cor do novo fundo (R, G, B)

    Returns:
        Imagem com fundo substituido
    """
    if not HAS_BG_REMOVER:
        print("backgroundremover nao disponivel")
        return image

    import io

    # Converter PIL para bytes
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    img_bytes = img_byte_arr.getvalue()

    # Remover fundo (retorna PNG com transparencia)
    result_bytes = remove_bg(img_bytes)

    # Carregar resultado com alpha
    result_img = Image.open(io.BytesIO(result_bytes)).convert('RGBA')

    # Criar novo fundo com cor solida
    background = Image.new('RGBA', result_img.size, bg_color + (255,))

    # Compor figura sobre o fundo
    composite = Image.alpha_composite(background, result_img)

    return composite.convert('RGB')


def convert_gif(
    input_path: Path,
    output_path: Path,
    target_size: int = 64,
    max_frames: int = 92,  # Limite do Pixoo 64
    enhance: bool = True,
    led_optimize: bool = False,  # Otimizacao para LED display
    focus_center: bool = False,  # Destacar centro
    darken_bg: bool = False,  # Escurecer fundo para destacar figura clara
    remove_bg: bool = False,  # Remover fundo e substituir por cor solida
    bg_color: tuple = (30, 30, 40),  # Cor do fundo quando remove_bg=True
    num_colors: int = 0  # 0 = não quantizar
) -> None:
    """Converte um GIF para formato Pixoo 64."""

    print(f"Carregando: {input_path.name}")
    frames, durations = load_gif_frames(input_path)
    print(f"   {len(frames)} frames, {frames[0].size[0]}x{frames[0].size[1]}")

    # Limitar frames se necessário
    if len(frames) > max_frames:
        print(f"   Reduzindo de {len(frames)} para {max_frames} frames")
        # Selecionar frames uniformemente distribuídos
        indices = np.linspace(0, len(frames) - 1, max_frames, dtype=int)
        frames = [frames[i] for i in indices]
        durations = [durations[i] for i in indices]

    # Processar cada frame
    converted_frames = []

    for i, frame in enumerate(frames):
        print(f"   Processando frame {i+1}/{len(frames)}...", end='\r')

        # Remover fundo ANTES do downscale (melhor qualidade)
        if remove_bg:
            frame = remove_background_and_replace(frame, bg_color)

        # Downscale adaptativo
        converted = adaptive_downscale(frame, target_size)

        # Melhorar contraste basico (opcional)
        if enhance and not led_optimize:
            converted = enhance_contrast(converted, factor=1.15)

        # Otimizacao para LED display (mais agressiva)
        if led_optimize:
            converted = enhance_for_led_display(converted, contrast=1.4, saturation=1.3, sharpness=1.5)

        # Escurecer fundo para destacar figura clara
        if darken_bg:
            converted = darken_background(converted, threshold=140, darken_factor=0.55)

        # Destacar centro da imagem
        if focus_center:
            converted = focus_on_center(converted, vignette_strength=0.25)

        # Quantizar cores (opcional)
        if num_colors > 0:
            converted = quantize_colors(converted, num_colors)

        converted_frames.append(converted)

    print(f"\n   {len(converted_frames)} frames processados")

    # Salvar GIF
    print(f"Salvando: {output_path.name}")

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

    print(f"Conversao completa!")
    print(f"   Tamanho: {output_path.stat().st_size / 1024:.1f} KB")


def create_preview(input_path: Path, output_path: Path, scale: int = 8) -> None:
    """Cria versao ampliada para inspecao visual."""
    frames, durations = load_gif_frames(input_path)

    scaled_frames = []
    for frame in frames:
        w, h = frame.size
        scaled = frame.resize((w * scale, h * scale), Image.Resampling.NEAREST)
        scaled_frames.append(np.array(scaled.convert('RGB')))

    avg_duration = sum(durations) / len(durations)
    fps = 1000 / avg_duration if avg_duration > 0 else 10

    iio.imwrite(output_path, scaled_frames, fps=fps, loop=0)
    print(f"Preview criado: {output_path.name} ({scale}x)")


def main():
    # Paths
    base_dir = Path(__file__).parent
    input_dir = base_dir / "Originais"
    output_dir = base_dir / "Processados"

    output_dir.mkdir(exist_ok=True)

    # Arquivo a processar (pode ser alterado)
    test_name = "Jamiroquai"
    test_file = input_dir / f"{test_name}.gif"

    if not test_file.exists():
        print(f"Arquivo nao encontrado: {test_file}")
        sys.exit(1)

    # Converter com otimizacao LED + foco central (versao que funcionou bem)
    output_file = output_dir / f"{test_name}_adaptive.gif"
    convert_gif(test_file, output_file, led_optimize=True, focus_center=True)

    # Criar preview ampliado
    preview_file = output_dir / f"{test_name}_adaptive_preview.gif"
    create_preview(output_file, preview_file, scale=8)

    print("\nPronto! Compare os arquivos:")
    print(f"   Original:   {test_file}")
    print(f"   Convertido: {output_file}")
    print(f"   Preview:    {preview_file}")


if __name__ == "__main__":
    main()
