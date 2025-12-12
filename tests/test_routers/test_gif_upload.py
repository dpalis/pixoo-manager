"""
Testes de integracao para router de GIF upload.
"""

import pytest
from io import BytesIO
from PIL import Image


class TestGifUploadEndpoint:
    """Testes para POST /api/gif/upload."""

    def test_uploads_valid_gif(self, client, sample_64x64_gif):
        """Deve fazer upload de GIF valido."""
        with open(sample_64x64_gif, "rb") as f:
            response = client.post(
                "/api/gif/upload",
                files={"file": ("test.gif", f, "image/gif")}
            )

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["width"] == 64
        assert data["height"] == 64
        assert data["frames"] > 0
        assert "preview_url" in data

    def test_converts_large_gif(self, client, sample_large_gif):
        """Deve converter GIF grande para 64x64."""
        with open(sample_large_gif, "rb") as f:
            response = client.post(
                "/api/gif/upload",
                files={"file": ("large.gif", f, "image/gif")}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["width"] == 64
        assert data["height"] == 64
        assert data["converted"] is True

    def test_rejects_invalid_content_type(self, client, temp_dir):
        """Deve rejeitar tipo de conteudo invalido."""
        # Criar arquivo texto fake
        text_file = temp_dir / "test.txt"
        text_file.write_text("not an image")

        with open(text_file, "rb") as f:
            response = client.post(
                "/api/gif/upload",
                files={"file": ("test.txt", f, "text/plain")}
            )

        assert response.status_code == 400

    def test_rejects_corrupt_gif(self, client, temp_dir):
        """Deve rejeitar GIF corrompido."""
        # Criar arquivo com extensao gif mas conteudo invalido
        fake_gif = temp_dir / "fake.gif"
        fake_gif.write_bytes(b"not a real gif")

        with open(fake_gif, "rb") as f:
            response = client.post(
                "/api/gif/upload",
                files={"file": ("fake.gif", f, "image/gif")}
            )

        assert response.status_code == 400


class TestGifPreviewEndpoint:
    """Testes para GET /api/gif/preview/{upload_id}."""

    def test_returns_preview_for_valid_upload(self, client, sample_64x64_gif):
        """Deve retornar preview para upload valido."""
        # Primeiro fazer upload
        with open(sample_64x64_gif, "rb") as f:
            upload_response = client.post(
                "/api/gif/upload",
                files={"file": ("test.gif", f, "image/gif")}
            )

        upload_id = upload_response.json()["id"]

        # Obter preview
        response = client.get(f"/api/gif/preview/{upload_id}")

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/gif"

    def test_returns_404_for_invalid_upload(self, client):
        """Deve retornar 404 para upload invalido."""
        response = client.get("/api/gif/preview/invalid-id")

        assert response.status_code == 404


class TestGifSendEndpoint:
    """Testes para POST /api/gif/send."""

    def test_requires_pixoo_connection(self, client, sample_64x64_gif):
        """Deve exigir conexao com Pixoo."""
        # Fazer upload
        with open(sample_64x64_gif, "rb") as f:
            upload_response = client.post(
                "/api/gif/upload",
                files={"file": ("test.gif", f, "image/gif")}
            )

        upload_id = upload_response.json()["id"]

        # Tentar enviar sem estar conectado
        response = client.post(
            "/api/gif/send",
            json={"id": upload_id}
        )

        assert response.status_code == 400
        assert "conectado" in response.json()["detail"].lower() or "Conecte" in response.json()["detail"]

    def test_returns_404_for_invalid_upload(self, client, mock_pixoo_connection):
        """Deve retornar 404 para upload invalido."""
        # Conectar ao mock
        client.post("/api/connect", json={"ip": "192.168.1.100"})

        response = client.post(
            "/api/gif/send",
            json={"id": "invalid-id"}
        )

        assert response.status_code == 404


class TestGifDeleteEndpoint:
    """Testes para DELETE /api/gif/{upload_id}."""

    def test_deletes_valid_upload(self, client, sample_64x64_gif):
        """Deve deletar upload valido."""
        # Fazer upload
        with open(sample_64x64_gif, "rb") as f:
            upload_response = client.post(
                "/api/gif/upload",
                files={"file": ("test.gif", f, "image/gif")}
            )

        upload_id = upload_response.json()["id"]

        # Deletar
        response = client.delete(f"/api/gif/{upload_id}")

        assert response.status_code == 200
        assert response.json()["success"] is True

        # Verificar que foi deletado
        preview_response = client.get(f"/api/gif/preview/{upload_id}")
        assert preview_response.status_code == 404

    def test_returns_404_for_invalid_upload(self, client):
        """Deve retornar 404 para upload invalido."""
        response = client.delete("/api/gif/invalid-id")

        assert response.status_code == 404
