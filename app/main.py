"""
Pixoo Manager - Aplicação web local para gerenciar conteúdo no Pixoo 64.

Execute com: python -m app.main
O navegador abrirá automaticamente em http://127.0.0.1:8000
"""

import os
import shutil
import webbrowser
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import HOST, MAX_FILE_SIZE, PORT, STATIC_DIR, TEMPLATES_DIR, TEMP_DIR
from app.routers import connection as connection_router
from app.routers import gif_upload as gif_router
from app.routers import heartbeat as heartbeat_router
from app.routers import media_upload as media_router
from app.routers import youtube as youtube_router
from app.middleware import CSRFMiddleware


# Modo headless (sem abrir browser) para testes/automação
HEADLESS = os.getenv("PIXOO_HEADLESS", "false").lower() == "true"

# Disable auto-shutdown for development (can be set via env var)
AUTO_SHUTDOWN = os.getenv("PIXOO_AUTO_SHUTDOWN", "true").lower() == "true"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia ciclo de vida da aplicação.

    Startup: Abre browser (se não headless), inicia monitor de inatividade
    Shutdown: Limpa arquivos temporários e desconecta do Pixoo
    """
    # Startup
    if not HEADLESS:
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
    try:
        # Desconecta do Pixoo
        from app.services.pixoo_connection import get_pixoo_connection
        conn = get_pixoo_connection()
        if conn.is_connected:
            conn.disconnect()
            print("Desconectado do Pixoo")

        # Limpa diretório temporário
        if TEMP_DIR.exists():
            shutil.rmtree(TEMP_DIR, ignore_errors=True)
            print(f"Diretório temporário limpo: {TEMP_DIR}")

        print("Cleanup concluído com sucesso")
    except Exception as e:
        print(f"Erro no cleanup: {e}")


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
    # 'unsafe-eval' necessário para Alpine.js
    # frame-src para YouTube IFrame API
    # connect-src blob: necessário para Cropper.js processar imagens
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://www.youtube.com https://s.ytimg.com; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob: https://i.ytimg.com https://*.ytimg.com; "
        "font-src 'self'; "
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
app.include_router(gif_router.router)
app.include_router(heartbeat_router.router)
app.include_router(media_router.router)
app.include_router(youtube_router.router)


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
    })


@app.get("/youtube")
async def youtube_page(request: Request):
    """Página de download do YouTube."""
    return templates.TemplateResponse("base.html", {
        "request": request,
        "active_tab": "youtube",
        "max_file_size": MAX_FILE_SIZE,
    })


if __name__ == "__main__":
    print(f"\n  Pixoo Manager rodando em http://{HOST}:{PORT}")
    print("  Pressione Ctrl+C para parar\n")
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
