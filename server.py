import os
import time
import logging
import requests
from datetime import datetime
from urllib.parse import urlparse, parse_qs
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


# ====== 通过页面网络请求提取参数（参考 main.py get_lottery_url）======

def get_lottery_params_from_page(page_url, chrome_path=None, driver_path=None):
    """
    访问 B 站收藏集页面，通过捕获页面发出的网络请求提取所有 act_id / lottery_id 参数对。
    参考 main.py 的 get_lottery_url() 实现。
    返回: (params_list, error_message)
      - 成功: ([{"act_id": ..., "lottery_id": ...}, ...], None)
      - 失败: (None, "错误说明")
    """
    try:
        from seleniumwire import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
    except ImportError as e:
        LOGGER.error(f"缺少依赖，无法使用页面模式: {e}")
        return None, "服务端缺少 seleniumwire 依赖，请运行 pip install selenium-wire webdriver-manager"

    try:
        chrome_options = Options()
        if chrome_path:
            LOGGER.info(f"使用指定 Chrome 路径: {chrome_path}")
            chrome_options.binary_location = chrome_path
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        seleniumwire_options = {"disable_encoding": True}

        if driver_path:
            LOGGER.info(f"使用指定 ChromeDriver 路径: {driver_path}")
            service = Service(executable_path=driver_path)
        else:
            try:
                from webdriver_manager.chrome import ChromeDriverManager
                LOGGER.info("使用 webdriver-manager 自动下载 ChromeDriver")
                service = Service(ChromeDriverManager().install())
            except ImportError:
                LOGGER.info("webdriver-manager 未安装，尝试使用 PATH 中的 chromedriver")
                service = Service()

        driver = webdriver.Chrome(
            service=service,
            options=chrome_options,
            seleniumwire_options=seleniumwire_options,
        )

        LOGGER.info(f"正在访问页面: {page_url}")
        driver.get(page_url)
        time.sleep(5)

        try:
            WebDriverWait(driver, 10).until(
                EC.frame_to_be_available_and_switch_to_it((By.ID, "mall-iframe"))
            )
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".card-tabs .tab"))
            )
            tabs = driver.find_elements(By.CSS_SELECTOR, ".card-tabs .tab")
            LOGGER.info(f"找到 {len(tabs)} 个 tab，依次点击以触发 API 请求")
            for i in range(len(tabs)):
                tabs = driver.find_elements(By.CSS_SELECTOR, ".card-tabs .tab")
                name_els = tabs[i].find_elements(By.CSS_SELECTOR, ".lottery-name")
                name = name_els[0].text if name_els else f"tab-{i + 1}"
                LOGGER.info(f"点击第 {i + 1} 个 tab: {name}")
                tabs[i].click()
                time.sleep(2)
        except Exception as e:
            LOGGER.warning(f"未找到 tab 结构，直接从已有请求中提取: {e}")

        target_urls = []
        for req in driver.requests:
            if (
                req.response
                and "lottery_home_detail" in req.url
                and req.url not in target_urls
            ):
                target_urls.append(req.url)

        driver.quit()
        LOGGER.info(f"共捕获到 {len(target_urls)} 个 lottery_home_detail 请求")

        if not target_urls:
            LOGGER.warning("未捕获到 lottery_home_detail 请求")
            return None, "未在页面网络请求中找到 lottery_home_detail，请确认链接正确"

        params_list = []
        for url in target_urls:
            LOGGER.info(f"解析请求 URL: {url}")
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)
            act = qs.get("act_id", [None])[0]
            lot = qs.get("lottery_id", [None])[0]
            if act and lot:
                params_list.append({"act_id": act, "lottery_id": lot})
                LOGGER.info(f"提取参数: act_id={act}, lottery_id={lot}")
            else:
                LOGGER.warning(f"请求 URL 缺少有效参数，跳过: {url}")

        if not params_list:
            return None, "捕获的请求 URL 中未包含有效的 act_id 或 lottery_id"

        return params_list, None

    except Exception as e:
        LOGGER.error(f"通过页面获取参数失败: {e}", exc_info=True)
        return None, "通过页面获取参数时发生错误，请查看服务端日志了解详情"


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
    访问 B 站收藏集页面，从页面网络请求中提取所有 act_id / lottery_id 参数对。
    参数:
      url         — B 站收藏集页面 URL（必填）
      chrome_path — Chrome 浏览器可执行文件路径（可选，留空则自动检测）
      driver_path — ChromeDriver 可执行文件路径（可选，留空则自动检测）
    """
    page_url = request.args.get("url", "").strip()
    chrome_path = request.args.get("chrome_path", "").strip() or None
    driver_path = request.args.get("driver_path", "").strip() or None

    LOGGER.info(
        f"/api/get_params 收到请求: url={page_url!r}, "
        f"chrome_path={chrome_path!r}, driver_path={driver_path!r}"
    )

    if not page_url:
        LOGGER.warning("/api/get_params 缺少 url 参数")
        return jsonify({"code": -1, "message": "缺少参数 url"}), 400

    params_list, error = get_lottery_params_from_page(page_url, chrome_path, driver_path)
    if error:
        LOGGER.error(f"获取页面参数失败: {error}")
        return jsonify({"code": -1, "message": error}), 500

    LOGGER.info(f"成功提取 {len(params_list)} 个参数对: {params_list}")
    return jsonify({"code": 0, "data": params_list})


if __name__ == "__main__":
    print("启动服务器：http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
