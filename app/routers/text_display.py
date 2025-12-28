"""
Router para exibição de texto scrolling no Pixoo 64.

Endpoints:
- POST /api/text/send - Envia texto para o display
- POST /api/text/clear - Limpa todos os textos
"""

import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.services.text_sender import text_sender
from app.services.pixoo_connection import get_pixoo_connection
from app.services.exceptions import PixooConnectionError

router = APIRouter(prefix="/api/text", tags=["text"])


class TextRequest(BaseModel):
    """Request para enviar texto ao Pixoo."""
    text: str = Field(..., min_length=1, max_length=500)
    color: str = Field(default="#FFFFFF")
    speed: int = Field(default=150, ge=150, le=200)
    font: int = Field(default=0, ge=0, le=7)
    y: int = Field(default=28, ge=0, le=56)

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str) -> str:
        """Valida formato de cor hex."""
        if not re.match(r"^#[0-9A-Fa-f]{6}$", v):
            raise ValueError("Cor deve estar no formato #RRGGBB")
        return v.upper()


class TextResponse(BaseModel):
    """Response após envio de texto."""
    success: bool
    text_id: int


class ClearResponse(BaseModel):
    """Response após limpar textos."""
    success: bool


@router.post("/send", response_model=TextResponse)
async def send_text(request: TextRequest):
    """
    Envia texto scrolling para o Pixoo.

    O texto rola da direita para a esquerda no display.
    Requer conexão prévia com o Pixoo via /api/connect.
    """
    conn = get_pixoo_connection()
    if not conn.is_connected:
        raise HTTPException(
            status_code=400,
            detail="Não conectado ao Pixoo. Conecte primeiro."
        )

    try:
        result = text_sender.send_text(
            text=request.text,
            color=request.color,
            speed=request.speed,
            font=request.font,
            y=request.y
        )

        return TextResponse(
            success=result.get("error_code", -1) == 0,
            text_id=text_sender._text_id
        )

    except PixooConnectionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao enviar texto: {e}")


@router.post("/clear", response_model=ClearResponse)
async def clear_text():
    """
    Limpa todos os textos do display.

    Requer conexão prévia com o Pixoo via /api/connect.
    """
    conn = get_pixoo_connection()
    if not conn.is_connected:
        raise HTTPException(
            status_code=400,
            detail="Não conectado ao Pixoo. Conecte primeiro."
        )

    try:
        result = text_sender.clear_text()

        return ClearResponse(
            success=result.get("error_code", -1) == 0
        )

    except PixooConnectionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao limpar textos: {e}")
