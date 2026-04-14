"""
run_web.py — 启动本地网页版（仅Flask服务，不弹窗）

用法：
  python run_web.py
然后用浏览器访问 http://127.0.0.1:5000/
"""
from server import app

if __name__ == "__main__":
    print("本地网页版已启动：http://127.0.0.1:5000/")
    app.run(host="127.0.0.1", port=5000, debug=False)
