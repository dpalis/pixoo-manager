"""
Testes do servico de conexao com o Pixoo.
"""

import pytest
from unittest.mock import patch, Mock

from app.services.pixoo_connection import PixooConnection, get_pixoo_connection
from app.services.exceptions import PixooConnectionError


class TestPixooConnectionSingleton:
    """Testes do padrao Singleton."""

    def test_returns_same_instance(self):
        """Deve retornar a mesma instancia sempre."""
        conn1 = PixooConnection()
        conn2 = PixooConnection()

        assert conn1 is conn2

    def test_get_pixoo_connection_returns_instance(self):
        """get_pixoo_connection deve retornar instancia singleton."""
        conn1 = get_pixoo_connection()
        conn2 = get_pixoo_connection()

        assert conn1 is conn2


class TestPixooConnectionState:
    """Testes de estado da conexao."""

    def test_initial_state_disconnected(self):
        """Estado inicial deve ser desconectado."""
        conn = PixooConnection()

        assert conn.is_connected is False
        assert conn.current_ip is None

    def test_disconnect_clears_state(self, mock_pixoo_connection):
        """Disconnect deve limpar estado."""
        mock_pixoo_connection.connect("192.168.1.100")
        assert mock_pixoo_connection.is_connected is True

        mock_pixoo_connection.disconnect()

        assert mock_pixoo_connection.is_connected is False
        assert mock_pixoo_connection.current_ip is None


class TestPixooConnectionConnect:
    """Testes de conexao."""

    def test_connect_success(self, mock_pixoo_connection):
        """Conexao bem-sucedida deve atualizar estado."""
        result = mock_pixoo_connection.connect("192.168.1.100")

        assert result is True
        assert mock_pixoo_connection.is_connected is True
        assert mock_pixoo_connection.current_ip == "192.168.1.100"

    @patch("app.services.pixoo_connection.requests.post")
    def test_connect_timeout_raises_error(self, mock_post):
        """Timeout deve levantar PixooConnectionError."""
        import requests
        mock_post.side_effect = requests.exceptions.Timeout()

        conn = PixooConnection()

        with pytest.raises(PixooConnectionError) as exc:
            conn.connect("192.168.1.100")

        assert "Timeout" in str(exc.value)

    @patch("app.services.pixoo_connection.requests.post")
    def test_connect_connection_error_raises_error(self, mock_post):
        """Erro de conexao deve levantar PixooConnectionError."""
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError()

        conn = PixooConnection()

        with pytest.raises(PixooConnectionError) as exc:
            conn.connect("192.168.1.100")

        assert "conectar" in str(exc.value).lower()


class TestPixooConnectionDiscover:
    """Testes de descoberta de dispositivos."""

    def test_discover_returns_list(self, mock_pixoo_connection):
        """Discover deve retornar lista de IPs."""
        devices = mock_pixoo_connection.discover()

        assert isinstance(devices, list)
        assert len(devices) > 0

    def test_discover_returns_valid_ips(self, mock_pixoo_connection):
        """IPs retornados devem ser validos."""
        devices = mock_pixoo_connection.discover()

        for ip in devices:
            parts = ip.split(".")
            assert len(parts) == 4
            for part in parts:
                assert 0 <= int(part) <= 255


class TestPixooConnectionSendCommand:
    """Testes de envio de comandos."""

    def test_send_command_when_connected(self, mock_pixoo_connection):
        """Deve enviar comando quando conectado."""
        mock_pixoo_connection.connect("192.168.1.100")

        result = mock_pixoo_connection.send_command({"Command": "Test"})

        assert result["error_code"] == 0
        assert {"Command": "Test"} in mock_pixoo_connection.commands_sent

    def test_send_command_when_disconnected_raises_error(self, mock_pixoo_connection):
        """Deve levantar erro quando desconectado."""
        # Nao conectar

        with pytest.raises(PixooConnectionError) as exc:
            mock_pixoo_connection.send_command({"Command": "Test"})

        assert "conectado" in str(exc.value).lower()


class TestPixooConnectionGetStatus:
    """Testes de status."""

    def test_get_status_when_disconnected(self, mock_pixoo_connection):
        """Status quando desconectado."""
        status = mock_pixoo_connection.get_status()

        assert status["connected"] is False
        assert status["ip"] is None

    def test_get_status_when_connected(self, mock_pixoo_connection):
        """Status quando conectado."""
        mock_pixoo_connection.connect("192.168.1.100")

        status = mock_pixoo_connection.get_status()

        assert status["connected"] is True
        assert status["ip"] == "192.168.1.100"
