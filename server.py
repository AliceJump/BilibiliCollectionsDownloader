import mimetypes
import os
import logging
import hashlib
import json
import re
import time
import random
from datetime import datetime
from urllib.parse import quote, urlparse, unquote

import requests as req_lib
from flask import Flask, Response, jsonify, request, send_file

from bilibili_api import sync, ResponseCodeException, NetworkException
from bilibili_api.garb import DLC
from bilibili_api.utils.network import Api
from bilibili_api.utils.utils import get_api

app = Flask(__name__)

_GARB_API = get_api("garb")
APP_NAME = "biliCollectionDownloader"

# ============================================================
# B站 API 安全请求层（防 412 风控）
# ============================================================

BILI_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
    "Origin": "https://www.bilibili.com",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Connection": "keep-alive",
}

BILI_COOKIES = {
    "SESSDATA": os.environ.get("BILI_SESSDATA", ""),
    "buvid3": os.environ.get("BILI_BUVID3", ""),
    "b_nut": os.environ.get("BILI_BNUT", ""),
}

# 如果没有环境变量则尝试从文件读取
if not BILI_COOKIES["SESSDATA"]:
    cookie_file = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "configs",
    "bili_cookies.json"
)
    if os.path.exists(cookie_file):
        try:
            with open(cookie_file, "r", encoding="utf-8") as f:
                file_cookies = json.load(f)
                BILI_COOKIES.update({k: v for k, v in file_cookies.items() if v})
        except Exception:
            pass

_bili_session = req_lib.Session()
_bili_session.headers.update(BILI_HEADERS)

# 请求间隔控制（防止触发风控）
_last_request_time = 0.0
_MIN_REQUEST_INTERVAL = 0.8  # 最短 800ms 一个请求


def _bili_rate_limit():
    """请求限速：确保请求间隔不小于 _MIN_REQUEST_INTERVAL 秒"""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < _MIN_REQUEST_INTERVAL:
        sleep_time = _MIN_REQUEST_INTERVAL - elapsed + random.uniform(0, 0.3)
        time.sleep(sleep_time)
    _last_request_time = time.time()


def _is_412_response(resp):
    """检测响应是否为 B站 412 风控页面"""
    if resp.status_code == 412:
        return True
    text_head = resp.text[:200].lower()
    if resp.status_code == 200 and ("出错啦" in text_head or "安全风控" in text_head):
        return True
    return False


def bili_request(url, **kwargs):
    """
    带 Cookie + 完整请求头 + 限速 + 重试 的 B站 API 请求。
    返回: (response_json | None, error_message | None)
    """
    _bili_rate_limit()

    timeout = kwargs.pop("timeout", 15)
    max_retry = kwargs.pop("max_retry", 3)
    cookies = kwargs.pop("cookies", None) or BILI_COOKIES

    for attempt in range(max_retry):
        try:
            resp = _bili_session.get(
                url,
                cookies=cookies,
                timeout=timeout,
                **kwargs,
            )

            if _is_412_response(resp):
                LOGGER.warning(f"[retry {attempt + 1}/{max_retry}] 触发 B站 412 风控: {url}")
                if attempt < max_retry - 1:
                    time.sleep(1.5 + attempt * 1.0)
                continue

            if resp.status_code != 200:
                LOGGER.warning(
                    f"[retry {attempt + 1}/{max_retry}] HTTP {resp.status_code}: {url}"
                )
                if attempt < max_retry - 1:
                    time.sleep(0.5)
                continue

            # 检查是否返回了 HTML（某些情况 200 但返回风控页）
            ct = (resp.headers.get("Content-Type", "") or "").lower()
            if "html" in ct and "json" not in ct:
                LOGGER.warning(
                    f"[retry {attempt + 1}/{max_retry}] 返回 HTML 页面，疑似风控: {url}"
                )
                if attempt < max_retry - 1:
                    time.sleep(1.0 + attempt * 0.5)
                continue

            return resp.json(), None

        except req_lib.exceptions.Timeout:
            LOGGER.warning(f"[retry {attempt + 1}/{max_retry}] 请求超时: {url}")
            if attempt < max_retry - 1:
                time.sleep(1.0)
        except req_lib.exceptions.ConnectionError as e:
            LOGGER.warning(f"[retry {attempt + 1}/{max_retry}] 连接错误: {e}")
            if attempt < max_retry - 1:
                time.sleep(1.0)
        except Exception as e:
            LOGGER.error(f"请求失败 (不可重试): {url} | {e}")
            return None, str(e)

    return None, f"请求失败，已重试 {max_retry} 次，可能触发了 B站 风控(412)"


def safe_request(func, fallback_msg="请求失败"):
    """统一异常包装器，防止 Flask 500"""
    try:
        return func()
    except Exception as e:
        LOGGER.error(f"[safe_request] {fallback_msg}: {e}", exc_info=True)
        return None


# ====== 图片代理接口 ======

@app.route("/api/proxy_img")
def proxy_img():
    """
    代理图片请求，解决B站图片 Referer 防盗链问题。
    同时保留原始文件名，避免浏览器保存成 proxy_img.png

    用法：
        /api/proxy_img?url=xxx
    """

    url = request.args.get("url", "").strip()

    if not url or not (url.startswith("http://") or url.startswith("https://")):
        return jsonify({
            "code": -1,
            "message": "缺少或错误的url参数"
        }), 400

    try:
        headers = {
            "Referer": "https://www.bilibili.com/",
            "User-Agent": _RESOLVE_HEADERS["User-Agent"]
        }

        resp = req_lib.get(
            url,
            headers=headers,
            stream=True,
            timeout=10
        )

        resp.raise_for_status()

        # Content-Type
        content_type = resp.headers.get("Content-Type")

        if not content_type:
            ext = url.split(".")[-1].lower()
            content_type = (
                mimetypes.guess_type("file." + ext)[0]
                or "image/jpeg"
            )

        # =========================
        # 提取原始文件名
        # =========================

        parsed = urlparse(url)

        filename = os.path.basename(parsed.path)

        # URL 解码
        filename = unquote(filename)

        # 防止空文件名
        if not filename:
            ext = mimetypes.guess_extension(content_type) or ".jpg"
            filename = f"image{ext}"

        # =========================
        # 返回代理内容
        # =========================

        return Response(
            resp.raw.read(),
            content_type=content_type,
            headers={
                # inline = 浏览器内显示
                # attachment = 强制下载
                "Content-Disposition": f'inline; filename="{filename}"'
            }
        )

    except Exception as e:
        LOGGER.error(
            f"图片代理失败: {url} | {e}",
            exc_info=True
        )

        return jsonify({
            "code": -1,
            "message": "图片代理失败"
        }), 502
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


# ====== 通过 bilibili-api 库查询收藏集分组参数 ======

def get_lottery_params_by_act_id(act_id):
    """
    调用 bilibili-api 库的 DLC.get_info()，根据 act_id 获取该活动下所有分组的 lottery_id。
    使用 /x/vas/dlc_act/act/basic 接口，无需凭据或浏览器依赖。
    返回: (params_list, error_message)
      - 成功: ([{"act_id": ..., "lottery_id": ...}, ...], None)
      - 失败: (None, "错误说明")
    """
    try:
        # 限速：bilibili_api 内部也有自己的网络层，加延迟减少 412
        _bili_rate_limit()
        LOGGER.info(f"正在查询收藏集信息: act_id={act_id}")
        dlc = DLC(int(act_id))
        info = sync(dlc.get_info())

        lottery_list = info.get("lottery_list") or []
        if not lottery_list:
            LOGGER.warning(f"act/basic 未返回分组数据: {info}")
            return None, "未找到收藏集分组信息，请确认 act_id 是否正确"

        params_list = []
        for lottery in lottery_list:
            if not isinstance(lottery, dict):
                continue
            lot_id = lottery.get("lottery_id")
            goods_id = lottery.get("goods_id") or ""
            if lot_id:
                params_list.append({
                    "act_id": str(act_id),
                    "lottery_id": str(lot_id),
                    "goods_id": str(goods_id),
                })
                LOGGER.info(f"提取参数: act_id={act_id}, lottery_id={lot_id}, goods_id={goods_id}")

        if not params_list:
            return None, "返回数据中未包含有效的 lottery_id"

        return params_list, None

    except ResponseCodeException as e:
        LOGGER.error(f"B站API错误 (act_id={act_id}): code={e.code}, msg={e.msg}")
        return None, f"B站API错误: {e.msg}"
    except NetworkException as e:
        LOGGER.error(f"网络请求失败 (act_id={act_id}): {e}")
        return None, "请求超时或网络错误，请稍后重试"
    except Exception as e:
        LOGGER.error(f"查询收藏集信息失败: {e}", exc_info=True)
        return None, "查询时发生错误，请查看服务端日志了解详情"


# ====== Flask 路由 ======

_BILI_FETCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
}


def _fetch_suit_components(item_id: int) -> list:
    """
    调用 B 站装扮组件接口查询表情包等附加资源。
    https://api.bilibili.com/x/garb/v2/user/suit/benefit?item_id={id}&part=emoji_package
    返回: [{"type": "emoji", "name": ..., "images": {"static": ..., "gif": ...}}, ...]
    """
    try:
        _bili_rate_limit()
        url = f"https://api.bilibili.com/x/garb/v2/user/suit/benefit?item_id={item_id}&part=emoji_package"
        resp = _bili_session.get(url, timeout=10)
        if resp.status_code != 200:
            return []
        data = resp.json()
        if data.get("code") != 0 or not data.get("data"):
            return []
        d = data["data"]
        items = []
        # Emoji from properties.item_emoji_list
        prop_emoji = d.get("properties", {}).get("item_emoji_list")
        if prop_emoji:
            try:
                emoji_list = json.loads(prop_emoji) if isinstance(prop_emoji, str) else prop_emoji
                for em in emoji_list:
                    items.append({
                        "type": "emoji",
                        "name": em.get("name", ""),
                        "images": {
                            "static": em.get("image", ""),
                            "gif": em.get("image_gif", ""),
                            "webp": em.get("image_webp", ""),
                        }
                    })
            except Exception:
                pass
        # Emoji from suit_items.emoji
        suit_emoji = d.get("suit_items", {}).get("emoji", [])
        for em in suit_emoji:
            props = em.get("properties", {})
            items.append({
                "type": "emoji",
                "name": em.get("name", ""),
                "images": {
                    "static": props.get("image", ""),
                    "gif": props.get("image_gif", ""),
                    "webp": props.get("image_webp", ""),
                }
            })
        return items
    except Exception:
        LOGGER.warning(f"获取表情包失败: item_id={item_id}", exc_info=True)
        return []


@app.route("/")
def index():
    return send_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html"))


@app.route("/api/fetch")
def fetch():
    act_id = request.args.get("act_id", "").strip()
    lottery_id = request.args.get("lottery_id", "").strip()
    goods_id = request.args.get("goods_id", "").strip()
    LOGGER.info(f"/api/fetch 收到请求: act_id={act_id!r}, lottery_id={lottery_id!r}, goods_id={goods_id!r}")

    if not act_id or not lottery_id:
        LOGGER.warning("缺少参数 act_id 或 lottery_id")
        return jsonify({"code": -1, "message": "缺少参数 act_id 或 lottery_id"}), 400

    if not act_id.isdigit() or not lottery_id.isdigit():
        LOGGER.warning(f"参数格式错误: act_id={act_id!r}, lottery_id={lottery_id!r}")
        return jsonify({"code": -1, "message": "act_id 和 lottery_id 必须为数字"}), 400

    try:
        # 限速
        _bili_rate_limit()
        LOGGER.info(f"通过 bilibili-api 获取收藏集详情: act_id={act_id}, lottery_id={lottery_id}")
        api = _GARB_API["dlc"]["detail"]
        data = sync(
            Api(**api).update_params(act_id=int(act_id), lottery_id=int(lottery_id)).result
        )
        LOGGER.info(f"收藏集详情获取成功: act_id={act_id}, lottery_id={lottery_id}")

        # 如果提供了 goods_id，尝试获取表情包等附加资源
        if goods_id and goods_id.isdigit():
            try:
                emoji_items = _fetch_suit_components(int(goods_id))
                if emoji_items:
                    data["_emoji_packages"] = emoji_items
                    LOGGER.info(f"获取到 {len(emoji_items)} 个表情包: act_id={act_id}")
            except Exception as emoji_err:
                LOGGER.warning(f"获取表情包失败(不影响主数据): {emoji_err}")

        return jsonify({"code": 0, "message": "0", "data": data})
    except ResponseCodeException as e:
        LOGGER.error(f"B站API错误 (act_id={act_id}, lottery_id={lottery_id}): code={e.code}, msg={e.msg}")
        return jsonify({"code": e.code, "message": e.msg}), 400
    except NetworkException as e:
        LOGGER.error(f"网络请求失败 (act_id={act_id}, lottery_id={lottery_id}): {e}")
        return jsonify({"code": -1, "message": "请求超时或网络错误，请稍后重试"}), 504
    except Exception as e:
        LOGGER.error(f"获取收藏集详情失败: {e}", exc_info=True)
        return jsonify({"code": -1, "message": "请求 B 站 API 失败，请稍后重试"}), 502


@app.route("/api/get_params")
def get_params():
    """
    根据 act_id 通过 bilibili-api 库查询收藏集基本信息，返回所有分组的 lottery_id。
    参数:
      act_id — 活动 ID（必填）
    使用 /x/vas/dlc_act/act/basic 接口，无需凭据或浏览器依赖。
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


@app.route("/api/search_collections")
def search_collections():
    """
    按关键词搜索 B 站装扮商城中的收藏集活动。
    参考 Collection-Down 的搜索逻辑，仅保留可转换为 act_id 的 dlc_act / ip 结果。
    """
    key_word = request.args.get("key_word", "").strip()
    page = request.args.get("page", "1").strip() or "1"
    LOGGER.info(f"/api/search_collections 收到请求: key_word={key_word!r}, page={page!r}")

    if not key_word:
        return jsonify({"code": -1, "message": "缺少参数 key_word"}), 400

    if not page.isdigit() or int(page) < 1:
        return jsonify({"code": -1, "message": "page 必须为正整数"}), 400

    url = (
        "https://api.bilibili.com/x/garb/v2/mall/home/search"
        f"?key_word={quote(key_word)}&pn={page}"
    )
    raw, error = bili_request(url, timeout=12, max_retry=3)
    if error:
        LOGGER.error(f"搜索收藏集失败: {error}")
        return jsonify({"code": -1, "message": error}), 502

    if raw.get("code") != 0:
        LOGGER.warning(f"B站搜索接口错误: code={raw.get('code')}, message={raw.get('message')}")
        return jsonify({"code": raw.get("code", -1), "message": raw.get("message") or "B站搜索接口返回错误"}), 502

    result_list = []
    for item in ((raw.get("data") or {}).get("list") or []):
        if not isinstance(item, dict):
            continue
        props = item.get("properties") or {}
        item_type = props.get("type")
        if item_type not in ("ip", "dlc_act"):
            continue

        act_id = str(props.get("dlc_act_id") or "").strip()
        if (not act_id or not act_id.isdigit()) and item_type == "dlc_act" and item.get("item_id"):
            act_id = str(item.get("item_id"))

        if not act_id or not act_id.isdigit() or act_id == "0":
            continue

        sub_ids = []
        fan_item_ids = str(props.get("fan_item_ids") or "").strip()
        if fan_item_ids:
            sub_ids = [part.strip() for part in fan_item_ids.split(",") if part.strip().isdigit()]
        else:
            lottery_id = str(props.get("dlc_lottery_id") or "").strip()
            if lottery_id.isdigit() and lottery_id != "0":
                sub_ids = [lottery_id]

        result_list.append({
            "name": item.get("name") or act_id,
            "act_id": act_id,
            "type": item_type,
            "sub_ids": sub_ids,
            "cover": props.get("image_cover") or "",
        })

    return jsonify({"code": 0, "data": result_list})


def _available_act_ids_path():
    logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    return os.path.join(logs_dir, "available_act_ids.json")


def _read_available_act_ids():
    path = _available_act_ids_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict) and str(item.get("act_id", "")).isdigit()]
    except Exception:
        LOGGER.warning("读取可用 act_id 记录失败", exc_info=True)
    return []


@app.route("/api/available_act_ids", methods=["GET", "POST"])
def available_act_ids():
    """读取或追加扫描确认可用的 act_id。"""
    if request.method == "GET":
        return jsonify({"code": 0, "data": _read_available_act_ids()})

    payload = request.get_json(silent=True) or {}
    act_id = str(payload.get("act_id") or "").strip()
    name = str(payload.get("name") or "").strip()
    if not act_id.isdigit() or act_id == "0":
        return jsonify({"code": -1, "message": "act_id 必须为正整数"}), 400

    items = _read_available_act_ids()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    found = False
    for item in items:
        if str(item.get("act_id")) == act_id:
            if name:
                item["name"] = name
            item["updated_at"] = now
            found = True
            break
    if not found:
        items.append({"act_id": act_id, "name": name or act_id, "created_at": now, "updated_at": now})

    items.sort(key=lambda item: int(item.get("act_id") or 0))
    with open(_available_act_ids_path(), "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    return jsonify({"code": 0, "data": {"act_id": act_id, "count": len(items)}})


_RESOLVE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
}


@app.route("/api/check_login")
def check_login():
    """
    检查当前是否已登录（是否有有效的 SESSDATA Cookie）。
    返回:
      {"code": 0, "data": {"logged_in": true/false}}
    """
    sess = BILI_COOKIES.get("SESSDATA", "").strip()
    logged_in = bool(sess)
    LOGGER.info(f"/api/check_login: logged_in={logged_in}")
    return jsonify({"code": 0, "data": {"logged_in": logged_in}})


@app.route("/api/check_act_id")
def check_act_id():
    """
    快速检查单个 act_id 是否存在。
    使用 requests.Session + Cookie + 完整请求头 + 重试机制，避免 412 风控。
    参数:
      act_id — 活动 ID（必填）
    返回:
      {"code": 0, "data": {"act_id": "...", "exists": true/false, "name": "..."}}
      或 {"code": -1, "message": "..."}
    """
    act_id = request.args.get("act_id", "").strip()
    LOGGER.info(f"/api/check_act_id 收到请求: act_id={act_id!r}")

    if not act_id or not act_id.isdigit():
        return jsonify({"code": -1, "message": "act_id 必须为数字"}), 400

    # 使用 bilibili_api 的 DLC.get_info()（已内置必要请求头），配合限速防风控
    try:
        _bili_rate_limit()
        dlc = DLC(int(act_id))
        info = sync(dlc.get_info())
        lottery_list = info.get("lottery_list") or []
        name = info.get("name") or info.get("title") or ""
        exists = len(lottery_list) > 0
        LOGGER.info(f"检查 act_id={act_id}: exists={exists}, name={name!r}")
        return jsonify({
            "code": 0,
            "data": {
                "act_id": act_id,
                "exists": exists,
                "name": name if exists else "",
            }
        })
    except ResponseCodeException as e:
        LOGGER.warning(f"act_id={act_id} 不存在: code={e.code}, msg={e.msg}")
        return jsonify({
            "code": 0,
            "data": {"act_id": act_id, "exists": False, "name": ""}
        })
    except NetworkException as e:
        err_str = str(e)
        if "412" in err_str or "状态码：412" in err_str:
            LOGGER.error(f"B站风控拦截 (act_id={act_id}): 触发了 412 安全策略")
            return jsonify({"code": -1, "message": "B站风控拦截(412)，请求过于频繁，请稍后重试"}), 412
        LOGGER.error(f"网络请求失败 (act_id={act_id}): {e}")
        return jsonify({"code": -1, "message": "请求超时或网络错误"}), 504
    except Exception as e:
        LOGGER.error(f"检查 act_id={act_id} 失败: {e}", exc_info=True)
        return jsonify({"code": -1, "message": "查询时发生错误"}), 502


@app.route("/api/resolve_url")
def resolve_url():
    """
    跟随 HTTP 重定向，返回最终落地 URL。
    供前端解析 b23.tv 等短链接，以提取 act_id。
    参数:
      url — 待解析的 URL（必填，必须以 http:// 或 https:// 开头）
    """
    url = request.args.get("url", "").strip()
    LOGGER.info(f"/api/resolve_url 收到请求: url={url!r}")

    if not url:
        return jsonify({"code": -1, "message": "缺少参数 url"}), 400

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return jsonify({"code": -1, "message": "url 必须以 http:// 或 https:// 开头"}), 400

    try:
        resp = req_lib.head(
            url,
            allow_redirects=True,
            timeout=10,
            headers=_RESOLVE_HEADERS,
        )
        final_url = resp.url
        LOGGER.info(f"URL 解析成功: {url!r} → {final_url!r}")
        return jsonify({"code": 0, "url": final_url})
    except req_lib.exceptions.Timeout:
        LOGGER.error(f"URL 解析超时: {url!r}")
        return jsonify({"code": -1, "message": "请求超时，请稍后重试"}), 504
    except Exception as e:
        LOGGER.error(f"URL 解析失败: {url!r} | {e}", exc_info=True)
        return jsonify({"code": -1, "message": "URL 解析失败"}), 502


@app.route("/api/save_zip", methods=["POST"])
def save_zip():
    """
    接收前端上传的 ZIP 文件并保存到应用的 `downloads` 目录。
    前端应提交 multipart/form-data，字段名为 `file`，可选 `filename`。
    返回 JSON: {code:0, path: saved_path}
    """
    try:
        file = request.files.get("file")
        filename = request.form.get("filename") or (file.filename if file else None) or "archive.zip"

        # 安全化文件名
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        filename = filename.strip() or 'archive.zip'

        save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, filename)

        if file:
            file.save(save_path)
        else:
            # 如果没有 multipart 文件，尝试写入原始请求体
            with open(save_path, "wb") as fh:
                fh.write(request.get_data())

        LOGGER.info(f"已保存压缩包: {save_path}")
        return jsonify({"code": 0, "path": save_path})
    except Exception as e:
        LOGGER.error("保存 ZIP 失败", exc_info=True)
        return jsonify({"code": -1, "message": "保存失败"}), 500


def _sanitize_name(name: str, default_name: str) -> str:
    value = (name or "").strip()
    value = re.sub(r'[<>:"/\\|?*]', '_', value)
    value = value.strip(" .")
    return value or default_name


def _unique_file_path(dir_path: str, filename: str) -> str:
    name, ext = os.path.splitext(filename)
    candidate = os.path.join(dir_path, filename)
    index = 1
    while os.path.exists(candidate):
        candidate = os.path.join(dir_path, f"{name}({index}){ext}")
        index += 1
    return candidate


def _sha256_file(file_path: str) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            if chunk:
                hasher.update(chunk)
    return hasher.hexdigest()


def _find_duplicate_by_hash(dir_path: str, file_hash: str, exclude_path: str = "") -> str:
    exclude_abs = os.path.abspath(exclude_path) if exclude_path else ""
    for name in os.listdir(dir_path):
        candidate = os.path.join(dir_path, name)
        if not os.path.isfile(candidate):
            continue
        if exclude_abs and os.path.abspath(candidate) == exclude_abs:
            continue
        try:
            if _sha256_file(candidate) == file_hash:
                return candidate
        except Exception:
            continue
    return ""


def _save_single_link(item: dict, root_dir: str) -> dict:
    type_folder_map = {
        "dl-a-img": "img",
        "dl-a-vid": "video",
        "dl-a-wm": "watermark_video",
    }

    if not isinstance(item, dict):
        raise ValueError("item 不是对象")

    raw_url = (item.get("url") or "").strip()
    if not raw_url or not (raw_url.startswith("http://") or raw_url.startswith("https://")):
        raise ValueError("url 无效")

    item_type = (item.get("type") or "").strip()
    folder_name = type_folder_map.get(item_type, "other")

    collection_name = _sanitize_name(item.get("collectionFolder") or "", "未知合集")
    target_dir = os.path.join(root_dir, collection_name, folder_name)
    os.makedirs(target_dir, exist_ok=True)

    parsed_url = urlparse(raw_url)
    raw_basename = os.path.basename(parsed_url.path)
    fallback_name = unquote(raw_basename) if raw_basename else "resource.bin"
    file_name = _sanitize_name(item.get("filename") or "", fallback_name)
    save_path = _unique_file_path(target_dir, file_name)

    headers = {
        "Referer": "https://www.bilibili.com/",
        "User-Agent": _RESOLVE_HEADERS["User-Agent"],
    }

    with req_lib.get(raw_url, headers=headers, stream=True, timeout=(8, 30)) as resp:
        resp.raise_for_status()
        hasher = hashlib.sha256()
        with open(save_path, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    fh.write(chunk)
                    hasher.update(chunk)

    content_hash = hasher.hexdigest()
    duplicated_path = _find_duplicate_by_hash(target_dir, content_hash, save_path)
    if duplicated_path:
        try:
            os.remove(save_path)
        except Exception:
            pass
        return {
            "code": 0,
            "path": duplicated_path,
            "filename": os.path.basename(duplicated_path),
            "hash": content_hash,
            "duplicate": True,
        }

    return {
        "code": 0,
        "path": save_path,
        "filename": os.path.basename(save_path),
        "hash": content_hash,
        "duplicate": False,
    }


@app.route("/api/save_file", methods=["POST"])
def save_file():
    """
    应用模式保存单个文件，供前端逐个调用实现实时进度展示。
    """
    payload = request.get_json(silent=True) or {}
    item = payload.get("item")
    root_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
    os.makedirs(root_dir, exist_ok=True)

    try:
        result = _save_single_link(item, root_dir)
        result["root_dir"] = root_dir
        return jsonify(result)
    except Exception as e:
        LOGGER.error(f"保存单文件失败: error={e}", exc_info=True)
        return jsonify({"code": -1, "message": str(e), "root_dir": root_dir}), 500


@app.route("/api/save_files", methods=["POST"])
def save_files():
    """
    应用模式批量下载并按目录保存文件。
    目录结构：downloads/<合集名>/<类型目录>/<文件名>
    """
    payload = request.get_json(silent=True) or {}
    links = payload.get("links") or []

    if not isinstance(links, list) or not links:
        return jsonify({"code": -1, "message": "缺少 links 参数"}), 400

    root_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
    os.makedirs(root_dir, exist_ok=True)

    saved_count = 0
    failed_count = 0
    duplicate_count = 0
    results = []

    for i, item in enumerate(links):
        try:
            one = _save_single_link(item, root_dir)
            saved_count += 1
            if one.get("duplicate"):
                duplicate_count += 1
            results.append({
                "index": i,
                **one,
            })
        except Exception as e:
            failed_count += 1
            LOGGER.error(f"保存文件失败: index={i}, error={e}", exc_info=True)
            results.append({
                "index": i,
                "code": -1,
                "message": str(e),
            })

    code = 0 if saved_count > 0 else -1
    message = "完成" if failed_count == 0 else f"部分失败: {failed_count}"
    return jsonify({
        "code": code,
        "message": message,
        "root_dir": root_dir,
        "total": len(links),
        "saved_count": saved_count,
        "failed_count": failed_count,
        "duplicate_count": duplicate_count,
        "results": results,
    })


if __name__ == "__main__":
    import socket
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    print(f"启动服务器：http://127.0.0.1:5000")
    print(f"局域网访问：http://{local_ip}:5000/  （请确保防火墙已放行 5000 端口）")
    app.run(host="0.0.0.0", port=5000, debug=False)
