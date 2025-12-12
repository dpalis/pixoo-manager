"""
Fixtures compartilhadas para testes do Pixoo Manager.
"""

import pytest
from pathlib import Path
from PIL import Image
import tempfile
import shutil

from fastapi.testclient import TestClient

from app.main import app
from app.services.pixoo_connection import PixooConnection


# ============================================
# Diretorio de fixtures
# ============================================
FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ============================================
# Client FastAPI
# ============================================
@pytest.fixture
def client():
    """Cliente de teste para FastAPI."""
    return TestClient(app)


# ============================================
# Diretorio temporario
# ============================================
@pytest.fixture
def temp_dir():
    """Cria diretorio temporario que e limpo apos o teste."""
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    shutil.rmtree(tmp)


# ============================================
# Imagens de teste
# ============================================
@pytest.fixture
def sample_64x64_gif(temp_dir):
    """Cria um GIF 64x64 de teste."""
    path = temp_dir / "sample_64x64.gif"

    # Criar 3 frames de cores diferentes
    frames = []
    for color in [(255, 0, 0), (0, 255, 0), (0, 0, 255)]:
        frame = Image.new("RGB", (64, 64), color)
        frames.append(frame)

    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        duration=100,
        loop=0
    )
    return path


@pytest.fixture
def sample_large_gif(temp_dir):
    """Cria um GIF 256x256 que precisa de conversao."""
    path = temp_dir / "sample_large.gif"

    frames = []
    for color in [(255, 128, 0), (128, 0, 255)]:
        frame = Image.new("RGB", (256, 256), color)
        frames.append(frame)

    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        duration=200,
        loop=0
    )
    return path


@pytest.fixture
def sample_png(temp_dir):
    """Cria uma imagem PNG 128x128 de teste."""
    path = temp_dir / "sample.png"

    # Criar imagem com gradiente
    img = Image.new("RGB", (128, 128))
    pixels = img.load()
    for x in range(128):
        for y in range(128):
            pixels[x, y] = (x * 2, y * 2, 128)

    img.save(path)
    return path


@pytest.fixture
def sample_jpeg(temp_dir):
    """Cria uma imagem JPEG de teste."""
    path = temp_dir / "sample.jpg"

    img = Image.new("RGB", (200, 150), (100, 150, 200))
    img.save(path, "JPEG")
    return path


# ============================================
# Mock do Pixoo Connection
# ============================================
@pytest.fixture
def mock_pixoo_connection(monkeypatch):
    """Mock do PixooConnection para testes sem dispositivo real."""
    class MockConnection:
        def __init__(self):
            self._connected = False
            self._ip = None
            self.commands_sent = []

        @property
        def is_connected(self):
            return self._connected

        @property
        def current_ip(self):
            return self._ip if self._connected else None

        def discover(self, timeout=3.0):
            return ["192.168.1.100"]

        def connect(self, ip):
            self._connected = True
            self._ip = ip
            return True

        def disconnect(self):
            self._connected = False
            self._ip = None

        def send_command(self, command):
            if not self._connected:
                from app.services.exceptions import PixooConnectionError
                raise PixooConnectionError("Nao conectado")
            self.commands_sent.append(command)
            return {"error_code": 0}

        def get_status(self):
            return {
                "connected": self._connected,
                "ip": self._ip if self._connected else None
            }

    mock = MockConnection()

    # Substituir a instancia global
    monkeypatch.setattr(
        "app.services.pixoo_connection.PixooConnection._instance",
        None
    )

    def mock_get_connection():
        return mock

    monkeypatch.setattr(
        "app.services.pixoo_connection.get_pixoo_connection",
        mock_get_connection
    )

    return mock


# ============================================
# Reset do singleton entre testes
# ============================================
@pytest.fixture(autouse=True)
def reset_pixoo_singleton():
    """Reseta o singleton do PixooConnection entre testes."""
    yield
    PixooConnection._instance = None
