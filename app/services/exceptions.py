"""Exceções customizadas do Pixoo Manager."""


class PixooError(Exception):
    """Exceção base para erros do Pixoo Manager."""
    pass


class PixooConnectionError(PixooError):
    """Falha ao conectar com o Pixoo."""
    pass


class PixooNotFoundError(PixooError):
    """Pixoo não encontrado na rede."""
    pass


class ConversionError(PixooError):
    """Falha ao converter mídia."""
    pass


class UploadError(PixooError):
    """Falha ao enviar para o Pixoo."""
    pass


class InvalidFileError(PixooError):
    """Arquivo inválido (tipo, tamanho, formato)."""
    pass


class VideoTooLongError(ConversionError):
    """Vídeo excede duração máxima permitida."""
    pass


class TooManyFramesError(ConversionError):
    """GIF excede número máximo de frames."""
    pass


class ValidationError(PixooError):
    """Erro de validação de entrada do usuário."""
    pass


class RateLimitError(PixooError):
    """Limite de requisições excedido."""
    pass
