"""
app.py — B 站收藏集下载器桌面客户端入口

运行方式：
  python app.py          # 启动 pywebview 原生窗口（默认）
  python app.py --cli    # 退回命令行交互模式（同 main.py）

打包方式（生成单 EXE）：
  pip install pyinstaller pywebview
  pyinstaller build.spec
"""

import sys
import threading
import socket

# ── 命令行模式直接转发给 main.py ──────────────────────────────────────
if "--cli" in sys.argv:
    import main  # noqa: F401 — execution happens at module level
    sys.exit(0)

# ── 正常 GUI 模式 ──────────────────────────────────────────────────────
import os
import webview
from server import app as flask_app  # reuse existing Flask app


def _resource_path(relative: str) -> str:
    """Return absolute path, compatible with PyInstaller's --onefile bundle."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)


def _get_free_port() -> int:
    """Bind to port 0 to let the OS allocate a free ephemeral port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_flask(port: int) -> None:
    """Run Flask in a daemon thread so it exits when the main thread exits."""
    flask_app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


def main():
    port = _get_free_port()

    flask_thread = threading.Thread(target=_start_flask, args=(port,), daemon=True)
    flask_thread.start()

    # Give Flask a moment to bind before opening the window
    import time
    time.sleep(0.5)

    window = webview.create_window(
        title="B 站收藏集下载器",
        url=f"http://127.0.0.1:{port}/",
        width=1100,
        height=820,
        resizable=True,
        min_size=(760, 560),
    )

    # Use the EdgeChromium backend on Windows when available; fall back to default
    gui = "edgechromium" if sys.platform == "win32" else None
    webview.start(gui=gui)


if __name__ == "__main__":
    main()
