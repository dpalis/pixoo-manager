"""
Menu bar integration for macOS.

Provides a menu bar icon with options to open browser and quit the app.
"""

import urllib.request
import webbrowser


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
        print("rumps not installed. Menu bar disabled.")
        return None

    class PixooMenuBar(rumps.App):
        def __init__(self):
            super().__init__("Pixoo", quit_button=None)
            self.server_url = server_url
            self.menu = [
                rumps.MenuItem("Abrir no navegador", callback=self.open_browser),
                None,  # Separator
                rumps.MenuItem("Encerrar", callback=self.quit_app),
            ]

        def open_browser(self, _):
            """Open the web interface in default browser."""
            webbrowser.open(self.server_url)

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
