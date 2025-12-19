"""Logging configuration for Pixoo Manager."""

import logging
import sys


def setup_logging(level: int = logging.INFO) -> None:
    """Configure structured logging for the application.

    Args:
        level: Logging level (default: INFO)
    """
    # Formato com timestamp, nível e contexto
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Root logger
    root = logging.getLogger()
    root.setLevel(level)

    # Evitar handlers duplicados
    if not root.handlers:
        root.addHandler(handler)

    # Reduzir ruído de dependências
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('moviepy').setLevel(logging.WARNING)
