"""
Validadores e utilitários de segurança.

Centraliza validação de IPs, URLs e outras entradas do usuário.
"""

import ipaddress
import re
from typing import Optional

from app.services.exceptions import ValidationError


# =============================================================================
# Validação de IP (#2 - SSRF Protection)
# =============================================================================

def validate_pixoo_ip(ip_str: str) -> str:
    """
    Valida que o IP é um endereço privado válido para conexão com Pixoo.

    Bloqueia:
    - Loopback (127.x.x.x)
    - Link-local (169.254.x.x) - inclui cloud metadata endpoints
    - Multicast
    - Broadcast
    - IPs públicos (para prevenir SSRF externo)

    Args:
        ip_str: String do endereço IP

    Returns:
        IP validado como string

    Raises:
        ValidationError: Se IP for inválido ou não permitido
    """
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        raise ValidationError(f"Endereço IP inválido: {ip_str}")

    # Bloqueia loopback (127.x.x.x)
    if ip.is_loopback:
        raise ValidationError("Endereço loopback não permitido")

    # Bloqueia link-local (169.254.x.x) - inclui AWS/GCP metadata endpoint
    if ip.is_link_local:
        raise ValidationError("Endereço link-local não permitido")

    # Bloqueia multicast
    if ip.is_multicast:
        raise ValidationError("Endereço multicast não permitido")

    # Bloqueia IPs reservados/especiais
    if ip.is_reserved:
        raise ValidationError("Endereço reservado não permitido")

    # Bloqueia unspecified (0.0.0.0)
    if ip.is_unspecified:
        raise ValidationError("Endereço não especificado não permitido")

    # Permite apenas IPs privados (redes locais típicas para Pixoo)
    # 10.x.x.x, 172.16-31.x.x, 192.168.x.x
    if not ip.is_private:
        raise ValidationError(
            "Apenas endereços de rede privada são permitidos. "
            "O Pixoo deve estar na mesma rede local."
        )

    return ip_str


# =============================================================================
# Validação de URL YouTube (#4 - Command Injection Protection)
# =============================================================================

# Regex rigorosa para URLs do YouTube
YOUTUBE_URL_PATTERNS = [
    # youtube.com/watch?v=VIDEO_ID
    re.compile(r'^https?://(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})(?:&.*)?$'),
    # youtu.be/VIDEO_ID
    re.compile(r'^https?://(?:www\.)?youtu\.be/([a-zA-Z0-9_-]{11})(?:\?.*)?$'),
    # youtube.com/embed/VIDEO_ID
    re.compile(r'^https?://(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})(?:\?.*)?$'),
    # youtube.com/v/VIDEO_ID
    re.compile(r'^https?://(?:www\.)?youtube\.com/v/([a-zA-Z0-9_-]{11})(?:\?.*)?$'),
    # youtube.com/shorts/VIDEO_ID
    re.compile(r'^https?://(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]{11})(?:\?.*)?$'),
]


def validate_youtube_url(url: str) -> str:
    """
    Valida estritamente uma URL do YouTube e extrai o video ID.

    Validações:
    - URL deve começar com http:// ou https://
    - Domínio deve ser youtube.com ou youtu.be
    - Video ID deve ter exatamente 11 caracteres alfanuméricos + _ e -
    - Rejeita qualquer caractere especial que possa ser usado para injeção

    Args:
        url: URL do YouTube

    Returns:
        Video ID validado (11 caracteres)

    Raises:
        ValidationError: Se URL for inválida ou suspeita
    """
    if not url or not isinstance(url, str):
        raise ValidationError("URL do YouTube não fornecida")

    # Limita tamanho para prevenir DoS
    if len(url) > 500:
        raise ValidationError("URL muito longa")

    # Remove espaços
    url = url.strip()

    # Tenta cada padrão
    for pattern in YOUTUBE_URL_PATTERNS:
        match = pattern.match(url)
        if match:
            video_id = match.group(1)
            # Validação extra do video ID
            if re.match(r'^[a-zA-Z0-9_-]{11}$', video_id):
                return video_id

    raise ValidationError(
        "URL do YouTube inválida. Formatos aceitos:\n"
        "- https://www.youtube.com/watch?v=VIDEO_ID\n"
        "- https://youtu.be/VIDEO_ID"
    )


def sanitize_time_value(value: float, max_duration: float = 3600.0) -> float:
    """
    Sanitiza valor de tempo para prevenir injeção em comandos.

    Args:
        value: Tempo em segundos
        max_duration: Duração máxima permitida (default: 1 hora)

    Returns:
        Tempo sanitizado

    Raises:
        ValidationError: Se valor for inválido
    """
    try:
        time = float(value)
    except (TypeError, ValueError):
        raise ValidationError("Valor de tempo inválido")

    if time < 0:
        raise ValidationError("Tempo não pode ser negativo")

    if time > max_duration:
        raise ValidationError(f"Tempo excede o máximo de {max_duration} segundos")

    # Arredonda para 3 casas decimais (milissegundos)
    return round(time, 3)


# =============================================================================
# Validação de arquivos (suporte)
# =============================================================================

def validate_file_size(size: Optional[int], max_size: int) -> None:
    """
    Valida tamanho de arquivo.

    Args:
        size: Tamanho do arquivo em bytes (pode ser None)
        max_size: Tamanho máximo permitido

    Raises:
        ValidationError: Se arquivo for muito grande
    """
    if size is not None and size > max_size:
        max_mb = max_size // (1024 * 1024)
        raise ValidationError(f"Arquivo muito grande. Limite: {max_mb}MB")


def validate_content_type(content_type: Optional[str], allowed_types: list[str]) -> None:
    """
    Valida content type do arquivo.

    Args:
        content_type: MIME type do arquivo
        allowed_types: Lista de tipos permitidos

    Raises:
        ValidationError: Se tipo não for permitido
    """
    if not content_type or content_type not in allowed_types:
        tipos = ", ".join(t.split("/")[1].upper() for t in allowed_types)
        raise ValidationError(f"Tipo de arquivo inválido. Tipos aceitos: {tipos}")


def is_youtube_shorts(url: str) -> bool:
    """
    Detecta se a URL é de um YouTube Shorts.

    Usa apenas padrão de URL para detecção confiável.
    Evita falsos positivos de vídeos verticais normais.

    Args:
        url: URL do YouTube

    Returns:
        True se for URL de Shorts (/shorts/), False caso contrário
    """
    return '/shorts/' in url


def validate_video_duration(start: float, end: float, max_duration: float) -> float:
    """
    Valida duração de um segmento de vídeo.

    Args:
        start: Tempo inicial em segundos
        end: Tempo final em segundos
        max_duration: Duração máxima permitida

    Returns:
        Duração do segmento

    Raises:
        ValidationError: Se duração for inválida
    """
    duration = end - start

    if duration <= 0:
        raise ValidationError("Tempo final deve ser maior que o inicial")

    # Arredondar para 1 casa decimal para evitar erros de ponto flutuante
    # (ex: 10.0000001 > 10.0 seria True sem arredondamento)
    rounded_duration = round(duration, 1)
    if rounded_duration > max_duration:
        raise ValidationError(f"Duração máxima é {max_duration}s")

    return duration
