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
from app.services.exceptions import PixooConnectionError

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
    """
    conn = get_pixoo_connection()
    devices = conn.discover(timeout=3.0)
    return DiscoverResponse(devices=devices)


@router.post("/connect")
async def connect_to_pixoo(request: ConnectRequest):
    """
    Conecta ao Pixoo no IP especificado.

    Testa a conexão antes de confirmar.
    """
    conn = get_pixoo_connection()

    try:
        conn.connect(request.ip)
        return {"success": True, "ip": request.ip}
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
