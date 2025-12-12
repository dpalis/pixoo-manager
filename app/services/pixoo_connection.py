"""
Serviço de conexão com o Pixoo 64.

Implementa descoberta de dispositivos na rede e gerenciamento de conexão.
Usa padrão Singleton para manter estado de conexão entre requests.
"""

import socket
import threading
from typing import List, Optional

import requests
from zeroconf import ServiceBrowser, ServiceListener, Zeroconf

from app.services.exceptions import PixooConnectionError, PixooNotFoundError


class PixooServiceListener(ServiceListener):
    """Listener para descoberta de dispositivos Pixoo via mDNS."""

    def __init__(self):
        self.devices: List[str] = []

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info and info.addresses:
            ip = socket.inet_ntoa(info.addresses[0])
            if ip not in self.devices:
                self.devices.append(ip)

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        pass

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        pass


class PixooConnection:
    """
    Singleton para gerenciar conexão com o Pixoo 64.

    Uso:
        conn = PixooConnection()
        devices = conn.discover()
        conn.connect(devices[0])
        conn.send_command({"Command": "Channel/GetIndex"})
        conn.disconnect()
    """

    _instance: Optional["PixooConnection"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "PixooConnection":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._ip: Optional[str] = None
        self._connected: bool = False

    @property
    def is_connected(self) -> bool:
        """Retorna True se conectado ao Pixoo."""
        return self._connected

    @property
    def current_ip(self) -> Optional[str]:
        """Retorna o IP do Pixoo conectado, ou None."""
        return self._ip if self._connected else None

    def discover(self, timeout: float = 3.0) -> List[str]:
        """
        Descobre dispositivos Pixoo na rede via mDNS.

        Args:
            timeout: Tempo máximo de busca em segundos

        Returns:
            Lista de IPs encontrados
        """
        devices: List[str] = []

        try:
            zeroconf = Zeroconf()
            listener = PixooServiceListener()

            # Pixoo usa serviço _pixoo._tcp.local.
            browser = ServiceBrowser(zeroconf, "_pixoo._tcp.local.", listener)

            # Aguardar descoberta
            import time
            time.sleep(timeout)

            devices = listener.devices.copy()
            zeroconf.close()

        except Exception:
            # mDNS pode falhar em algumas redes
            pass

        # Se não encontrou via mDNS, tenta scan de rede como fallback
        if not devices:
            devices = self._scan_network()

        return devices

    def _scan_network(self, timeout: float = 0.5) -> List[str]:
        """
        Scan de rede como fallback quando mDNS não funciona.

        Tenta conectar na porta 80 dos IPs comuns de rede local.
        """
        devices: List[str] = []

        # Obtém o IP local para determinar a rede
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            return devices

        # Extrai o prefixo da rede (ex: 192.168.1)
        network_prefix = ".".join(local_ip.split(".")[:-1])

        # Scan paralelo dos IPs mais comuns (1-50 e 100-150)
        def check_ip(ip: str):
            try:
                response = requests.post(
                    f"http://{ip}:80/post",
                    json={"Command": "Channel/GetIndex"},
                    timeout=timeout
                )
                if response.status_code == 200:
                    data = response.json()
                    # Pixoo retorna error_code 0 em sucesso
                    if data.get("error_code") == 0:
                        devices.append(ip)
            except Exception:
                pass

        threads = []
        for i in list(range(1, 51)) + list(range(100, 151)):
            ip = f"{network_prefix}.{i}"
            t = threading.Thread(target=check_ip, args=(ip,))
            t.start()
            threads.append(t)

        # Aguardar todas as threads
        for t in threads:
            t.join()

        return devices

    def connect(self, ip: str) -> bool:
        """
        Conecta ao Pixoo no IP especificado.

        Args:
            ip: Endereço IP do Pixoo

        Returns:
            True se conexão bem-sucedida

        Raises:
            PixooConnectionError: Se falhar ao conectar
        """
        try:
            # Testar conexão com comando simples
            response = requests.post(
                f"http://{ip}:80/post",
                json={"Command": "Channel/GetIndex"},
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("error_code") == 0:
                    self._ip = ip
                    self._connected = True
                    return True

            raise PixooConnectionError(f"Pixoo em {ip} não respondeu corretamente")

        except requests.exceptions.Timeout:
            raise PixooConnectionError(f"Timeout ao conectar com {ip}")
        except requests.exceptions.ConnectionError:
            raise PixooConnectionError(f"Não foi possível conectar com {ip}")
        except Exception as e:
            raise PixooConnectionError(f"Erro ao conectar: {e}")

    def disconnect(self) -> None:
        """Desconecta do Pixoo."""
        self._ip = None
        self._connected = False

    def send_command(self, command: dict) -> dict:
        """
        Envia comando para o Pixoo conectado.

        Args:
            command: Dicionário com o comando (ex: {"Command": "Channel/GetIndex"})

        Returns:
            Resposta do Pixoo como dicionário

        Raises:
            PixooConnectionError: Se não estiver conectado ou comando falhar
        """
        if not self._connected or not self._ip:
            raise PixooConnectionError("Não conectado ao Pixoo")

        try:
            response = requests.post(
                f"http://{self._ip}:80/post",
                json=command,
                timeout=10
            )

            if response.status_code == 200:
                return response.json()

            raise PixooConnectionError(f"Comando falhou: HTTP {response.status_code}")

        except requests.exceptions.Timeout:
            raise PixooConnectionError("Timeout ao enviar comando")
        except requests.exceptions.ConnectionError:
            # Conexão perdida
            self._connected = False
            raise PixooConnectionError("Conexão perdida com o Pixoo")
        except Exception as e:
            raise PixooConnectionError(f"Erro ao enviar comando: {e}")

    def get_status(self) -> dict:
        """
        Retorna status atual da conexão.

        Returns:
            Dict com connected (bool) e ip (str ou None)
        """
        return {
            "connected": self._connected,
            "ip": self._ip if self._connected else None
        }


# Instância global (singleton)
def get_pixoo_connection() -> PixooConnection:
    """Retorna a instância singleton do PixooConnection."""
    return PixooConnection()
