"""
Testes do servico de upload para o Pixoo.
"""

import pytest
from PIL import Image
import base64

from app.services.pixoo_upload import (
    frame_to_base64,
    upload_gif,
    upload_single_frame,
)
from app.services.exceptions import (
    PixooConnectionError,
    TooManyFramesError,
)
from app.config import PIXOO_SIZE, MAX_UPLOAD_FRAMES


class TestFrameToBase64:
    """Testes para frame_to_base64()."""

    def test_returns_valid_base64(self):
        """Deve retornar string base64 valida."""
        frame = Image.new("RGB", (64, 64), (255, 0, 0))
        result = frame_to_base64(frame)

        # Deve ser decodificavel
        decoded = base64.b64decode(result)
        assert len(decoded) > 0

    def test_correct_data_size(self):
        """Dados devem ter tamanho correto (64*64*3 bytes)."""
        frame = Image.new("RGB", (64, 64), (0, 255, 0))
        result = frame_to_base64(frame)

        decoded = base64.b64decode(result)
        expected_size = PIXOO_SIZE * PIXOO_SIZE * 3  # RGB
        assert len(decoded) == expected_size

    def test_converts_rgba_to_rgb(self):
        """Deve converter RGBA para RGB."""
        frame = Image.new("RGBA", (64, 64), (0, 0, 255, 128))
        result = frame_to_base64(frame)

        decoded = base64.b64decode(result)
        expected_size = PIXOO_SIZE * PIXOO_SIZE * 3
        assert len(decoded) == expected_size

    def test_resizes_if_not_64x64(self):
        """Deve redimensionar se nao for 64x64."""
        frame = Image.new("RGB", (128, 128), (255, 255, 0))
        result = frame_to_base64(frame)

        decoded = base64.b64decode(result)
        expected_size = PIXOO_SIZE * PIXOO_SIZE * 3
        assert len(decoded) == expected_size

    def test_preserves_color_data(self):
        """Deve preservar dados de cor."""
        # Frame vermelho
        frame = Image.new("RGB", (64, 64), (255, 0, 0))
        result = frame_to_base64(frame)

        decoded = base64.b64decode(result)

        # Primeiro pixel deve ser vermelho (255, 0, 0)
        assert decoded[0] == 255  # R
        assert decoded[1] == 0    # G
        assert decoded[2] == 0    # B


class TestUploadGif:
    """Testes para upload_gif()."""

    def test_upload_requires_connection(self, sample_64x64_gif):
        """Deve exigir conexao ativa."""
        # Resetar singleton para garantir estado limpo
        from app.services.pixoo_connection import PixooConnection
        PixooConnection._instance = None

        with pytest.raises(PixooConnectionError) as exc:
            upload_gif(sample_64x64_gif)

        assert "conectado" in str(exc.value).lower()

    def test_upload_sends_all_frames(self, sample_64x64_gif, monkeypatch):
        """Deve enviar todos os frames do GIF."""
        from app.services import pixoo_upload
        from app.services.pixoo_connection import PixooConnection

        # Criar mock connection
        class MockConn:
            is_connected = True
            def send_command(self, cmd):
                return {"error_code": 0}

        mock = MockConn()
        monkeypatch.setattr(pixoo_upload, "get_pixoo_connection", lambda: mock)

        result = upload_gif(sample_64x64_gif)

        assert result["success"] is True
        assert result["frames_sent"] == 3  # sample_64x64_gif tem 3 frames

    def test_upload_respects_speed_parameter(self, sample_64x64_gif, monkeypatch):
        """Deve respeitar parametro de velocidade."""
        from app.services import pixoo_upload

        class MockConn:
            is_connected = True
            def send_command(self, cmd):
                return {"error_code": 0}

        monkeypatch.setattr(pixoo_upload, "get_pixoo_connection", lambda: MockConn())

        result = upload_gif(sample_64x64_gif, speed=200)

        assert result["speed_ms"] == 200

    def test_upload_uses_original_duration_if_no_speed(self, sample_64x64_gif, monkeypatch):
        """Deve usar duracao original se speed nao especificado."""
        from app.services import pixoo_upload

        class MockConn:
            is_connected = True
            def send_command(self, cmd):
                return {"error_code": 0}

        monkeypatch.setattr(pixoo_upload, "get_pixoo_connection", lambda: MockConn())

        result = upload_gif(sample_64x64_gif)

        # sample_64x64_gif foi criado com duration=100
        assert result["speed_ms"] >= 50  # Minimo e 50ms

    def test_upload_calls_progress_callback(self, sample_64x64_gif, monkeypatch):
        """Deve chamar callback de progresso."""
        from app.services import pixoo_upload

        class MockConn:
            is_connected = True
            def send_command(self, cmd):
                return {"error_code": 0}

        monkeypatch.setattr(pixoo_upload, "get_pixoo_connection", lambda: MockConn())

        progress_calls = []

        def callback(current, total):
            progress_calls.append((current, total))

        upload_gif(sample_64x64_gif, progress_callback=callback)

        assert len(progress_calls) == 3  # 3 frames
        assert progress_calls[0] == (1, 3)
        assert progress_calls[2] == (3, 3)


class TestUploadSingleFrame:
    """Testes para upload_single_frame()."""

    def test_upload_requires_connection(self):
        """Deve exigir conexao ativa."""
        from app.services.pixoo_connection import PixooConnection
        PixooConnection._instance = None

        frame = Image.new("RGB", (64, 64), (128, 128, 128))

        with pytest.raises(PixooConnectionError):
            upload_single_frame(frame)

    def test_upload_single_frame_success(self, monkeypatch):
        """Deve enviar frame unico com sucesso."""
        from app.services import pixoo_upload

        class MockConn:
            is_connected = True
            def send_command(self, cmd):
                return {"error_code": 0}

        monkeypatch.setattr(pixoo_upload, "get_pixoo_connection", lambda: MockConn())

        frame = Image.new("RGB", (64, 64), (0, 128, 255))
        result = upload_single_frame(frame)

        assert result["success"] is True
        assert result["frames_sent"] == 1
