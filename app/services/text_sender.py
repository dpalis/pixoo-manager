"""
Serviço para envio de texto scrolling ao Pixoo 64.

Gerencia TextId internamente (1-20, cicla) e envia comandos
SendHttpText e ClearHttpText para o dispositivo.
"""

from app.services.pixoo_connection import get_pixoo_connection


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

    def send_text(
        self,
        text: str,
        color: str = "#FFFFFF",
        speed: int = 150,
        font: int = 0,
        y: int = 28
    ) -> dict:
        """
        Envia texto scrolling para o Pixoo.

        Args:
            text: Texto a exibir (max 500 chars)
            color: Cor em hex #RRGGBB (default: branco)
            speed: Velocidade em ms entre frames, 150-200 (default: 150)
            font: Índice da fonte, 0-7 (default: 0)
            y: Posição vertical, 0-56 (default: 28 = centro)

        Returns:
            Resposta do Pixoo como dict

        Raises:
            PixooConnectionError: Se não conectado ou falha no envio
        """
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
