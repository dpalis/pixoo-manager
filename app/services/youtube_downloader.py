"""
Servico de download de videos do YouTube.

Usa yt-dlp Python API para baixar trechos de video e converter para GIF.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.config import MAX_VIDEO_DURATION, MAX_SHORTS_DURATION, TEMP_DIR
from app.services.exceptions import ConversionError, VideoTooLongError, ValidationError
from app.services.video_converter import convert_video_to_gif
from app.services.gif_converter import ConvertOptions
from app.services.validators import (
    validate_youtube_url as _validate_youtube_url,
    sanitize_time_value,
    is_youtube_shorts,
)

# Importar yt_dlp uma vez no modulo (evita reimportar a cada chamada)
try:
    import yt_dlp
    _YTDLP_AVAILABLE = True
except ImportError:
    _YTDLP_AVAILABLE = False


def _check_ytdlp():
    """Verifica se yt_dlp esta disponivel."""
    if not _YTDLP_AVAILABLE:
        raise ConversionError("yt-dlp nao encontrado. Instale com: pip install yt-dlp")


@dataclass
class YouTubeInfo:
    """Informacoes de um video do YouTube."""
    id: str
    title: str
    duration: float  # segundos
    thumbnail: str
    channel: str
    width: int = 0
    height: int = 0


def validate_youtube_url(url: str) -> str:
    """
    Valida e extrai o ID do video do YouTube.

    Usa validacao rigorosa para prevenir command injection.

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

    Usa yt_dlp Python API diretamente (mais rapido que subprocess).

    Args:
        url: URL do YouTube

    Returns:
        YouTubeInfo com metadados do video

    Raises:
        ConversionError: Se nao conseguir obter info
    """
    _check_ytdlp()
    video_id = validate_youtube_url(url)

    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'noplaylist': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(
                f"https://www.youtube.com/watch?v={video_id}",
                download=False
            )

        if not info:
            raise ConversionError("Nao foi possivel obter informacoes do video")

        return YouTubeInfo(
            id=video_id,
            title=info.get("title", "Sem titulo"),
            duration=float(info.get("duration", 0)),
            thumbnail=info.get("thumbnail", ""),
            channel=info.get("channel", info.get("uploader", "")),
            width=info.get("width", 0) or 0,
            height=info.get("height", 0) or 0
        )

    except yt_dlp.DownloadError as e:
        raise ConversionError(f"Erro ao obter info do video: {e}")
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

    Usa yt_dlp Python API com download_ranges para baixar apenas o trecho.

    Args:
        url: URL do YouTube
        start: Tempo inicial em segundos
        end: Tempo final em segundos
        progress_callback: Callback para progresso

    Returns:
        Caminho do arquivo baixado

    Raises:
        VideoTooLongError: Se o trecho for maior que o limite permitido
        ConversionError: Se o download falhar
    """
    _check_ytdlp()

    # Sanitiza valores de tempo
    try:
        start = sanitize_time_value(start, max_duration=36000.0)  # Max 10h
        end = sanitize_time_value(end, max_duration=36000.0)
    except ValidationError as e:
        raise ConversionError(str(e))

    duration = end - start

    # Validar duracao baseado no tipo de video
    shorts = is_youtube_shorts(url)
    max_duration = MAX_SHORTS_DURATION if shorts else MAX_VIDEO_DURATION
    rounded_duration = round(duration, 1)
    if rounded_duration > max_duration:
        raise VideoTooLongError(
            f"Trecho de {duration:.1f}s excede o limite de {max_duration}s"
        )

    if duration <= 0:
        raise ConversionError("Tempo final deve ser maior que o inicial")

    video_id = validate_youtube_url(url)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    # Baixar video e cortar com moviepy
    # (yt_dlp Python API é rapida, download_ranges tem API instavel)
    return _download_and_trim(video_id, start, end, progress_callback)


def _download_and_trim(
    video_id: str,
    start: float,
    end: float,
    progress_callback: Optional[callable] = None
) -> Path:
    """
    Baixa video e corta o trecho com moviepy.

    Usa yt_dlp Python API (rapido) + moviepy para corte.
    """
    full_video_path = TEMP_DIR / f"yt_{video_id}_full.mp4"
    output_path = TEMP_DIR / f"yt_{video_id}_{start:.0f}_{end:.0f}.mp4"

    try:
        if progress_callback:
            progress_callback("downloading", 0)

        # Progress hook para yt-dlp
        def progress_hook(d):
            if progress_callback and d.get('status') == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                downloaded = d.get('downloaded_bytes', 0)
                if total > 0:
                    pct = (downloaded / total) * 80  # 80% para download
                    progress_callback("downloading", pct)

        ydl_opts = {
            'format': 'best[ext=mp4][height<=720]/best[ext=mp4]/best',
            'outtmpl': str(full_video_path),
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'progress_hooks': [progress_hook],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

        # Verificar se arquivo existe
        if not full_video_path.exists():
            possible_files = list(TEMP_DIR.glob(f"yt_{video_id}_full.*"))
            if possible_files:
                full_video_path = possible_files[0]
            else:
                raise ConversionError("Arquivo de video nao foi criado")

        if progress_callback:
            progress_callback("downloading", 85)

        # Cortar o trecho desejado usando moviepy
        from moviepy import VideoFileClip
        with VideoFileClip(str(full_video_path)) as clip:
            actual_end = min(end, clip.duration)
            trimmed = clip.subclipped(start, actual_end)
            trimmed.write_videofile(
                str(output_path),
                codec="libx264",
                audio_codec="aac",
                logger=None
            )

        if progress_callback:
            progress_callback("downloading", 100)

        return output_path

    except yt_dlp.DownloadError as e:
        raise ConversionError(f"Erro no download: {e}")
    except Exception as e:
        raise ConversionError(f"Erro no download: {e}")
    finally:
        # Limpar video completo
        if full_video_path.exists():
            full_video_path.unlink()


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
