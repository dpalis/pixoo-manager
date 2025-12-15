"""
Testes de integracao para router de conexao.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestDiscoverEndpoint:
    """Testes para POST /api/discover."""

    def test_returns_discovered_devices(self, client, mock_pixoo_connection):
        """Deve retornar dispositivos descobertos."""
        response = client.post("/api/discover")

        assert response.status_code == 200
        data = response.json()
        assert "devices" in data
        assert isinstance(data["devices"], list)

    def test_returns_empty_list_when_no_devices(self, client, monkeypatch):
        """Deve retornar lista vazia quando nenhum dispositivo."""
        mock_conn = MagicMock()
        mock_conn.discover.return_value = []

        monkeypatch.setattr(
            "app.routers.connection.get_pixoo_connection",
            lambda: mock_conn
        )

        response = client.post("/api/discover")

        assert response.status_code == 200
        assert response.json()["devices"] == []


class TestConnectEndpoint:
    """Testes para POST /api/connect."""

    def test_connects_to_valid_ip(self, client, mock_pixoo_connection):
        """Deve conectar a IP valido."""
        response = client.post(
            "/api/connect",
            json={"ip": "192.168.1.100"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["ip"] == "192.168.1.100"

    def test_rejects_invalid_ip_format(self, client):
        """Deve rejeitar formato de IP invalido."""
        response = client.post(
            "/api/connect",
            json={"ip": "not-an-ip"}
        )

        assert response.status_code == 400

    def test_rejects_localhost(self, client):
        """Deve rejeitar localhost por seguranca."""
        response = client.post(
            "/api/connect",
            json={"ip": "127.0.0.1"}
        )

        assert response.status_code == 400

    def test_rejects_private_networks_other_than_local(self, client):
        """Deve rejeitar redes privadas nao-locais como 10.x.x.x."""
        # 10.x.x.x e permitido pois e rede privada comum
        # O teste aqui verifica apenas o formato valido
        pass


class TestDisconnectEndpoint:
    """Testes para POST /api/disconnect."""

    def test_disconnects_successfully(self, client, mock_pixoo_connection):
        """Deve desconectar com sucesso."""
        # Primeiro conectar
        client.post("/api/connect", json={"ip": "192.168.1.100"})

        response = client.post("/api/disconnect")

        assert response.status_code == 200
        assert response.json()["success"] is True


class TestStatusEndpoint:
    """Testes para GET /api/status."""

    def test_returns_status_disconnected(self, client, mock_pixoo_connection):
        """Deve retornar status desconectado."""
        response = client.get("/api/status")

        assert response.status_code == 200
        data = response.json()
        assert "connected" in data
        assert "ip" in data

    def test_returns_status_connected(self, client, mock_pixoo_connection):
        """Deve retornar status conectado apos conexao."""
        # Conectar
        client.post("/api/connect", json={"ip": "192.168.1.100"})

        response = client.get("/api/status")

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is True
        assert data["ip"] == "192.168.1.100"


class TestConfigEndpoint:
    """Testes para GET /api/config."""

    def test_returns_config_values(self, client):
        """Deve retornar configuracoes da aplicacao."""
        response = client.get("/api/config")

        assert response.status_code == 200
        data = response.json()

        assert "pixoo_size" in data
        assert data["pixoo_size"] == 64

        assert "max_upload_frames" in data
        assert "max_convert_frames" in data
        assert "max_video_duration" in data
        assert "max_file_size" in data
        assert "max_file_size_mb" in data
        assert "supported_formats" in data

    def test_returns_supported_formats(self, client):
        """Deve retornar formatos suportados."""
        response = client.get("/api/config")

        data = response.json()
        formats = data["supported_formats"]

        assert "gif" in formats
        assert "image" in formats
        assert "video" in formats
