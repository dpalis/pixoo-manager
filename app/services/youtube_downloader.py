"""
Servico de download de videos do YouTube.

Usa yt-dlp para baixar trechos de video e converter para GIF.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.config import MAX_VIDEO_DURATION, TEMP_DIR
from app.services.exceptions import ConversionError, VideoTooLongError, ValidationError
from app.services.video_converter import convert_video_to_gif
from app.services.gif_converter import ConvertOptions
from app.services.validators import (
    validate_youtube_url as _validate_youtube_url,
    sanitize_time_value,
)


@dataclass
class YouTubeInfo:
    """Informacoes de um video do YouTube."""
    id: str
    title: str
    duration: float  # segundos
    thumbnail: str
    channel: str


def validate_youtube_url(url: str) -> str:
    """
    Valida e extrai o ID do video do YouTube.

    Usa validação rigorosa para prevenir command injection.

    Args:
        url: URL do YouTube

    Returns:
        ID do video (11 caracteres)

    Raises:
        ConversionError: Se URL invalida
    """
    try:
        return _validate_youtube_url(url)
    except ValidationError as e:
        raise ConversionError(str(e))


def get_youtube_info(url: str) -> YouTubeInfo:
    """
    Obtem informacoes do video sem baixar.

    Args:
        url: URL do YouTube

    Returns:
        YouTubeInfo com metadados do video

    Raises:
        ConversionError: Se nao conseguir obter info
    """
    video_id = validate_youtube_url(url)

    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "--dump-json",
                "--no-download",
                "--no-warnings",
                f"https://www.youtube.com/watch?v={video_id}"
            ],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            raise ConversionError(f"Erro ao obter info do video: {result.stderr}")

        import json
        info = json.loads(result.stdout)

        return YouTubeInfo(
            id=video_id,
            title=info.get("title", "Sem titulo"),
            duration=float(info.get("duration", 0)),
            thumbnail=info.get("thumbnail", ""),
            channel=info.get("channel", info.get("uploader", ""))
        )

    except subprocess.TimeoutExpired:
        raise ConversionError("Timeout ao obter info do video")
    except json.JSONDecodeError:
        raise ConversionError("Erro ao processar resposta do yt-dlp")
    except FileNotFoundError:
        raise ConversionError("yt-dlp nao encontrado. Instale com: pip install yt-dlp")
    except Exception as e:
        raise ConversionError(f"Erro ao obter info: {e}")


def download_youtube_segment(
    url: str,
    start: float,
    end: float,
    progress_callback: Optional[callable] = None
) -> Path:
    """
    Baixa um trecho do video do YouTube.

    Args:
        url: URL do YouTube
        start: Tempo inicial em segundos
        end: Tempo final em segundos
        progress_callback: Callback para progresso

    Returns:
        Caminho do arquivo baixado

    Raises:
        VideoTooLongError: Se o trecho for maior que MAX_VIDEO_DURATION
        ConversionError: Se o download falhar
    """
    # Sanitiza valores de tempo para prevenir command injection
    try:
        start = sanitize_time_value(start, max_duration=36000.0)  # Max 10h
        end = sanitize_time_value(end, max_duration=36000.0)
    except ValidationError as e:
        raise ConversionError(str(e))

    duration = end - start

    if duration > MAX_VIDEO_DURATION:
        raise VideoTooLongError(
            f"Trecho de {duration:.1f}s excede o limite de {MAX_VIDEO_DURATION}s"
        )

    if duration <= 0:
        raise ConversionError("Tempo final deve ser maior que o inicial")

    video_id = validate_youtube_url(url)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    output_path = TEMP_DIR / f"yt_{video_id}_{start:.0f}_{end:.0f}.mp4"

    # Formatar tempos para yt-dlp
    def format_time(seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = seconds % 60
        return f"{h:02d}:{m:02d}:{s:06.3f}"

    try:
        if progress_callback:
            progress_callback("downloading", 0)

        result = subprocess.run(
            [
                "yt-dlp",
                "-f", "bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "--download-sections", f"*{format_time(start)}-{format_time(end)}",
                "--force-keyframes-at-cuts",
                "-o", str(output_path),
                "--no-warnings",
                "--no-playlist",
                f"https://www.youtube.com/watch?v={video_id}"
            ],
            capture_output=True,
            text=True,
            timeout=120
        )

        if progress_callback:
            progress_callback("downloading", 100)

        if result.returncode != 0:
            # Tentar metodo alternativo sem --download-sections
            # (para versoes mais antigas do yt-dlp)
            result = subprocess.run(
                [
                    "yt-dlp",
                    "-f", "best[ext=mp4]/best",
                    "-o", str(output_path),
                    "--no-warnings",
                    "--no-playlist",
                    f"https://www.youtube.com/watch?v={video_id}"
                ],
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode != 0:
                raise ConversionError(f"Erro no download: {result.stderr}")

        if not output_path.exists():
            # yt-dlp pode adicionar extensao diferente
            possible_files = list(TEMP_DIR.glob(f"yt_{video_id}_{start:.0f}_{end:.0f}.*"))
            if possible_files:
                output_path = possible_files[0]
            else:
                raise ConversionError("Arquivo de video nao foi criado")

        return output_path

    except subprocess.TimeoutExpired:
        raise ConversionError("Timeout no download do video")
    except FileNotFoundError:
        raise ConversionError("yt-dlp nao encontrado. Instale com: pip install yt-dlp")
    except ConversionError:
        raise
    except Exception as e:
        raise ConversionError(f"Erro no download: {e}")


def download_and_convert_youtube(
    url: str,
    start: float,
    end: float,
    options: Optional[ConvertOptions] = None,
    progress_callback: Optional[callable] = None
) -> tuple[Path, int]:
    """
    Baixa trecho do YouTube e converte para GIF 64x64.

    Args:
        url: URL do YouTube
        start: Tempo inicial em segundos
        end: Tempo final em segundos
        options: Opcoes de conversao
        progress_callback: Callback (fase, progresso)

    Returns:
        Tupla (caminho do GIF, numero de frames)
    """
    if options is None:
        options = ConvertOptions(led_optimize=True)

    def download_progress(phase, progress):
        if progress_callback:
            progress_callback(phase, progress * 0.4)  # 40% para download

    # Baixar video
    video_path = download_youtube_segment(url, start, end, download_progress)

    try:
        def convert_progress(phase, progress):
            if progress_callback:
                # 60% para conversao (40-100)
                progress_callback(phase, 40 + progress * 0.6)

        # Converter para GIF
        # O video ja esta cortado, entao converter do inicio ao fim
        from moviepy import VideoFileClip
        with VideoFileClip(str(video_path)) as clip:
            video_duration = clip.duration

        gif_path, frames = convert_video_to_gif(
            video_path,
            start=0,
            end=video_duration,
            options=options,
            progress_callback=convert_progress
        )

        return gif_path, frames

    finally:
        # Limpar video temporario
        if video_path.exists():
            video_path.unlink()
