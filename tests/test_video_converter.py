"""
Testes do servico de conversao de video.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
import numpy as np
from PIL import Image

from app.services.video_converter import (
    VideoMetadata,
    get_video_info,
    extract_video_segment,
    convert_video_to_gif,
)
from app.services.exceptions import ConversionError, VideoTooLongError
from app.config import MAX_VIDEO_DURATION, MAX_CONVERT_FRAMES, PIXOO_SIZE


class TestVideoMetadata:
    """Testes para VideoMetadata dataclass."""

    def test_creates_metadata(self, temp_dir):
        """Deve criar metadados corretamente."""
        path = temp_dir / "video.mp4"
        metadata = VideoMetadata(
            duration=10.5,
            width=1920,
            height=1080,
            fps=30.0,
            path=path
        )

        assert metadata.duration == 10.5
        assert metadata.width == 1920
        assert metadata.height == 1080
        assert metadata.fps == 30.0
        assert metadata.path == path


class TestGetVideoInfo:
    """Testes para get_video_info()."""

    def test_returns_metadata_for_valid_video(self, sample_video):
        """Deve retornar metadados para video valido."""
        metadata = get_video_info(sample_video)

        assert metadata.duration > 0
        assert metadata.width > 0
        assert metadata.height > 0
        assert metadata.fps > 0
        assert metadata.path == sample_video

    def test_raises_for_invalid_file(self, temp_dir):
        """Deve lancar erro para arquivo invalido."""
        invalid_file = temp_dir / "not_a_video.txt"
        invalid_file.write_text("not a video")

        with pytest.raises(ConversionError) as exc_info:
            get_video_info(invalid_file)

        assert "Erro ao ler video" in str(exc_info.value)

    def test_raises_for_nonexistent_file(self, temp_dir):
        """Deve lancar erro para arquivo inexistente."""
        nonexistent = temp_dir / "nonexistent.mp4"

        with pytest.raises(ConversionError):
            get_video_info(nonexistent)


class TestExtractVideoSegment:
    """Testes para extract_video_segment()."""

    def test_extracts_frames_from_segment(self, sample_video):
        """Deve extrair frames do segmento."""
        frames, durations = extract_video_segment(sample_video, start=0, end=1.0)

        assert len(frames) > 0
        assert len(durations) == len(frames)
        assert all(isinstance(f, Image.Image) for f in frames)
        assert all(d > 0 for d in durations)

    def test_raises_for_too_long_segment(self, sample_video):
        """Deve lancar erro para segmento muito longo."""
        with pytest.raises(VideoTooLongError) as exc_info:
            extract_video_segment(
                sample_video,
                start=0,
                end=MAX_VIDEO_DURATION + 5
            )

        assert "excede o limite" in str(exc_info.value)

    def test_raises_for_invalid_time_range(self, sample_video):
        """Deve lancar erro para intervalo invalido."""
        with pytest.raises(ConversionError) as exc_info:
            extract_video_segment(sample_video, start=5, end=2)

        assert "deve ser maior que" in str(exc_info.value)

    def test_calls_progress_callback(self, sample_video):
        """Deve chamar callback de progresso."""
        progress_values = []

        def callback(progress):
            progress_values.append(progress)

        frames, _ = extract_video_segment(
            sample_video,
            start=0,
            end=1.0,
            progress_callback=callback
        )

        assert len(progress_values) > 0
        assert progress_values[-1] == 1.0  # Ultimo deve ser 100%


class TestConvertVideoToGif:
    """Testes para convert_video_to_gif()."""

    def test_converts_video_to_gif(self, sample_video):
        """Deve converter video para GIF."""
        output_path, frame_count = convert_video_to_gif(
            sample_video,
            start=0,
            end=1.0
        )

        assert output_path.exists()
        assert output_path.suffix == ".gif"
        assert frame_count > 0

        # Verificar que o GIF e 64x64
        with Image.open(output_path) as img:
            assert img.size == (PIXOO_SIZE, PIXOO_SIZE)

    def test_respects_max_duration(self, sample_video):
        """Deve respeitar duracao maxima."""
        with pytest.raises(VideoTooLongError):
            convert_video_to_gif(
                sample_video,
                start=0,
                end=MAX_VIDEO_DURATION + 1
            )

    def test_respects_max_frames(self, sample_video):
        """Deve limitar numero de frames."""
        # Video de teste tem 3 segundos
        output_path, frame_count = convert_video_to_gif(
            sample_video,
            start=0,
            end=3.0
        )

        assert frame_count <= MAX_CONVERT_FRAMES

    def test_calls_progress_callback(self, sample_video):
        """Deve chamar callback de progresso."""
        phases_seen = set()

        def callback(phase, progress):
            phases_seen.add(phase)

        convert_video_to_gif(
            sample_video,
            start=0,
            end=1.0,
            progress_callback=callback
        )

        assert "processing" in phases_seen
        assert "saving" in phases_seen

    def test_uses_led_optimize_by_default(self, sample_video):
        """Deve usar otimizacao LED por padrao."""
        from app.services.gif_converter import ConvertOptions

        # Sem options explicitas
        output_path, _ = convert_video_to_gif(
            sample_video,
            start=0,
            end=1.0
        )

        assert output_path.exists()

    def test_accepts_custom_options(self, sample_video):
        """Deve aceitar opcoes customizadas."""
        from app.services.gif_converter import ConvertOptions

        options = ConvertOptions(led_optimize=False, num_colors=32)
        output_path, _ = convert_video_to_gif(
            sample_video,
            start=0,
            end=1.0,
            options=options
        )

        assert output_path.exists()


# ============================================
# Fixture para video de teste
# ============================================
@pytest.fixture
def sample_video(temp_dir):
    """
    Cria um video de teste usando moviepy.

    Gera um video simples com frames coloridos.
    """
    from moviepy import ColorClip

    output_path = temp_dir / "sample_video.mp4"

    # Criar clip de cor solida de 3 segundos
    clip = ColorClip(size=(128, 128), color=(255, 0, 0), duration=3)
    clip = clip.with_fps(10)

    clip.write_videofile(
        str(output_path),
        codec="libx264",
        audio=False,
        logger=None
    )
    clip.close()

    return output_path
