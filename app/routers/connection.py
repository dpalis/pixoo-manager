"""
Router para endpoints de conexão com o Pixoo.

Endpoints:
- POST /api/discover - Busca dispositivos na rede
- POST /api/connect - Conecta ao Pixoo
- POST /api/disconnect - Desconecta
- GET /api/status - Retorna status da conexão
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.pixoo_connection import get_pixoo_connection
from app.services.exceptions import PixooConnectionError, ValidationError
from app.services.validators import validate_pixoo_ip
from app.middleware import discover_limiter, check_rate_limit

router = APIRouter(prefix="/api", tags=["connection"])


class ConnectRequest(BaseModel):
    """Request para conectar ao Pixoo."""
    ip: str


class StatusResponse(BaseModel):
    """Response com status de conexão."""
    connected: bool
    ip: str | None


class DiscoverResponse(BaseModel):
    """Response com dispositivos descobertos."""
    devices: list[str]


@router.post("/discover", response_model=DiscoverResponse)
async def discover_devices():
    """
    Busca dispositivos Pixoo na rede local.

    Tenta descoberta via mDNS primeiro, depois scan de rede como fallback.

    Rate limited: 3 requisições por minuto (operação intensiva).
    """
    # Rate limit: descoberta cria muitas threads
    check_rate_limit(discover_limiter)

    conn = get_pixoo_connection()
    devices = conn.discover(timeout=3.0)
    return DiscoverResponse(devices=devices)


@router.post("/connect")
async def connect_to_pixoo(request: ConnectRequest):
    """
    Conecta ao Pixoo no IP especificado.

    Valida o IP antes de conectar para prevenir SSRF.
    Testa a conexão antes de confirmar.
    """
    # Validação de segurança: previne SSRF
    try:
        validated_ip = validate_pixoo_ip(request.ip)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    conn = get_pixoo_connection()

    try:
        conn.connect(validated_ip)
        return {"success": True, "ip": validated_ip}
    except PixooConnectionError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/disconnect")
async def disconnect_from_pixoo():
    """Desconecta do Pixoo."""
    conn = get_pixoo_connection()
    conn.disconnect()
    return {"success": True}


@router.get("/status", response_model=StatusResponse)
async def get_connection_status():
    """Retorna o status atual da conexão."""
    conn = get_pixoo_connection()
    status = conn.get_status()
    return StatusResponse(**status)
