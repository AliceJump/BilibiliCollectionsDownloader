import requests
from flask import Flask, jsonify, request, send_file

app = Flask(__name__)

API_URL = "https://api.bilibili.com/x/vas/dlc_act/lottery_home_detail"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)
REFERER = "https://www.bilibili.com/"
REQUEST_TIMEOUT = 15


@app.route("/")
def index():
    return send_file("index.html")


@app.route("/api/fetch")
def fetch():
    act_id = request.args.get("act_id", "").strip()
    lottery_id = request.args.get("lottery_id", "").strip()

    if not act_id or not lottery_id:
        return jsonify({"code": -1, "message": "缺少参数 act_id 或 lottery_id"}), 400

    if not act_id.isdigit() or not lottery_id.isdigit():
        return jsonify({"code": -1, "message": "act_id 和 lottery_id 必须为数字"}), 400

    try:
        resp = requests.get(
            API_URL,
            params={"act_id": act_id, "lottery_id": lottery_id},
            headers={"User-Agent": USER_AGENT, "Referer": REFERER},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return jsonify(resp.json())
    except requests.Timeout:
        return jsonify({"code": -1, "message": "请求超时，请稍后重试"}), 504
    except requests.RequestException:
        return jsonify({"code": -1, "message": "请求 B 站 API 失败，请稍后重试"}), 502


if __name__ == "__main__":
    print("启动服务器：http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
