"""
Pixoo Manager - Aplicação web local para gerenciar conteúdo no Pixoo 64.

Execute com: python -m app.main
O navegador abrirá automaticamente em http://127.0.0.1:8000
"""

import logging
import os
import shutil
import sys
import threading
import time
import webbrowser
from contextlib import asynccontextmanager

import uvicorn

from app.logging_config import setup_logging

# Session ID único para esta instância do servidor
# Usado para invalidar estado do cliente quando o servidor reinicia
SERVER_SESSION_ID = str(int(time.time()))
from fastapi import FastAPI, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import HOST, MAX_FILE_SIZE, PORT, STATIC_DIR, TEMPLATES_DIR, TEMP_DIR
from app.routers import connection as connection_router
from app.routers import gallery as gallery_router
from app.routers import gif_upload as gif_router
from app.routers import heartbeat as heartbeat_router
from app.routers import media_upload as media_router
from app.routers import rotation as rotation_router
from app.routers import system as system_router
from app.routers import text_display as text_router
from app.routers import youtube as youtube_router
from app.middleware import CSRFMiddleware


# Modo headless (sem abrir browser) para testes/automação
HEADLESS = os.getenv("PIXOO_HEADLESS", "false").lower() == "true"

# Auto-shutdown por inatividade desabilitado por padrão
# Justificativa: menu bar permite encerrar manualmente a qualquer momento
# Para reabilitar: PIXOO_AUTO_SHUTDOWN=true python -m app.main
AUTO_SHUTDOWN = os.getenv("PIXOO_AUTO_SHUTDOWN", "false").lower() == "true"

# Flag interna: quando True, browser é aberto pelo __main__, não pelo lifespan
# Isso permite que o menubar controle quando abrir o browser
_SKIP_BROWSER_IN_LIFESPAN = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia ciclo de vida da aplicação.

    Startup: Abre browser (se não headless), inicia monitor de inatividade
    Shutdown: Limpa arquivos temporários e desconecta do Pixoo
    """
    # Configura logging estruturado
    setup_logging()
    logger = logging.getLogger(__name__)

    # Startup
    logger.info("Pixoo Manager starting...")

    # Abre browser apenas se não headless E não estiver sendo controlado externamente
    if not HEADLESS and not _SKIP_BROWSER_IN_LIFESPAN:
        webbrowser.open(f"http://{HOST}:{PORT}")

    # Start inactivity monitor if enabled
    if AUTO_SHUTDOWN and not HEADLESS:
        heartbeat_router.start_inactivity_monitor()
    else:
        heartbeat_router.disable_auto_shutdown()

    yield

    # Stop inactivity monitor
    heartbeat_router.stop_inactivity_monitor()

    # Shutdown cleanup
    logger.info("Shutting down...")
    try:
        # Parar rotação ativa se existir (antes de desconectar do Pixoo)
        from app.services.rotation_manager import get_rotation_manager
        rotation = get_rotation_manager()
        if rotation.get_status().is_active:
            rotation.stop()
            logger.info("Rotação parada durante shutdown")

        # Desconecta do Pixoo
        from app.services.pixoo_connection import get_pixoo_connection
        conn = get_pixoo_connection()
        if conn.is_connected:
            conn.disconnect()
            logger.info("Desconectado do Pixoo")

        # Limpa diretório temporário
        if TEMP_DIR.exists():
            shutil.rmtree(TEMP_DIR, ignore_errors=True)
            logger.debug(f"Diretório temporário limpo: {TEMP_DIR}")

        logger.info("Cleanup concluído")
    except Exception as e:
        logger.error(f"Erro no cleanup: {e}")


app = FastAPI(
    title="Pixoo Manager",
    description="Gerenciador de conteúdo para Divoom Pixoo 64",
    lifespan=lifespan,
)


# Middleware de proteção CSRF
app.add_middleware(CSRFMiddleware)


# Headers de segurança HTTP
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Adiciona headers de segurança em todas as respostas."""
    response: Response = await call_next(request)

    # Previne clickjacking
    response.headers["X-Frame-Options"] = "DENY"

    # Previne MIME type sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"

    # Habilita proteção XSS do browser
    response.headers["X-XSS-Protection"] = "1; mode=block"

    # Política de referrer
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # Content Security Policy
    # frame-src para YouTube IFrame API
    # connect-src blob: necessário para Cropper.js processar imagens
    # media-src blob: necessário para preview de vídeo no Safari
    # font-src data: necessário para fontes embutidas do YouTube embed
    # unsafe-eval: necessário para Alpine.js avaliar expressões (x-data, x-show, etc.)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://www.youtube.com https://s.ytimg.com; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob: https://i.ytimg.com https://*.ytimg.com; "
        "media-src 'self' blob:; "
        "font-src 'self' data:; "
        "connect-src 'self' blob:; "
        "frame-src https://www.youtube.com; "
        "frame-ancestors 'none'"
    )

    return response


# Configura arquivos estáticos (CSS, JS, imagens)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Configura templates HTML
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Registra routers da API
app.include_router(connection_router.router)
app.include_router(gallery_router.router)
app.include_router(gif_router.router)
app.include_router(heartbeat_router.router)
app.include_router(media_router.router)
app.include_router(rotation_router.router)
app.include_router(system_router.router)
app.include_router(text_router.router)
app.include_router(youtube_router.router)


# Favicon
from fastapi.responses import FileResponse

@app.get("/favicon.ico")
async def favicon():
    """Serve favicon."""
    favicon_path = STATIC_DIR / "favicon.ico"
    if favicon_path.exists():
        return FileResponse(favicon_path)
    return Response(status_code=204)


# Rotas de páginas

@app.get("/")
async def home():
    """Página inicial - redireciona para Mídia."""
    return RedirectResponse(url="/media", status_code=302)


@app.get("/gif")
async def gif_page():
    """Redireciona /gif para /media (tabs unificadas)."""
    return RedirectResponse(url="/media", status_code=302)


@app.get("/media")
async def media_page(request: Request):
    """Página de conversão de foto/vídeo."""
    return templates.TemplateResponse("base.html", {
        "request": request,
        "active_tab": "media",
        "max_file_size": MAX_FILE_SIZE,
        "session_id": SERVER_SESSION_ID,
    })


@app.get("/youtube")
async def youtube_page(request: Request):
    """Página de download do YouTube."""
    return templates.TemplateResponse("base.html", {
        "request": request,
        "active_tab": "youtube",
        "max_file_size": MAX_FILE_SIZE,
        "session_id": SERVER_SESSION_ID,
    })


@app.get("/text")
async def text_page(request: Request):
    """Página de texto scrolling."""
    return templates.TemplateResponse("base.html", {
        "request": request,
        "active_tab": "text",
        "max_file_size": MAX_FILE_SIZE,
        "session_id": SERVER_SESSION_ID,
    })


@app.get("/gallery")
async def gallery_page(request: Request):
    """Página da galeria de GIFs salvos."""
    return templates.TemplateResponse("base.html", {
        "request": request,
        "active_tab": "gallery",
        "max_file_size": MAX_FILE_SIZE,
        "session_id": SERVER_SESSION_ID,
    })


def _run_server():
    """Executa uvicorn em thread separada (para uso com menubar)."""
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


def _wait_for_server(timeout: float = 5.0) -> bool:
    """
    Aguarda o servidor estar pronto.

    Returns:
        True se servidor está pronto, False se timeout
    """
    import socket
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((HOST, PORT), timeout=0.5):
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.1)
    return False


def run_app():
    """
    Executa o Pixoo Manager.

    Chamado pelo launcher.py (py2app) ou pelo bloco __main__ (desenvolvimento).
    """
    global _SKIP_BROWSER_IN_LIFESPAN

    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info(f"Pixoo Manager rodando em http://{HOST}:{PORT}")

    # Tenta usar menu bar no macOS (não-headless)
    if sys.platform == "darwin" and not HEADLESS:
        try:
            from app.menubar import run_menu_bar

            # Indica que browser será aberto aqui, não pelo lifespan
            _SKIP_BROWSER_IN_LIFESPAN = True

            # Servidor em daemon thread (para quando menubar fechar)
            server_thread = threading.Thread(target=_run_server, daemon=True)
            server_thread.start()

            # Aguarda servidor estar pronto
            if _wait_for_server():
                # Abre browser
                webbrowser.open(f"http://{HOST}:{PORT}")

                # Menu bar na main thread (bloqueia até quit)
                logger.info("Menu bar ativo. Use o ícone para encerrar.")
                run_menu_bar(f"http://{HOST}:{PORT}")
            else:
                logger.error("Servidor não iniciou a tempo")
                sys.exit(1)

        except ImportError:
            # rumps não disponível, comportamento normal
            logger.warning("Menu bar não disponível (rumps não instalado)")
            logger.info("Pressione Ctrl+C para parar")
            uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
    else:
        # Não-macOS ou headless
        logger.info("Pressione Ctrl+C para parar")
        uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    run_app()
