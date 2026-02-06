"""
Launcher para Pixoo Manager empacotado com py2app.

Este é o entry point do .app. Envolve todo o startup em error handling
para que crashes mostrem um diálogo útil em vez do genérico do macOS.

Imports: apenas stdlib no topo. Tudo do app é importado dentro do try/except.
"""

import os
import platform
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path


def show_error_dialog(title: str, message: str) -> None:
    """Mostra diálogo nativo macOS via osascript (zero dependências Python)."""
    short_msg = message[:500] + "..." if len(message) > 500 else message
    # Escapar para AppleScript: backslash, aspas, e newlines (quebraria a string literal)
    short_msg = (
        short_msg
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "")
        .replace("\n", '" & return & "')
    )
    script = (
        f'display dialog "{short_msg}" '
        f'with title "{title}" '
        f'buttons {{"OK"}} default button "OK" with icon stop'
    )
    try:
        subprocess.run(["osascript", "-e", script], timeout=30)
    except Exception:
        pass  # Se até osascript falhar, nada mais a fazer


def write_crash_log(error: Exception) -> Path:
    """Grava crash log em ~/.pixoo_manager/crash.log."""
    log_dir = Path.home() / ".pixoo_manager"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "crash.log"

    try:
        version = "unknown"
        try:
            from app.__version__ import __version__
            version = __version__
        except Exception:
            pass

        content = (
            f"=== Pixoo Manager Crash Report ===\n"
            f"Date: {datetime.now().isoformat()}\n"
            f"App Version: {version}\n"
            f"Python: {sys.version}\n"
            f"macOS: {platform.mac_ver()[0]}\n"
            f"Architecture: {platform.machine()}\n"
            f"Frozen: {getattr(sys, 'frozen', False)}\n"
            f"Executable: {sys.executable}\n"
            f"\n--- Traceback ---\n"
            f"{traceback.format_exc()}\n"
            f"\n--- sys.path ---\n"
            + "\n".join(sys.path)
            + "\n"
        )
        log_file.write_text(content, encoding="utf-8")
    except Exception:
        pass

    return log_file


def setup_frozen_env() -> None:
    """Configura env vars para app empacotado (antes de qualquer import do app)."""
    frozen = getattr(sys, "frozen", False)
    if frozen != "macosx_app":
        return

    resources_dir = Path(sys.executable).parent.parent / "Resources"

    # ffmpeg bundled
    ffmpeg_path = resources_dir / "bin" / "ffmpeg"
    if ffmpeg_path.exists():
        os.environ["IMAGEIO_FFMPEG_EXE"] = str(ffmpeg_path)
        os.environ["FFMPEG_BINARY"] = str(ffmpeg_path)
        # Adicionar ao PATH (para yt-dlp)
        ffmpeg_dir = str(ffmpeg_path.parent)
        current_path = os.environ.get("PATH", "")
        if ffmpeg_dir not in current_path:
            os.environ["PATH"] = f"{ffmpeg_dir}:{current_path}"


def main() -> None:
    """Entry point principal — toda exceção é capturada."""
    try:
        # Configurar ambiente ANTES de qualquer import do app
        setup_frozen_env()

        # Agora importar e rodar o app
        from app.main import run_app
        run_app()

    except Exception as e:
        log_file = write_crash_log(e)
        error_type = type(e).__name__
        error_msg = str(e)

        dialog_msg = (
            f"O Pixoo Manager encontrou um erro ao iniciar.\n\n"
            f"Erro: {error_type}: {error_msg}\n\n"
            f"Um log detalhado foi salvo em:\n"
            f"{log_file}\n\n"
            f"Envie este arquivo ao desenvolvedor para diagnóstico."
        )
        show_error_dialog("Pixoo Manager - Erro", dialog_msg)
        sys.exit(1)


if __name__ == "__main__":
    main()
