"""
Testes do servico de utilitarios de arquivo.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
from io import BytesIO

from app.services.file_utils import (
    sanitize_filename,
    validate_magic_bytes,
    get_extension_for_type,
    ensure_temp_dir,
    create_temp_output,
    FileTracker,
    file_tracker,
    cleanup_files,
    GIF_MAGIC_BYTES,
    PNG_MAGIC_BYTES,
    JPEG_MAGIC_BYTES,
)
from app.config import TEMP_DIR


class TestSanitizeFilename:
    """Testes para sanitize_filename()."""

    def test_removes_path_components(self):
        """Deve remover componentes de caminho."""
        assert sanitize_filename("../../../etc/passwd") == "passwd"
        assert sanitize_filename("/etc/hosts") == "hosts"
        assert sanitize_filename("foo/bar/baz.txt") == "baz"

    def test_removes_extension(self):
        """Deve remover extensao do arquivo."""
        assert sanitize_filename("arquivo.gif") == "arquivo"
        assert sanitize_filename("video.mp4") == "video"

    def test_removes_special_characters(self):
        """Deve remover caracteres especiais."""
        assert sanitize_filename("file<>:\"|?*.txt") == "file"
        assert sanitize_filename("test;rm -rf /") == "testrm -rf"

    def test_handles_empty_string(self):
        """Deve retornar padrao para string vazia."""
        assert sanitize_filename("") == "arquivo"
        assert sanitize_filename("   ") == "arquivo"

    def test_preserves_unicode_letters(self):
        """Deve preservar letras unicode."""
        assert sanitize_filename("açúcar.gif") == "açúcar"
        assert sanitize_filename("日本語.png") == "日本語"

    def test_limits_length(self):
        """Deve limitar tamanho do nome."""
        long_name = "a" * 200 + ".gif"
        result = sanitize_filename(long_name)
        assert len(result) <= 100


class TestValidateMagicBytes:
    """Testes para validate_magic_bytes()."""

    def test_validates_gif_magic_bytes(self):
        """Deve validar magic bytes de GIF."""
        gif_data = b"GIF89a" + b"\x00" * 10
        assert validate_magic_bytes(gif_data, "image/gif") is True

        gif87_data = b"GIF87a" + b"\x00" * 10
        assert validate_magic_bytes(gif87_data, "image/gif") is True

    def test_validates_png_magic_bytes(self):
        """Deve validar magic bytes de PNG."""
        png_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 10
        assert validate_magic_bytes(png_data, "image/png") is True

    def test_validates_jpeg_magic_bytes(self):
        """Deve validar magic bytes de JPEG."""
        jpeg_data = b"\xff\xd8\xff" + b"\x00" * 10
        assert validate_magic_bytes(jpeg_data, "image/jpeg") is True
        assert validate_magic_bytes(jpeg_data, "image/jpg") is True

    def test_validates_mp4_magic_bytes(self):
        """Deve validar magic bytes de MP4."""
        mp4_data = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 10
        assert validate_magic_bytes(mp4_data, "video/mp4") is True

    def test_validates_webm_magic_bytes(self):
        """Deve validar magic bytes de WebM."""
        webm_data = b"\x1a\x45\xdf\xa3" + b"\x00" * 10
        assert validate_magic_bytes(webm_data, "video/webm") is True

    def test_rejects_mismatched_type(self):
        """Deve rejeitar tipo que nao corresponde."""
        gif_data = b"GIF89a" + b"\x00" * 10
        assert validate_magic_bytes(gif_data, "image/png") is False

        png_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 10
        assert validate_magic_bytes(png_data, "image/gif") is False

    def test_rejects_insufficient_data(self):
        """Deve rejeitar dados insuficientes."""
        assert validate_magic_bytes(b"GIF", "image/gif") is False
        assert validate_magic_bytes(b"", "image/gif") is False

    def test_rejects_unknown_type(self):
        """Deve rejeitar tipos desconhecidos."""
        data = b"\x00" * 20
        assert validate_magic_bytes(data, "application/octet-stream") is False


class TestGetExtensionForType:
    """Testes para get_extension_for_type()."""

    def test_returns_gif_extension(self):
        """Deve retornar .gif para image/gif."""
        assert get_extension_for_type("image/gif") == ".gif"

    def test_returns_png_extension(self):
        """Deve retornar .png para image/png."""
        assert get_extension_for_type("image/png") == ".png"

    def test_returns_jpg_extension(self):
        """Deve retornar .jpg para image/jpeg."""
        assert get_extension_for_type("image/jpeg") == ".jpg"
        assert get_extension_for_type("image/jpg") == ".jpg"

    def test_returns_mp4_extension(self):
        """Deve retornar .mp4 para video/mp4."""
        assert get_extension_for_type("video/mp4") == ".mp4"

    def test_returns_webm_extension(self):
        """Deve retornar .webm para video/webm."""
        assert get_extension_for_type("video/webm") == ".webm"

    def test_returns_mov_extension(self):
        """Deve retornar .mov para video/quicktime."""
        assert get_extension_for_type("video/quicktime") == ".mov"

    def test_returns_empty_for_unknown(self):
        """Deve retornar vazio para tipo desconhecido."""
        assert get_extension_for_type("application/pdf") == ""
        assert get_extension_for_type("unknown/type") == ""


class TestEnsureTempDir:
    """Testes para ensure_temp_dir()."""

    def test_creates_directory_if_not_exists(self, temp_dir, monkeypatch):
        """Deve criar diretorio se nao existir."""
        test_dir = temp_dir / "test_temp"
        monkeypatch.setattr("app.services.file_utils.TEMP_DIR", test_dir)

        assert not test_dir.exists()
        result = ensure_temp_dir()
        assert test_dir.exists()
        assert result == test_dir

    def test_returns_existing_directory(self, temp_dir, monkeypatch):
        """Deve retornar diretorio existente."""
        monkeypatch.setattr("app.services.file_utils.TEMP_DIR", temp_dir)

        result = ensure_temp_dir()
        assert result == temp_dir


class TestCreateTempOutput:
    """Testes para create_temp_output()."""

    def test_creates_temp_file_with_suffix(self, monkeypatch, temp_dir):
        """Deve criar arquivo temporario com sufixo."""
        monkeypatch.setattr("app.services.file_utils.TEMP_DIR", temp_dir)

        path = create_temp_output(".gif")
        assert path.suffix == ".gif"
        assert path.parent == temp_dir

    def test_creates_unique_files(self, monkeypatch, temp_dir):
        """Deve criar arquivos unicos."""
        monkeypatch.setattr("app.services.file_utils.TEMP_DIR", temp_dir)

        path1 = create_temp_output(".gif")
        path2 = create_temp_output(".gif")
        assert path1 != path2


class TestFileTracker:
    """Testes para FileTracker."""

    def test_acquire_increments_reference(self):
        """Deve incrementar referencia ao adquirir."""
        tracker = FileTracker()
        path = Path("/tmp/test.gif")

        tracker.acquire(path)
        assert tracker.is_in_use(path) is True

        tracker.acquire(path)
        # Ainda em uso apos segunda aquisicao
        assert tracker.is_in_use(path) is True

    def test_release_decrements_reference(self):
        """Deve decrementar referencia ao liberar."""
        tracker = FileTracker()
        path = Path("/tmp/test.gif")

        tracker.acquire(path)
        tracker.acquire(path)

        result = tracker.release(path)
        assert result is False  # Ainda tem 1 referencia
        assert tracker.is_in_use(path) is True

        result = tracker.release(path)
        assert result is True  # Zerou referencias
        assert tracker.is_in_use(path) is False

    def test_release_unknown_path(self):
        """Deve retornar True para caminho desconhecido."""
        tracker = FileTracker()
        path = Path("/tmp/unknown.gif")

        result = tracker.release(path)
        assert result is True

    def test_is_in_use_returns_false_for_unknown(self):
        """Deve retornar False para caminho desconhecido."""
        tracker = FileTracker()
        path = Path("/tmp/unknown.gif")

        assert tracker.is_in_use(path) is False

    def test_get_stale_files(self, monkeypatch):
        """Deve retornar arquivos expirados."""
        tracker = FileTracker()
        path = Path("/tmp/test.gif")

        # Simular arquivo adicionado no passado
        tracker._refs[path] = 0
        tracker._timestamps[path] = 0  # Muito antigo

        stale = tracker.get_stale_files(ttl=1)
        assert path in stale

    def test_get_stale_files_excludes_in_use(self, monkeypatch):
        """Deve excluir arquivos em uso."""
        tracker = FileTracker()
        path = Path("/tmp/test.gif")

        tracker.acquire(path)
        # Forcar timestamp antigo
        tracker._timestamps[path] = 0

        stale = tracker.get_stale_files(ttl=1)
        assert path not in stale


class TestCleanupFiles:
    """Testes para cleanup_files()."""

    def test_removes_existing_files(self, temp_dir):
        """Deve remover arquivos existentes."""
        file1 = temp_dir / "test1.gif"
        file2 = temp_dir / "test2.gif"
        file1.touch()
        file2.touch()

        assert file1.exists()
        assert file2.exists()

        cleanup_files([file1, file2])

        assert not file1.exists()
        assert not file2.exists()

    def test_ignores_nonexistent_files(self, temp_dir):
        """Deve ignorar arquivos inexistentes."""
        file = temp_dir / "nonexistent.gif"

        # Nao deve lancar excecao
        cleanup_files([file])

    def test_ignores_none_paths(self):
        """Deve ignorar caminhos None."""
        # Nao deve lancar excecao
        cleanup_files([None, None])

    def test_skips_files_in_use(self, temp_dir):
        """Deve pular arquivos em uso."""
        file = temp_dir / "in_use.gif"
        file.touch()

        file_tracker.acquire(file)
        try:
            cleanup_files([file])
            assert file.exists()  # Nao deve ter sido removido
        finally:
            file_tracker.release(file)
