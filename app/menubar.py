"""
Menu bar integration for macOS.

Provides a menu bar icon with options to open browser and quit the app.
"""

import json
import logging
import urllib.request
import webbrowser

logger = logging.getLogger(__name__)


def create_menu_bar(server_url: str = "http://127.0.0.1:8000"):
    """
    Create and run the menu bar app.

    This should be called from the main thread on macOS.
    The server should run in a separate thread.

    Args:
        server_url: URL of the local server
    """
    try:
        import rumps
    except ImportError:
        logger.warning("rumps not installed. Menu bar disabled.")
        return None

    class PixooMenuBar(rumps.App):
        def __init__(self):
            super().__init__("Pixoo", quit_button=None)
            self.server_url = server_url
            self.menu = [
                rumps.MenuItem("Abrir no navegador", callback=self.open_browser),
                None,  # Separator
                rumps.MenuItem("Verificar Atualizações", callback=self.check_update),
                rumps.MenuItem("Desinstalar...", callback=self.uninstall),
                None,  # Separator
                rumps.MenuItem("Encerrar", callback=self.quit_app),
            ]

        def open_browser(self, _):
            """Open the web interface in default browser."""
            webbrowser.open(self.server_url)

        def check_update(self, _):
            """Check for updates via API and show result."""
            try:
                req = urllib.request.Request(
                    f"{self.server_url}/api/system/check-update",
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode("utf-8"))

                if data.get("error"):
                    rumps.alert(
                        title="Erro ao verificar",
                        message=data["error"]
                    )
                elif data.get("update_available"):
                    response = rumps.alert(
                        title="Atualização disponível!",
                        message=f"Versão {data['latest_version']} disponível.\n"
                                f"Você está usando a versão {data['current_version']}.",
                        ok="Baixar",
                        cancel="Depois"
                    )
                    if response == 1:  # OK button clicked
                        webbrowser.open(data["release_url"])
                else:
                    rumps.alert(
                        title="Você está atualizado!",
                        message=f"Versão {data['current_version']} é a mais recente."
                    )
            except Exception as e:
                logger.error(f"Erro ao verificar atualizações: {e}")
                rumps.alert(
                    title="Erro",
                    message="Não foi possível verificar atualizações."
                )

        def uninstall(self, _):
            """Confirm and run uninstall."""
            response = rumps.alert(
                title="Desinstalar Pixoo Manager?",
                message="Isso removerá os dados do usuário (~/.pixoo_manager/).\n\n"
                        "Para remoção completa, delete também o app.",
                ok="Desinstalar",
                cancel="Cancelar"
            )
            if response != 1:  # Cancel clicked
                return

            try:
                req = urllib.request.Request(
                    f"{self.server_url}/api/system/uninstall",
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))

                if data.get("success"):
                    size_mb = data.get("deleted_size_bytes", 0) / (1024 * 1024)
                    rumps.alert(
                        title="Dados removidos!",
                        message=f"Removido: {data['deleted_path']}\n"
                                f"Tamanho: {size_mb:.1f} MB\n\n"
                                "Para completar, delete o Pixoo Manager.app."
                    )
                else:
                    rumps.alert(
                        title="Erro ao desinstalar",
                        message=data.get("error", "Erro desconhecido")
                    )
            except Exception as e:
                logger.error(f"Erro ao desinstalar: {e}")
                rumps.alert(
                    title="Erro",
                    message="Não foi possível desinstalar."
                )

        def quit_app(self, _):
            """Quit the application via graceful shutdown."""
            try:
                req = urllib.request.Request(
                    f"{self.server_url}/api/system/shutdown",
                    method="POST"
                )
                urllib.request.urlopen(req, timeout=2)
            except Exception:
                # Fallback: quit direto se endpoint falhar
                rumps.quit_application()

    return PixooMenuBar()


def run_menu_bar(server_url: str = "http://127.0.0.1:8000"):
    """
    Run the menu bar app (blocking).

    This should be called from the main thread.
    """
    app = create_menu_bar(server_url)
    if app:
        app.run()
