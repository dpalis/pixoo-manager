"""
Serviço para envio de texto scrolling ao Pixoo 64.

Gerencia TextId internamente (1-20, cicla) e envia comandos
SendHttpText e ClearHttpText para o dispositivo.

Suporta cor de fundo enviando um GIF de cor sólida antes do texto.
"""

import time

from PIL import Image

from app.config import PIXOO_SIZE
from app.services.pixoo_connection import get_pixoo_connection
from app.services.pixoo_upload import upload_single_frame


class TextSender:
    """
    Envia texto scrolling para o Pixoo 64.

    Uso:
        sender = TextSender()
        result = sender.send_text("Hello!", "#FFFFFF", 150, 0, 28)
        result = sender.clear_text()
    """

    def __init__(self):
        self._text_id: int = 0

    def send_background(self, color: str) -> dict:
        """
        Envia uma imagem de fundo de cor sólida para o Pixoo.

        Como o Pixoo não suporta cor de fundo nativamente no texto,
        enviamos um GIF de cor sólida antes do texto.

        Args:
            color: Cor em hex #RRGGBB

        Returns:
            Resposta do Pixoo como dict

        Raises:
            PixooConnectionError: Se não conectado ou falha no envio
        """
        # Converter hex para RGB
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)

        # Criar imagem de cor sólida 64x64
        img = Image.new("RGB", (PIXOO_SIZE, PIXOO_SIZE), (r, g, b))

        # Enviar como frame único
        return upload_single_frame(img)

    def send_text(
        self,
        text: str,
        color: str = "#FFFFFF",
        speed: int = 150,
        font: int = 0,
        y: int = 28,
        background_color: str | None = None
    ) -> dict:
        """
        Envia texto scrolling para o Pixoo.

        Args:
            text: Texto a exibir (max 500 chars)
            color: Cor em hex #RRGGBB (default: branco)
            speed: Velocidade em ms entre frames, 150-200 (default: 150)
            font: Índice da fonte, 0-7 (default: 0)
            y: Posição vertical, 0-56 (default: 28 = centro)
            background_color: Cor de fundo em hex #RRGGBB (opcional)

        Returns:
            Resposta do Pixoo como dict

        Raises:
            PixooConnectionError: Se não conectado ou falha no envio
        """
        # Enviar fundo colorido primeiro, se diferente de preto
        if background_color and background_color.upper() != "#000000":
            self.send_background(background_color)
            # Aguardar para o display processar
            time.sleep(0.3)

        # Incrementa TextId ciclando de 1 a 20
        self._text_id = (self._text_id % 20) + 1

        command = {
            "Command": "Draw/SendHttpText",
            "TextId": self._text_id,
            "x": 0,
            "y": y,
            "dir": 0,  # Scroll para esquerda
            "font": font,
            "TextWidth": 64,
            "TextString": text,
            "speed": speed,
            "color": color,
            "align": 1  # Alinhamento esquerda
        }

        return get_pixoo_connection().send_command(command)

    def clear_text(self) -> dict:
        """
        Limpa todos os textos do display.

        Returns:
            Resposta do Pixoo como dict

        Raises:
            PixooConnectionError: Se não conectado ou falha no envio
        """
        self._text_id = 0
        return get_pixoo_connection().send_command({"Command": "Draw/ClearHttpText"})


# Singleton para uso global
text_sender = TextSender()
