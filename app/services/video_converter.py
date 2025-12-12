"""
Servico de conversao de video para GIF.

Usa MoviePy para extrair trechos de video e converter para GIF 64x64.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Tuple

from moviepy import VideoFileClip
from PIL import Image

from app.config import (
    ALLOWED_VIDEO_TYPES,
    MAX_CONVERT_FRAMES,
    MAX_VIDEO_DURATION,
    PIXOO_SIZE,
    TEMP_DIR,
)
from app.services.exceptions import ConversionError, VideoTooLongError
from app.services.gif_converter import (
    ConvertOptions,
    adaptive_downscale,
    enhance_for_led_display,
    quantize_colors,
)


@dataclass
class VideoMetadata:
    """Metadados de um arquivo de video."""
    duration: float  # segundos
    width: int
    height: int
    fps: float
    path: Path


def get_video_info(path: Path) -> VideoMetadata:
    """
    Obtem metadados de um arquivo de video.

    Args:
        path: Caminho do arquivo de video

    Returns:
        VideoMetadata com informacoes do video

    Raises:
        ConversionError: Se o arquivo nao puder ser lido
    """
    try:
        with VideoFileClip(str(path)) as clip:
            return VideoMetadata(
                duration=clip.duration,
                width=clip.w,
                height=clip.h,
                fps=clip.fps,
                path=path
            )
    except Exception as e:
        raise ConversionError(f"Erro ao ler video: {e}")


def extract_video_segment(
    path: Path,
    start: float,
    end: float,
    progress_callback: Optional[Callable[[float], None]] = None
) -> Tuple[list[Image.Image], list[int]]:
    """
    Extrai um segmento de video como frames PIL.

    Args:
        path: Caminho do arquivo de video
        start: Tempo inicial em segundos
        end: Tempo final em segundos
        progress_callback: Callback para progresso (0.0 a 1.0)

    Returns:
        Tupla (lista de frames PIL, lista de duracoes em ms)

    Raises:
        VideoTooLongError: Se o segmento for maior que MAX_VIDEO_DURATION
        ConversionError: Se a conversao falhar
    """
    duration = end - start

    if duration > MAX_VIDEO_DURATION:
        raise VideoTooLongError(
            f"Segmento de {duration:.1f}s excede o limite de {MAX_VIDEO_DURATION}s"
        )

    if duration <= 0:
        raise ConversionError("Tempo final deve ser maior que o inicial")

    try:
        with VideoFileClip(str(path)) as clip:
            # Cortar o segmento
            segment = clip.subclipped(start, end)

            # Calcular fps para nao exceder MAX_CONVERT_FRAMES
            target_fps = min(segment.fps, MAX_CONVERT_FRAMES / duration)
            target_fps = max(target_fps, 5)  # Minimo 5 FPS

            frames = []
            total_frames = int(duration * target_fps)
            frame_duration = int(1000 / target_fps)  # ms entre frames

            for i, t in enumerate(range(total_frames)):
                if progress_callback:
                    progress_callback(i / total_frames)

                # Extrair frame no tempo especifico
                time = t / target_fps
                # Usar >= para evitar off-by-one no último frame
                if time >= duration:
                    break

                frame_array = segment.get_frame(time)

                # Converter array numpy para PIL
                frame = Image.fromarray(frame_array)
                frames.append(frame)

            # Duracoes uniformes
            durations = [frame_duration] * len(frames)

            if progress_callback:
                progress_callback(1.0)

            return frames, durations

    except VideoTooLongError:
        raise
    except Exception as e:
        raise ConversionError(f"Erro ao extrair frames: {e}")


def convert_video_to_gif(
    path: Path,
    start: float,
    end: float,
    options: Optional[ConvertOptions] = None,
    progress_callback: Optional[Callable[[str, float], None]] = None
) -> Tuple[Path, int]:
    """
    Converte um segmento de video para GIF 64x64.

    Args:
        path: Caminho do arquivo de video
        start: Tempo inicial em segundos
        end: Tempo final em segundos
        options: Opcoes de conversao (led_optimize, max_colors)
        progress_callback: Callback (fase, progresso) - fase: "extracting", "processing", "saving"

    Returns:
        Tupla (caminho do GIF gerado, numero de frames)

    Raises:
        VideoTooLongError: Se o segmento for maior que MAX_VIDEO_DURATION
        ConversionError: Se a conversao falhar
    """
    if options is None:
        options = ConvertOptions(led_optimize=True)

    def extraction_progress(p: float):
        if progress_callback:
            progress_callback("extracting", p)

    # Extrair frames do video
    frames, durations = extract_video_segment(
        path, start, end,
        progress_callback=extraction_progress
    )

    if not frames:
        raise ConversionError("Nenhum frame extraido do video")

    # Processar cada frame
    processed_frames = []
    total = len(frames)

    for i, frame in enumerate(frames):
        if progress_callback:
            progress_callback("processing", i / total)

        # Converter para 64x64
        processed = adaptive_downscale(frame, PIXOO_SIZE)

        # Otimizar para LED se solicitado
        if options.led_optimize:
            processed = enhance_for_led_display(processed)

        # Quantizar cores (usa num_colors, não max_colors)
        processed = quantize_colors(processed, options.num_colors)

        processed_frames.append(processed)

    if progress_callback:
        progress_callback("processing", 1.0)

    # Salvar como GIF
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    output_path = TEMP_DIR / f"video_{path.stem}_{start:.0f}_{end:.0f}.gif"

    if progress_callback:
        progress_callback("saving", 0.5)

    try:
        processed_frames[0].save(
            output_path,
            save_all=True,
            append_images=processed_frames[1:],
            duration=durations,
            loop=0,
            optimize=False
        )
    except Exception as e:
        raise ConversionError(f"Erro ao salvar GIF: {e}")

    if progress_callback:
        progress_callback("saving", 1.0)

    return output_path, len(processed_frames)
