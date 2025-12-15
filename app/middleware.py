"""
Middleware de segurança para o Pixoo Manager.

Inclui:
- Validação de Origin (CSRF protection)
- Rate limiting para operações pesadas
"""

from collections import defaultdict
from time import time
from typing import Callable, Optional, Set

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


# =============================================================================
# CSRF Protection (#3)
# =============================================================================

# Origens permitidas (localhost apenas)
ALLOWED_ORIGINS: Set[str] = {
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://127.0.0.1",
    "http://localhost",
    # Permite requisições sem Origin (curl, Postman, etc)
    None,
    "",
}


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    Middleware para proteção CSRF via validação de Origin.

    Para aplicações locais, valida que requisições state-changing
    vêm apenas de localhost.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Apenas valida métodos que modificam estado
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            origin = request.headers.get("origin", "")

            # Permite se não tem origin (requests diretos)
            # ou se origin é localhost
            if origin and origin not in ALLOWED_ORIGINS:
                # Verifica se é localhost com porta diferente
                if not self._is_localhost_origin(origin):
                    raise HTTPException(
                        status_code=403,
                        detail="Origin não permitido. Requisições devem vir de localhost."
                    )

        return await call_next(request)

    def _is_localhost_origin(self, origin: str) -> bool:
        """Verifica se origin é uma variante de localhost."""
        localhost_prefixes = (
            "http://127.0.0.1",
            "http://localhost",
            "https://127.0.0.1",
            "https://localhost",
        )
        return any(origin.startswith(prefix) for prefix in localhost_prefixes)


# =============================================================================
# Rate Limiting (#5)
# =============================================================================

class RateLimiter:
    """
    Rate limiter simples em memória.

    Usa janela deslizante para controlar número de requisições.
    """

    def __init__(self, max_requests: int, window_seconds: int):
        """
        Args:
            max_requests: Máximo de requisições permitidas na janela
            window_seconds: Tamanho da janela em segundos
        """
        self.max_requests = max_requests
        self.window = window_seconds
        self.requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str = "global") -> bool:
        """
        Verifica se uma requisição é permitida.

        Args:
            key: Identificador para o rate limit (IP, endpoint, etc)

        Returns:
            True se permitido, False se limite excedido
        """
        now = time()

        # Remove requisições fora da janela
        self.requests[key] = [
            t for t in self.requests[key]
            if now - t < self.window
        ]

        # Verifica limite
        if len(self.requests[key]) >= self.max_requests:
            return False

        # Registra nova requisição
        self.requests[key].append(now)
        return True

    def get_retry_after(self, key: str = "global") -> Optional[int]:
        """
        Retorna quantos segundos até poder fazer nova requisição.

        Args:
            key: Identificador para o rate limit

        Returns:
            Segundos para esperar, ou None se não está limitado
        """
        if not self.requests[key]:
            return None

        now = time()
        oldest = min(self.requests[key])
        retry_after = int(self.window - (now - oldest)) + 1

        return max(0, retry_after)


# Rate limiters para diferentes operações
# Mais restritivo para operações mais pesadas

# Descoberta de rede: 3 requisições por minuto (cria 100 threads)
discover_limiter = RateLimiter(max_requests=3, window_seconds=60)

# Conversão de vídeo: 5 requisições por minuto (CPU intensivo)
convert_limiter = RateLimiter(max_requests=5, window_seconds=60)

# Download YouTube: 5 requisições por minuto (bandwidth)
youtube_limiter = RateLimiter(max_requests=5, window_seconds=60)

# Upload GIF: 10 requisições por minuto (menos intensivo)
upload_limiter = RateLimiter(max_requests=10, window_seconds=60)


def check_rate_limit(limiter: RateLimiter, key: str = "global") -> None:
    """
    Verifica rate limit e levanta HTTPException se excedido.

    Args:
        limiter: RateLimiter a usar
        key: Chave para o rate limit

    Raises:
        HTTPException: 429 se limite excedido
    """
    if not limiter.is_allowed(key):
        retry_after = limiter.get_retry_after(key)
        raise HTTPException(
            status_code=429,
            detail=f"Muitas requisições. Tente novamente em {retry_after} segundos.",
            headers={"Retry-After": str(retry_after)} if retry_after else None
        )
