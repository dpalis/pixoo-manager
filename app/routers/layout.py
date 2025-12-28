"""
Router para layouts com múltiplas linhas de texto no Pixoo 64.

Endpoints:
- POST /api/layout/send - Envia layout completo (fundo + textos)
- POST /api/layout/clear - Limpa todos os textos
"""

import base64
import io
import re
from typing import List, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.services.layout_renderer import (
    BackgroundType,
    GradientDirection,
    PatternType,
    render_background,
)
from app.services.multi_text_sender import MultiTextSender, TextLine
from app.services.pixoo_connection import get_pixoo_connection
from app.services.exceptions import PixooConnectionError

router = APIRouter(prefix="/api/layout", tags=["layout"])


# ============================================
# Pydantic Models
# ============================================

class TextLineRequest(BaseModel):
    """Linha de texto para o layout."""
    text: str = Field(..., max_length=100)
    x: int = Field(default=0, ge=0, le=63)
    y: int = Field(..., ge=0, le=63)
    color: str = Field(default="#FFFFFF")
    font_size: Literal["small", "medium", "large"] = "medium"
    font_type: Literal["sans", "serif", "pixel"] = "sans"
    speed: int = Field(default=120, ge=120, le=200)

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str) -> str:
        """Valida formato de cor hex."""
        if not re.match(r"^#[0-9A-Fa-f]{6}$", v):
            raise ValueError("Cor deve estar no formato #RRGGBB")
        return v.upper()


class BackgroundRequest(BaseModel):
    """Configuração do fundo do layout."""
    type: Literal["solid", "gradient", "pattern"] = "solid"
    color: str = Field(default="#000000")
    gradient_start: str = Field(default="#000000")
    gradient_end: str = Field(default="#333333")
    gradient_direction: Literal["vertical", "horizontal", "diagonal"] = "vertical"
    pattern_type: Literal["checkerboard", "stripes_h", "stripes_v", "dots"] = "checkerboard"
    pattern_color1: str = Field(default="#000000")
    pattern_color2: str = Field(default="#1a1a2e")

    @field_validator("color", "gradient_start", "gradient_end", "pattern_color1", "pattern_color2")
    @classmethod
    def validate_color(cls, v: str) -> str:
        """Valida formato de cor hex."""
        if not re.match(r"^#[0-9A-Fa-f]{6}$", v):
            raise ValueError("Cor deve estar no formato #RRGGBB")
        return v.upper()


class LayoutRequest(BaseModel):
    """Request para enviar layout completo."""
    background: BackgroundRequest = Field(default_factory=BackgroundRequest)
    lines: List[TextLineRequest] = Field(..., min_length=1, max_length=20)


class LayoutResponse(BaseModel):
    """Response após envio de layout."""
    success: bool
    lines_sent: int
    error: Optional[str] = None


class ClearResponse(BaseModel):
    """Response após limpar textos."""
    success: bool


class PreviewResponse(BaseModel):
    """Response com preview do fundo em base64."""
    success: bool
    image_base64: str


# ============================================
# Endpoints
# ============================================

@router.post("/send", response_model=LayoutResponse)
async def send_layout(request: LayoutRequest):
    """
    Envia layout completo para o Pixoo.

    O layout consiste em um fundo (imagem 64x64) e múltiplas linhas de texto.
    Requer conexão prévia com o Pixoo via /api/connect.
    """
    conn = get_pixoo_connection()
    if not conn.is_connected:
        raise HTTPException(
            status_code=400,
            detail="Não conectado ao Pixoo. Conecte primeiro."
        )

    try:
        # Renderizar fundo
        bg = request.background
        background_image = render_background(
            bg_type=BackgroundType(bg.type),
            color=bg.color,
            gradient_start=bg.gradient_start,
            gradient_end=bg.gradient_end,
            gradient_direction=GradientDirection(bg.gradient_direction),
            pattern_type=PatternType(bg.pattern_type),
            pattern_color1=bg.pattern_color1,
            pattern_color2=bg.pattern_color2,
        )

        # Converter requests para TextLine
        text_lines = [
            TextLine(
                text=line.text,
                x=line.x,
                y=line.y,
                color=line.color,
                font_size=line.font_size,
                font_type=line.font_type,
                speed=line.speed,
            )
            for line in request.lines
        ]

        # Enviar layout
        sender = MultiTextSender()
        result = await sender.send_layout(background_image, text_lines)

        return LayoutResponse(
            success=result.get("success", False),
            lines_sent=result.get("lines_sent", 0),
            error=result.get("error"),
        )

    except PixooConnectionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao enviar layout: {e}")


@router.post("/clear", response_model=ClearResponse)
async def clear_layout():
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
        sender = MultiTextSender()
        result = sender.clear_all_texts()

        return ClearResponse(
            success=result.get("error_code", -1) == 0
        )

    except PixooConnectionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao limpar textos: {e}")


@router.post("/preview", response_model=PreviewResponse)
async def preview_background(request: BackgroundRequest):
    """
    Gera preview do fundo em base64.

    Útil para mostrar o fundo no canvas antes de enviar.
    """
    try:
        bg = request
        background_image = render_background(
            bg_type=BackgroundType(bg.type),
            color=bg.color,
            gradient_start=bg.gradient_start,
            gradient_end=bg.gradient_end,
            gradient_direction=GradientDirection(bg.gradient_direction),
            pattern_type=PatternType(bg.pattern_type),
            pattern_color1=bg.pattern_color1,
            pattern_color2=bg.pattern_color2,
        )

        # Converter para base64 PNG
        buffer = io.BytesIO()
        background_image.save(buffer, format="PNG")
        image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        return PreviewResponse(
            success=True,
            image_base64=f"data:image/png;base64,{image_base64}"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar preview: {e}")
