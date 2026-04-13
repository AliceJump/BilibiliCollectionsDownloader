import os
import logging
import requests
from datetime import datetime
from flask import Flask, jsonify, request, send_file

app = Flask(__name__)

API_URL = "https://api.bilibili.com/x/vas/dlc_act/lottery_home_detail"
LOTTERY_LIST_API = "https://api.bilibili.com/x/vas/dlc_act/lottery_list"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)
REFERER = "https://www.bilibili.com/"
REQUEST_TIMEOUT = 15
APP_NAME = "biliCollectionDownloader"


# ====== 日志管理（与 main.py 保持一致）======

class LazyErrorHandler(logging.Handler):
    """延迟创建错误日志文件，只有有错误时才创建"""

    def __init__(self, app_name, log_dir="logs"):
        super().__init__(level=logging.ERROR)
        self.app_name = app_name
        self.log_dir = log_dir
        self.handler = None

    def emit(self, record):
        if not self.handler:
            os.makedirs(self.log_dir, exist_ok=True)
            date_str = datetime.now().strftime("%Y-%m-%d")
            err_file = os.path.join(self.log_dir, f"{self.app_name}_{date_str}.error.log")
            self.handler = logging.FileHandler(err_file, encoding="utf-8")
            formatter = logging.Formatter(
                "[%(asctime)s] [%(levelname)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            self.handler.setFormatter(formatter)
        self.handler.emit(record)


def setup_logger(app_name: str, log_dir="logs"):
    os.makedirs(log_dir, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(log_dir, f"{app_name}_{date_str}.log")

    logger = logging.getLogger(app_name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    lazy_error_handler = LazyErrorHandler(app_name, log_dir)

    if not logger.handlers:
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        logger.addHandler(lazy_error_handler)

    return logger


LOGGER = setup_logger(APP_NAME)


# ====== 通过 lottery_list 接口查询所有分组参数 ======

def get_lottery_params_by_act_id(act_id):
    """
    调用 B 站 lottery_list 接口，根据 act_id 获取该活动下所有分组的 lottery_id。
    无需 Chrome 或任何浏览器依赖。
    返回: (params_list, error_message)
      - 成功: ([{"act_id": ..., "lottery_id": ...}, ...], None)
      - 失败: (None, "错误说明")
    """
    try:
        LOGGER.info(f"正在查询 lottery 列表: act_id={act_id}")
        resp = requests.get(
            LOTTERY_LIST_API,
            params={"act_id": act_id},
            headers={"User-Agent": USER_AGENT, "Referer": REFERER},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        LOGGER.info(
            f"lottery_list API 返回: code={data.get('code')}, message={data.get('message')!r}"
        )

        if data.get("code") != 0:
            return None, f"B站API错误: {data.get('message', '未知错误')}"

        # Handle multiple possible response shapes
        result_data = data.get("data") or {}
        lottery_list = (
            result_data.get("lottery_list")
            or result_data.get("list")
            or (result_data if isinstance(result_data, list) else [])
        )

        if not lottery_list:
            LOGGER.warning(f"lottery_list API 未返回分组数据: {data}")
            return None, "未找到收藏集分组信息，请确认 act_id 是否正确"

        params_list = []
        for lottery in lottery_list:
            if not isinstance(lottery, dict):
                continue
            lot_id = lottery.get("lottery_id") or lottery.get("id")
            if lot_id:
                params_list.append({"act_id": str(act_id), "lottery_id": str(lot_id)})
                LOGGER.info(f"提取参数: act_id={act_id}, lottery_id={lot_id}")

        if not params_list:
            return None, "返回数据中未包含有效的 lottery_id"

        return params_list, None

    except requests.Timeout:
        LOGGER.error(f"查询 lottery 列表超时: act_id={act_id}")
        return None, "请求超时，请稍后重试"
    except requests.RequestException as e:
        LOGGER.error(f"查询 lottery 列表失败: {e}")
        return None, "请求 B 站 API 失败，请稍后重试"
    except Exception as e:
        LOGGER.error(f"处理 lottery 列表失败: {e}", exc_info=True)
        return None, "查询时发生错误，请查看服务端日志了解详情"


# ====== Flask 路由 ======

@app.route("/")
def index():
    return send_file("index.html")


@app.route("/api/fetch")
def fetch():
    act_id = request.args.get("act_id", "").strip()
    lottery_id = request.args.get("lottery_id", "").strip()
    LOGGER.info(f"/api/fetch 收到请求: act_id={act_id!r}, lottery_id={lottery_id!r}")

    if not act_id or not lottery_id:
        LOGGER.warning("缺少参数 act_id 或 lottery_id")
        return jsonify({"code": -1, "message": "缺少参数 act_id 或 lottery_id"}), 400

    if not act_id.isdigit() or not lottery_id.isdigit():
        LOGGER.warning(f"参数格式错误: act_id={act_id!r}, lottery_id={lottery_id!r}")
        return jsonify({"code": -1, "message": "act_id 和 lottery_id 必须为数字"}), 400

    try:
        LOGGER.info(f"向 B 站 API 发起请求: act_id={act_id}, lottery_id={lottery_id}")
        resp = requests.get(
            API_URL,
            params={"act_id": act_id, "lottery_id": lottery_id},
            headers={"User-Agent": USER_AGENT, "Referer": REFERER},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        LOGGER.info(
            f"B 站 API 返回: code={data.get('code')}, message={data.get('message')!r}"
        )
        return jsonify(data)
    except requests.Timeout:
        LOGGER.error(f"请求 B 站 API 超时: act_id={act_id}, lottery_id={lottery_id}")
        return jsonify({"code": -1, "message": "请求超时，请稍后重试"}), 504
    except requests.RequestException as e:
        LOGGER.error(f"请求 B 站 API 失败: {e}")
        return jsonify({"code": -1, "message": "请求 B 站 API 失败，请稍后重试"}), 502


@app.route("/api/get_params")
def get_params():
    """
    根据 act_id 调用 B 站 lottery_list 接口，获取该活动下所有分组的 lottery_id。
    参数:
      act_id — 活动 ID（必填）
    无需 Chrome 或任何浏览器依赖。
    """
    act_id = request.args.get("act_id", "").strip()

    LOGGER.info(f"/api/get_params 收到请求: act_id={act_id!r}")

    if not act_id:
        LOGGER.warning("/api/get_params 缺少 act_id 参数")
        return jsonify({"code": -1, "message": "缺少参数 act_id"}), 400

    if not act_id.isdigit():
        LOGGER.warning(f"/api/get_params act_id 格式错误: {act_id!r}")
        return jsonify({"code": -1, "message": "act_id 必须为数字"}), 400

    params_list, error = get_lottery_params_by_act_id(act_id)
    if error:
        LOGGER.error(f"获取 lottery 列表失败: {error}")
        return jsonify({"code": -1, "message": error}), 500

    LOGGER.info(f"成功提取 {len(params_list)} 个参数对: {params_list}")
    return jsonify({"code": 0, "data": params_list})


if __name__ == "__main__":
    print("启动服务器：http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
