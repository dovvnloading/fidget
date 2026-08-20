"""Native WebView2 host and controller-process supervisor."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx

from .config import AppConfig

ICON_PATH = Path(__file__).resolve().parents[1] / "assets" / "fidget.ico"
APP_USER_MODEL_ID = "Fidget.LocalMusicStudio"


def _claim_app_identity() -> None:
    """Stop Windows from treating this window as "just another python.exe".

    Without an explicit AppUserModelID, Windows derives one from the process's
    exe path, and the taskbar button's icon follows THAT identity's shell
    icon (python.exe's) rather than the window's live HICON -- so even after
    Form.Icon is corrected (see _apply_window_icon, which fixes the title bar
    and Alt-Tab), the taskbar button itself keeps showing the Python logo.
    Giving the process its own identity, before any window exists, is what
    lets the taskbar button follow our icon instead.
    """
    if os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        pass


def _apply_window_icon(window: Any) -> None:
    """Replace the title bar / taskbar / Alt-Tab icon with Fidget's own mark.

    pywebview has no supported way to do this on Windows. Its `icon` kwarg
    to webview.start() is only ever read by the GTK and QT backends
    (webview/platforms/{gtk,qt}.py); the WinForms backend used here via
    gui="edgechromium" ignores it entirely and always sets Form.Icon by
    extracting icon 0 from sys.executable (webview/platforms/winforms.py),
    which is why the venv's python.exe icon shows up everywhere instead.
    `window.native` is the underlying WinForms.Form pywebview already
    created (assigned to it in BrowserForm.__init__), so once the window
    exists we override its .Icon directly.
    """
    if os.name != "nt" or not ICON_PATH.exists():
        return
    try:
        import clr

        clr.AddReference("System.Drawing")
        from System.Drawing import Icon as NetIcon

        native = window.native
        if native is not None:
            native.Icon = NetIcon(str(ICON_PATH))
    except Exception:
        pass  # Cosmetic only -- never block the app over a missing icon.


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_server(url: str, process: subprocess.Popen[bytes], timeout: float = 45) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Fidget controller exited during startup with code {process.returncode}")
        try:
            if httpx.get(f"{url}/api/health", timeout=1).is_success:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.15)
    raise RuntimeError("Fidget's lightweight controller did not start within 45 seconds")


def _terminate(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            capture_output=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    else:
        process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


def _tail(path: Path, limit: int = 5000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return text[-limit:]
    except OSError:
        return ""


def run_desktop() -> None:
    """Keep WebView2 and the FastAPI controller in independent processes."""

    _claim_app_identity()
    config = AppConfig.from_environment()
    config.ensure_directories()
    host = "127.0.0.1"
    port = int(os.getenv("FIDGET_APP_PORT", "0")) or _free_port()
    url = f"http://{host}:{port}"
    controller_log = config.logs_dir / "controller.log"
    creation_flags = (
        getattr(subprocess, "CREATE_NO_WINDOW", 0)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    )
    with controller_log.open("ab", buffering=0) as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "fidget.backend.server",
                "--host",
                host,
                "--port",
                str(port),
            ],
            cwd=config.project_root,
            env=os.environ.copy(),
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=creation_flags,
        )
        try:
            _wait_for_server(url, process)
        except Exception as exc:
            _terminate(process)
            detail = _tail(controller_log)
            suffix = f"\n\nController log:\n{detail}" if detail else ""
            raise RuntimeError(f"{exc}{suffix}") from exc

        if os.getenv("FIDGET_HEADLESS", "false").lower() in {"1", "true", "yes"}:
            try:
                process.wait()
            except KeyboardInterrupt:
                _terminate(process)
            return

        import webview

        window_options: dict[str, Any] = {
            "title": "Fidget — Local Music Studio",
            "url": url,
            "width": 1480,
            "height": 940,
            "min_size": (1040, 720),
            "background_color": "#141412",
            "text_select": True,
        }
        window = webview.create_window(**window_options)
        # before_show, not shown: it runs synchronously on the WinForms UI
        # thread and fires before .Show() creates the taskbar button, so the
        # icon is already correct by the time Explorer registers it. shown
        # runs later on a spawned thread -- the title bar still ends up
        # correct (WM_SETICON always redraws it), but the taskbar button
        # keeps its original icon because Explorer doesn't reliably refresh
        # an already-created button's glyph from a later icon change.
        window.events.before_show += lambda: _apply_window_icon(window)
        try:
            webview.start(gui="edgechromium", debug=os.getenv("FIDGET_DEBUG") == "1")
        finally:
            _terminate(process)
