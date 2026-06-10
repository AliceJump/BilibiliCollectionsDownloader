"""
run_web.py — 启动本地网页版（仅Flask服务，不弹窗）

用法：
  python run_web.py
然后用浏览器访问 http://127.0.0.1:5000/
"""
import os
import sys

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from server import app

if __name__ == "__main__":
    import socket
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    print(f"本地网页版已启动：http://127.0.0.1:5000/")
    print(f"局域网访问：http://{local_ip}:5000/  （请确保防火墙已放行 5000 端口）")
    app.run(host="0.0.0.0", port=5000, debug=False)
