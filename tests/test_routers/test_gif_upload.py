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

    def test_returns_404_for_nonexistent_upload(self, client):
        """Deve retornar 404 para upload que nao existe."""
        response = client.get("/api/gif/preview/00000000")

        assert response.status_code == 404

    def test_returns_400_for_invalid_id_format(self, client):
        """Deve retornar 400 para formato de ID invalido."""
        response = client.get("/api/gif/preview/invalid-id")

        assert response.status_code == 400


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

    def test_returns_404_for_nonexistent_upload(self, client, mock_pixoo_connection):
        """Deve retornar 404 para upload que nao existe."""
        # Conectar ao mock
        client.post("/api/connect", json={"ip": "192.168.1.100"})

        response = client.post(
            "/api/gif/send",
            json={"id": "00000000"}
        )

        assert response.status_code == 404

    def test_returns_400_for_invalid_id_format(self, client, mock_pixoo_connection):
        """Deve retornar 400 para formato de ID invalido."""
        # Conectar ao mock
        client.post("/api/connect", json={"ip": "192.168.1.100"})

        response = client.post(
            "/api/gif/send",
            json={"id": "invalid-id"}
        )

        assert response.status_code == 400


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

    def test_returns_404_for_nonexistent_upload(self, client):
        """Deve retornar 404 para upload que nao existe."""
        response = client.delete("/api/gif/00000000")

        assert response.status_code == 404

    def test_returns_400_for_invalid_id_format(self, client):
        """Deve retornar 400 para formato de ID invalido."""
        response = client.delete("/api/gif/invalid-id")

        assert response.status_code == 400


class TestGifUploadRawEndpoint:
    """Testes para POST /api/gif/upload-raw."""

    def test_uploads_gif_without_conversion(self, client, sample_large_gif):
        """Deve fazer upload de GIF sem converter."""
        with open(sample_large_gif, "rb") as f:
            response = client.post(
                "/api/gif/upload-raw",
                files={"file": ("test.gif", f, "image/gif")}
            )

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["width"] == 256  # Mantém tamanho original
        assert data["height"] == 256
        assert "first_frame_url" in data

    def test_returns_first_frame_url(self, client, sample_large_gif):
        """Deve retornar URL do primeiro frame."""
        with open(sample_large_gif, "rb") as f:
            response = client.post(
                "/api/gif/upload-raw",
                files={"file": ("test.gif", f, "image/gif")}
            )

        data = response.json()
        upload_id = data["id"]

        # URL deve apontar para frame/0
        assert data["first_frame_url"] == f"/api/gif/frame/{upload_id}/0"


class TestGifFrameEndpoint:
    """Testes para GET /api/gif/frame/{upload_id}/{frame_num}."""

    def test_returns_first_frame(self, client, sample_large_gif):
        """Deve retornar primeiro frame como PNG."""
        # Upload raw
        with open(sample_large_gif, "rb") as f:
            upload_response = client.post(
                "/api/gif/upload-raw",
                files={"file": ("test.gif", f, "image/gif")}
            )

        upload_id = upload_response.json()["id"]

        # Obter frame 0
        response = client.get(f"/api/gif/frame/{upload_id}/0")

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"

    def test_returns_specific_frame(self, client, sample_large_gif):
        """Deve retornar frame específico."""
        with open(sample_large_gif, "rb") as f:
            upload_response = client.post(
                "/api/gif/upload-raw",
                files={"file": ("test.gif", f, "image/gif")}
            )

        upload_id = upload_response.json()["id"]

        # Obter frame 1
        response = client.get(f"/api/gif/frame/{upload_id}/1")

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"

    def test_returns_400_for_invalid_frame_index(self, client, sample_large_gif):
        """Deve retornar 400 para índice de frame inválido."""
        with open(sample_large_gif, "rb") as f:
            upload_response = client.post(
                "/api/gif/upload-raw",
                files={"file": ("test.gif", f, "image/gif")}
            )

        upload_id = upload_response.json()["id"]

        # Frame 999 não existe
        response = client.get(f"/api/gif/frame/{upload_id}/999")

        assert response.status_code == 400

    def test_returns_404_for_nonexistent_upload(self, client):
        """Deve retornar 404 para upload que não existe."""
        response = client.get("/api/gif/frame/00000000/0")

        assert response.status_code == 404


class TestGifCropAndConvertEndpoint:
    """Testes para POST /api/gif/crop-and-convert."""

    def test_crops_and_converts_gif(self, client, sample_large_gif):
        """Deve aplicar crop e converter para 64x64."""
        # Upload raw
        with open(sample_large_gif, "rb") as f:
            upload_response = client.post(
                "/api/gif/upload-raw",
                files={"file": ("test.gif", f, "image/gif")}
            )

        upload_id = upload_response.json()["id"]

        # Crop e convert
        response = client.post(
            "/api/gif/crop-and-convert",
            json={
                "id": upload_id,
                "crop_x": 50,
                "crop_y": 50,
                "crop_width": 100,
                "crop_height": 100
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["width"] == 64
        assert data["height"] == 64
        assert data["converted"] is True
        assert "preview_url" in data

    def test_rejects_invalid_crop_coordinates(self, client, sample_large_gif):
        """Deve rejeitar coordenadas de crop inválidas."""
        with open(sample_large_gif, "rb") as f:
            upload_response = client.post(
                "/api/gif/upload-raw",
                files={"file": ("test.gif", f, "image/gif")}
            )

        upload_id = upload_response.json()["id"]

        # Crop excede dimensões (256x256)
        response = client.post(
            "/api/gif/crop-and-convert",
            json={
                "id": upload_id,
                "crop_x": 200,
                "crop_y": 0,
                "crop_width": 100,  # 200 + 100 = 300 > 256
                "crop_height": 100
            }
        )

        assert response.status_code == 400
        assert "excede" in response.json()["detail"].lower() or "largura" in response.json()["detail"].lower()

    def test_rejects_negative_coordinates(self, client, sample_large_gif):
        """Deve rejeitar coordenadas negativas."""
        with open(sample_large_gif, "rb") as f:
            upload_response = client.post(
                "/api/gif/upload-raw",
                files={"file": ("test.gif", f, "image/gif")}
            )

        upload_id = upload_response.json()["id"]

        response = client.post(
            "/api/gif/crop-and-convert",
            json={
                "id": upload_id,
                "crop_x": -10,
                "crop_y": 0,
                "crop_width": 100,
                "crop_height": 100
            }
        )

        assert response.status_code == 400
        assert "negativ" in response.json()["detail"].lower()

    def test_deletes_original_after_crop(self, client, sample_large_gif):
        """Deve deletar upload original após crop."""
        with open(sample_large_gif, "rb") as f:
            upload_response = client.post(
                "/api/gif/upload-raw",
                files={"file": ("test.gif", f, "image/gif")}
            )

        original_id = upload_response.json()["id"]

        # Crop e convert
        response = client.post(
            "/api/gif/crop-and-convert",
            json={
                "id": original_id,
                "crop_x": 0,
                "crop_y": 0,
                "crop_width": 100,
                "crop_height": 100
            }
        )

        assert response.status_code == 200, f"Crop failed: {response.json()}"
        new_id = response.json()["id"]

        # Original deve ter sido deletado
        assert new_id != original_id
        frame_response = client.get(f"/api/gif/frame/{original_id}/0")
        assert frame_response.status_code == 404
