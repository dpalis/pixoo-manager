"""
Serviço de conexão com o Pixoo 64.

Implementa descoberta de dispositivos na rede e gerenciamento de conexão.
Usa padrão Singleton para manter estado de conexão entre requests.

Features:
- Descoberta via mDNS (_pixoo._tcp.local.)
- Fallback: scan de rede (1-254)
- Persistência do último IP conectado para descoberta instantânea
"""

import json
import logging
import socket
import threading
from pathlib import Path
from typing import List, Optional

import requests
from zeroconf import ServiceBrowser, ServiceListener, Zeroconf

from app.config import USER_DATA_DIR
from app.services.exceptions import PixooConnectionError, PixooNotFoundError

# Arquivo para persistir último IP conectado
LAST_CONNECTION_FILE = USER_DATA_DIR / "last_connection.json"

logger = logging.getLogger(__name__)


def _load_last_ip() -> Optional[str]:
    """Carrega o último IP conectado do arquivo de persistência."""
    try:
        if LAST_CONNECTION_FILE.exists():
            data = json.loads(LAST_CONNECTION_FILE.read_text())
            return data.get("ip")
    except Exception as e:
        logger.debug(f"Erro ao carregar último IP: {e}")
    return None


def _save_last_ip(ip: str) -> None:
    """Salva o IP conectado para descoberta futura."""
    try:
        USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        LAST_CONNECTION_FILE.write_text(json.dumps({"ip": ip}))
        logger.debug(f"IP salvo para próxima descoberta: {ip}")
    except Exception as e:
        logger.warning(f"Erro ao salvar último IP: {e}")


def _check_pixoo_ip(ip: str, timeout: float = 0.3) -> bool:
    """Verifica se um IP é um Pixoo válido."""
    try:
        response = requests.post(
            f"http://{ip}:80/post",
            json={"Command": "Channel/GetIndex"},
            timeout=timeout
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("error_code") == 0
    except Exception:
        pass
    return False


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
    Singleton thread-safe para gerenciar conexão com o Pixoo 64.

    Uso:
        conn = PixooConnection()
        devices = conn.discover()
        conn.connect(devices[0])
        conn.send_command({"Command": "Channel/GetIndex"})
        conn.disconnect()
    """

    _instance: Optional["PixooConnection"] = None
    _instance_lock = threading.Lock()

    def __new__(cls) -> "PixooConnection":
        if cls._instance is None:
            with cls._instance_lock:
                # Double-check locking
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
        # Lock para proteger estado de conexão
        self._state_lock = threading.RLock()
        # Sessão HTTP persistente para reutilizar conexões (keep-alive)
        self._session: Optional[requests.Session] = None

    @property
    def is_connected(self) -> bool:
        """Retorna True se conectado ao Pixoo (thread-safe)."""
        with self._state_lock:
            return self._connected

    @property
    def current_ip(self) -> Optional[str]:
        """Retorna o IP do Pixoo conectado, ou None (thread-safe)."""
        with self._state_lock:
            return self._ip if self._connected else None

    def discover(self, timeout: float = 3.0) -> List[str]:
        """
        Descobre dispositivos Pixoo na rede.

        Ordem de prioridade:
        1. Último IP conectado (instantâneo se ainda válido)
        2. mDNS (_pixoo._tcp.local.)
        3. Scan de rede completo (1-254)

        Args:
            timeout: Tempo máximo de busca em segundos

        Returns:
            Lista de IPs encontrados
        """
        devices: List[str] = []

        # 1. Tentar último IP conectado (descoberta instantânea)
        last_ip = _load_last_ip()
        if last_ip:
            logger.debug(f"Tentando último IP conhecido: {last_ip}")
            if _check_pixoo_ip(last_ip, timeout=0.5):
                logger.info(f"Pixoo encontrado no último IP: {last_ip}")
                return [last_ip]
            logger.debug(f"Último IP {last_ip} não responde mais")

        # 2. Tentar mDNS
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

        except Exception as e:
            # mDNS pode falhar em algumas redes - log para debugging
            logger.debug(f"mDNS discovery failed (will try network scan): {e}")

        # 3. Se não encontrou via mDNS, tenta scan de rede como fallback
        if not devices:
            devices = self._scan_network()

        return devices

    def _scan_network(self) -> List[str]:
        """
        Scan de rede completo como fallback quando mDNS não funciona.

        Escaneia todos os IPs (1-254) da rede local.
        Usa ThreadPoolExecutor com 50 workers e timeout de 0.3s
        para scan rápido (~3 segundos total).
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

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

        def check_ip(ip: str) -> Optional[str]:
            """Verifica se um IP é um Pixoo. Retorna o IP se encontrado."""
            if _check_pixoo_ip(ip, timeout=0.3):
                return ip
            return None

        # Escaneia TODOS os IPs da rede (1-254)
        ips_to_check = [f"{network_prefix}.{i}" for i in range(1, 255)]

        logger.debug(f"Escaneando rede {network_prefix}.1-254 (254 IPs)")

        # Usa ThreadPoolExecutor com 50 workers para scan rápido
        # 254 IPs / 50 workers = ~5 batches × 0.3s timeout = ~1.5s
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = {executor.submit(check_ip, ip): ip for ip in ips_to_check}

            for future in as_completed(futures, timeout=30):
                try:
                    result = future.result()
                    if result:
                        devices.append(result)
                except Exception:
                    pass

        return devices

    def connect(self, ip: str) -> bool:
        """
        Conecta ao Pixoo no IP especificado (thread-safe).

        Args:
            ip: Endereço IP do Pixoo

        Returns:
            True se conexão bem-sucedida

        Raises:
            PixooConnectionError: Se falhar ao conectar
        """
        try:
            # Criar sessão HTTP persistente (keep-alive)
            session = requests.Session()

            # Testar conexão com comando simples
            response = session.post(
                f"http://{ip}:80/post",
                json={"Command": "Channel/GetIndex"},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("error_code") == 0:
                    with self._state_lock:
                        # Fechar sessão anterior se existir
                        if self._session:
                            self._session.close()
                        self._session = session
                        self._ip = ip
                        self._connected = True
                    # Salvar IP para próxima descoberta (fora do lock)
                    _save_last_ip(ip)
                    logger.info(f"Conectado ao Pixoo em {ip} (sessão persistente)")
                    return True

            session.close()
            raise PixooConnectionError(f"Pixoo em {ip} não respondeu corretamente")

        except requests.exceptions.Timeout:
            raise PixooConnectionError(f"Timeout ao conectar com {ip}")
        except requests.exceptions.ConnectionError:
            raise PixooConnectionError(f"Não foi possível conectar com {ip}")
        except PixooConnectionError:
            raise
        except Exception as e:
            raise PixooConnectionError(f"Erro ao conectar: {e}")

    def disconnect(self) -> None:
        """Desconecta do Pixoo (thread-safe)."""
        with self._state_lock:
            if self._session:
                self._session.close()
                self._session = None
            self._ip = None
            self._connected = False

    def send_command(
        self,
        command: dict,
        max_retries: int = 3,
        timeout: int = 120
    ) -> dict:
        """
        Envia comando para o Pixoo conectado (thread-safe) com retry automático.

        Args:
            command: Dicionário com o comando (ex: {"Command": "Channel/GetIndex"})
            max_retries: Número máximo de tentativas (default: 3)
            timeout: Timeout em segundos por tentativa (default: 120)

        Returns:
            Resposta do Pixoo como dicionário

        Raises:
            PixooConnectionError: Se não estiver conectado ou comando falhar após retries
        """
        import time

        with self._state_lock:
            if not self._connected or not self._ip or not self._session:
                raise PixooConnectionError("Não conectado ao Pixoo")
            ip = self._ip  # Cópia local para uso fora do lock
            session = self._session  # Sessão persistente

        last_error = None
        is_connection_error = False
        for attempt in range(max_retries):
            try:
                response = session.post(
                    f"http://{ip}:80/post",
                    json=command,
                    timeout=timeout
                )

                if response.status_code == 200:
                    return response.json()

                raise PixooConnectionError(f"Comando falhou: HTTP {response.status_code}")

            except requests.exceptions.Timeout:
                last_error = "Timeout ao enviar comando"
                is_connection_error = False
                logger.warning(f"Tentativa {attempt + 1}/{max_retries} falhou: timeout")
            except requests.exceptions.ConnectionError:
                last_error = "Conexão perdida com o Pixoo"
                is_connection_error = True
                logger.warning(f"Tentativa {attempt + 1}/{max_retries} falhou: conexão")
            except PixooConnectionError:
                raise
            except Exception as e:
                last_error = f"Erro ao enviar comando: {e}"
                is_connection_error = False
                logger.warning(f"Tentativa {attempt + 1}/{max_retries} falhou: {e}")

            # Aguardar antes de tentar novamente (backoff exponencial)
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 1s, 2s, 4s
                logger.info(f"Aguardando {wait_time}s antes de retry...")
                time.sleep(wait_time)

        # Todas as tentativas falharam
        # Só marca como desconectado se foi erro de conexão (não timeout)
        if is_connection_error:
            with self._state_lock:
                if self._session:
                    self._session.close()
                    self._session = None
                self._connected = False
        raise PixooConnectionError(f"{last_error} (após {max_retries} tentativas)")

    def get_status(self) -> dict:
        """
        Retorna status atual da conexão (thread-safe).

        Returns:
            Dict com connected (bool) e ip (str ou None)
        """
        with self._state_lock:
            return {
                "connected": self._connected,
                "ip": self._ip if self._connected else None
            }


# Instância global (singleton)
def get_pixoo_connection() -> PixooConnection:
    """Retorna a instância singleton do PixooConnection."""
    return PixooConnection()
