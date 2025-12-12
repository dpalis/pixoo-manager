"""
Testes do servico de download do YouTube.

Usa mocks para evitar chamadas reais ao YouTube.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import subprocess
import json

from app.services.youtube_downloader import (
    YouTubeInfo,
    validate_youtube_url,
    get_youtube_info,
    download_youtube_segment,
    download_and_convert_youtube,
)
from app.services.exceptions import ConversionError, VideoTooLongError
from app.config import MAX_VIDEO_DURATION


class TestYouTubeInfo:
    """Testes para YouTubeInfo dataclass."""

    def test_creates_info(self):
        """Deve criar info corretamente."""
        info = YouTubeInfo(
            id="dQw4w9WgXcQ",
            title="Test Video",
            duration=180.0,
            thumbnail="https://img.youtube.com/vi/dQw4w9WgXcQ/0.jpg",
            channel="Test Channel"
        )

        assert info.id == "dQw4w9WgXcQ"
        assert info.title == "Test Video"
        assert info.duration == 180.0
        assert info.thumbnail == "https://img.youtube.com/vi/dQw4w9WgXcQ/0.jpg"
        assert info.channel == "Test Channel"


class TestValidateYoutubeUrl:
    """Testes para validate_youtube_url()."""

    def test_validates_standard_url(self):
        """Deve validar URL padrao do YouTube."""
        result = validate_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert result == "dQw4w9WgXcQ"

    def test_validates_short_url(self):
        """Deve validar URL curta youtu.be."""
        result = validate_youtube_url("https://youtu.be/dQw4w9WgXcQ")
        assert result == "dQw4w9WgXcQ"

    def test_validates_url_with_timestamp(self):
        """Deve validar URL com timestamp."""
        result = validate_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42")
        assert result == "dQw4w9WgXcQ"

    def test_validates_url_with_playlist(self):
        """Deve validar URL com playlist."""
        result = validate_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf")
        assert result == "dQw4w9WgXcQ"

    def test_rejects_invalid_url(self):
        """Deve rejeitar URL invalida."""
        with pytest.raises(ConversionError) as exc_info:
            validate_youtube_url("https://vimeo.com/12345")

        assert "URL" in str(exc_info.value) or "invalida" in str(exc_info.value).lower()

    def test_rejects_malformed_url(self):
        """Deve rejeitar URL malformada."""
        with pytest.raises(ConversionError):
            validate_youtube_url("not-a-url")

    def test_rejects_empty_url(self):
        """Deve rejeitar URL vazia."""
        with pytest.raises(ConversionError):
            validate_youtube_url("")


class TestGetYoutubeInfo:
    """Testes para get_youtube_info()."""

    @patch("subprocess.run")
    def test_returns_info_for_valid_video(self, mock_run):
        """Deve retornar info para video valido."""
        # Mock da resposta do yt-dlp
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({
                "title": "Test Video",
                "duration": 180,
                "thumbnail": "https://example.com/thumb.jpg",
                "channel": "Test Channel"
            })
        )

        info = get_youtube_info("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

        assert info.id == "dQw4w9WgXcQ"
        assert info.title == "Test Video"
        assert info.duration == 180.0
        assert info.thumbnail == "https://example.com/thumb.jpg"
        assert info.channel == "Test Channel"

    @patch("subprocess.run")
    def test_raises_for_yt_dlp_error(self, mock_run):
        """Deve lancar erro quando yt-dlp falha."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="Video unavailable"
        )

        with pytest.raises(ConversionError) as exc_info:
            get_youtube_info("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

        assert "Erro" in str(exc_info.value)

    @patch("subprocess.run")
    def test_raises_for_timeout(self, mock_run):
        """Deve lancar erro em timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="yt-dlp", timeout=30)

        with pytest.raises(ConversionError) as exc_info:
            get_youtube_info("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

        assert "Timeout" in str(exc_info.value)

    @patch("subprocess.run")
    def test_raises_for_missing_yt_dlp(self, mock_run):
        """Deve lancar erro quando yt-dlp nao existe."""
        mock_run.side_effect = FileNotFoundError()

        with pytest.raises(ConversionError) as exc_info:
            get_youtube_info("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

        assert "yt-dlp" in str(exc_info.value)


class TestDownloadYoutubeSegment:
    """Testes para download_youtube_segment()."""

    def test_raises_for_too_long_segment(self):
        """Deve lancar erro para segmento muito longo."""
        with pytest.raises(VideoTooLongError) as exc_info:
            download_youtube_segment(
                "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                start=0,
                end=MAX_VIDEO_DURATION + 5
            )

        assert "excede" in str(exc_info.value)

    def test_raises_for_invalid_time_range(self):
        """Deve lancar erro para intervalo invalido."""
        with pytest.raises(ConversionError) as exc_info:
            download_youtube_segment(
                "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                start=10,
                end=5
            )

        assert "deve ser maior" in str(exc_info.value)

    def test_raises_for_negative_time(self):
        """Deve lancar erro para tempo negativo."""
        with pytest.raises(ConversionError):
            download_youtube_segment(
                "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                start=-5,
                end=5
            )

    @patch("subprocess.run")
    def test_raises_for_download_timeout(self, mock_run):
        """Deve lancar erro em timeout de download."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="yt-dlp", timeout=120)

        with pytest.raises(ConversionError) as exc_info:
            download_youtube_segment(
                "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                start=0,
                end=5
            )

        assert "Timeout" in str(exc_info.value)

    @patch("subprocess.run")
    def test_raises_for_missing_yt_dlp(self, mock_run):
        """Deve lancar erro quando yt-dlp nao existe."""
        mock_run.side_effect = FileNotFoundError()

        with pytest.raises(ConversionError) as exc_info:
            download_youtube_segment(
                "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                start=0,
                end=5
            )

        assert "yt-dlp" in str(exc_info.value)


class TestDownloadAndConvertYoutube:
    """Testes para download_and_convert_youtube()."""

    def test_raises_for_too_long_segment(self):
        """Deve lancar erro para segmento muito longo."""
        with pytest.raises(VideoTooLongError):
            download_and_convert_youtube(
                "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                start=0,
                end=MAX_VIDEO_DURATION + 5
            )

    def test_raises_for_invalid_time_range(self):
        """Deve lancar erro para intervalo invalido."""
        with pytest.raises(ConversionError):
            download_and_convert_youtube(
                "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                start=20,
                end=10
            )

    @patch("app.services.youtube_downloader.download_youtube_segment")
    @patch("app.services.youtube_downloader.convert_video_to_gif")
    @patch("moviepy.VideoFileClip")
    def test_calls_download_and_convert(self, mock_clip_class, mock_convert, mock_download, temp_dir):
        """Deve chamar download e conversao."""
        # Setup mocks
        video_path = temp_dir / "test_video.mp4"
        video_path.touch()
        mock_download.return_value = video_path

        gif_path = temp_dir / "test.gif"
        mock_convert.return_value = (gif_path, 30)

        # Mock VideoFileClip
        mock_clip_instance = MagicMock()
        mock_clip_instance.__enter__ = MagicMock(return_value=mock_clip_instance)
        mock_clip_instance.__exit__ = MagicMock(return_value=False)
        mock_clip_instance.duration = 5.0
        mock_clip_class.return_value = mock_clip_instance

        result_path, frame_count = download_and_convert_youtube(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            start=0,
            end=5
        )

        mock_download.assert_called_once()
        mock_convert.assert_called_once()
        assert frame_count == 30

    @patch("app.services.youtube_downloader.download_youtube_segment")
    def test_cleans_up_video_after_conversion(self, mock_download, temp_dir):
        """Deve limpar video apos conversao."""
        # Criar arquivo de video temporario
        video_path = temp_dir / "test_video.mp4"

        # Criar video de teste real
        from moviepy import ColorClip
        clip = ColorClip(size=(64, 64), color=(255, 0, 0), duration=2)
        clip = clip.with_fps(10)
        clip.write_videofile(str(video_path), codec="libx264", audio=False, logger=None)
        clip.close()

        mock_download.return_value = video_path

        # Executar
        gif_path, _ = download_and_convert_youtube(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            start=0,
            end=2
        )

        # Verificar que o video foi removido
        assert not video_path.exists()
        assert gif_path.exists()
