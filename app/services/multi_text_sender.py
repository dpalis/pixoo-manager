"""
Serviço para envio de layouts com múltiplas linhas de texto ao Pixoo 64.

Gerencia o envio sequencial de fundo + textos com delays apropriados
para garantir que o dispositivo processe corretamente.
"""

import asyncio
from dataclasses import dataclass
from typing import List, Optional

from PIL import Image

from app.services.pixoo_connection import get_pixoo_connection
from app.services.pixoo_upload import upload_single_frame
from app.services.exceptions import PixooConnectionError


# Delays configuráveis (em segundos)
DELAY_AFTER_BACKGROUND = 0.3  # 300ms após enviar fundo
DELAY_BETWEEN_TEXTS = 0.05    # 50ms entre textos


# Mapeamento de font_size + font_type para font ID do Pixoo
# Baseado nas fontes seguras descobertas: 0, 2, 4, 5, 8
FONT_MAP = {
    ("small", "sans"): 2,
    ("small", "pixel"): 5,
    ("medium", "sans"): 0,
    ("medium", "pixel"): 8,
    ("large", "sans"): 4,
    ("large", "pixel"): 4,  # Não há fonte pixel grande, usa sans
    # Fallbacks para tipos não mapeados
    ("small", "serif"): 2,
    ("medium", "serif"): 0,
    ("large", "serif"): 4,
}


def get_font_id(size: str, font_type: str) -> int:
    """
    Retorna o ID da fonte do Pixoo baseado em tamanho e tipo.

    Args:
        size: 'small', 'medium', ou 'large'
        font_type: 'sans', 'serif', ou 'pixel'

    Returns:
        ID da fonte (0-8)
    """
    return FONT_MAP.get((size, font_type), 0)


@dataclass
class TextLine:
    """Representa uma linha de texto para envio."""
    text: str
    x: int = 0
    y: int = 28
    color: str = "#FFFFFF"
    font_size: str = "medium"  # small, medium, large
    font_type: str = "sans"    # sans, serif, pixel
    speed: int = 120           # 120-200ms


class MultiTextSender:
    """
    Envia layouts com múltiplas linhas de texto para o Pixoo 64.

    Sequência de envio:
    1. Limpa textos anteriores
    2. Envia fundo como GIF de 1 frame
    3. Envia cada linha com TextId sequencial (1, 2, 3...)
    """

    def clear_all_texts(self) -> dict:
        """
        Limpa todos os textos do display.

        Returns:
            Resposta do Pixoo

        Raises:
            PixooConnectionError: Se não conectado
        """
        conn = get_pixoo_connection()
        if not conn.is_connected:
            raise PixooConnectionError("Não conectado ao Pixoo")

        return conn.send_command({"Command": "Draw/ClearHttpText"})

    def send_text_line(self, text_id: int, line: TextLine) -> dict:
        """
        Envia uma linha de texto para o Pixoo.

        Args:
            text_id: ID do texto (1-20)
            line: Dados da linha

        Returns:
            Resposta do Pixoo
        """
        conn = get_pixoo_connection()

        font_id = get_font_id(line.font_size, line.font_type)

        command = {
            "Command": "Draw/SendHttpText",
            "TextId": text_id,
            "x": line.x,
            "y": line.y,
            "dir": 0,  # Scroll para esquerda
            "font": font_id,
            "TextWidth": 64,
            "TextString": line.text,
            "speed": line.speed,
            "color": line.color,
            "align": 1  # Alinhamento esquerda
        }

        return conn.send_command(command)

    async def send_layout(
        self,
        background: Image.Image,
        lines: List[TextLine]
    ) -> dict:
        """
        Envia layout completo: fundo + múltiplas linhas de texto.

        Args:
            background: Imagem PIL 64x64 para fundo
            lines: Lista de linhas de texto (máx 20)

        Returns:
            Dict com resultado do envio

        Raises:
            PixooConnectionError: Se não conectado
            ValueError: Se mais de 20 linhas
        """
        conn = get_pixoo_connection()
        if not conn.is_connected:
            raise PixooConnectionError("Não conectado ao Pixoo")

        if len(lines) > 20:
            raise ValueError("Máximo de 20 linhas de texto permitido")

        # Filtrar linhas vazias
        valid_lines = [line for line in lines if line.text.strip()]

        if not valid_lines:
            raise ValueError("Pelo menos uma linha de texto é necessária")

        # 1. Limpar textos anteriores
        self.clear_all_texts()

        # 2. Enviar fundo
        upload_single_frame(background)

        # 3. Aguardar processamento do fundo
        await asyncio.sleep(DELAY_AFTER_BACKGROUND)

        # 4. Enviar cada linha de texto
        for idx, line in enumerate(valid_lines):
            text_id = idx + 1  # TextId começa em 1

            result = self.send_text_line(text_id, line)

            if result.get("error_code", 0) != 0:
                return {
                    "success": False,
                    "error": f"Erro na linha {idx + 1}: {result}",
                    "lines_sent": idx
                }

            # Delay entre textos (exceto após o último)
            if idx < len(valid_lines) - 1:
                await asyncio.sleep(DELAY_BETWEEN_TEXTS)

        return {
            "success": True,
            "lines_sent": len(valid_lines)
        }


# Singleton para uso global
multi_text_sender = MultiTextSender()
