import os
import time
import requests
import cv2
from pyzbar.pyzbar import decode
from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import hashlib
from urllib.parse import urlparse, parse_qs
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import logging

# ====== 使用须知 ======
'''
1. 自行搜索并安装依赖库：pyzbar, seleniumwire, opencv-python, requests, selenium
2. 下载并配置 Chrome 浏览器，下载并配置 ChromeDriver(自行寻找chromedriver和对应chrome版本)，下载并配置 B 站收藏集二维码图片(收藏集页面点分享后保存的分享二维码)
3. 修改 CHROME_BROWSER_PATH, CHROME_DRIVER_PATH, QRCODE_IMAGE_PATH 三个常量
'''

# ====== 常量配置 ======
CHROME_BROWSER_PATH = r"chrome-win64\chrome.exe"
CHROME_DRIVER_PATH = r"chromedriver.exe"

VIDEO_WATER_TYPE = False
VIDEO_NO_WATER_TYPE = False

API_URL = "https://api.bilibili.com/x/vas/dlc_act/lottery_home_detail"
REFERER = "https://www.bilibili.com/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"

APP_NAME = "biliCollectionDownloader"


# ====== 日志管理 ======


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

    # 控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # 普通日志文件
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    # 延迟错误日志
    lazy_error_handler = LazyErrorHandler(app_name, log_dir)

    if not logger.handlers:
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        logger.addHandler(lazy_error_handler)

    return logger


# 使用
LOGGER = setup_logger("biliCollectionDownloader")


# ====== 工具函数 ======
def is_url(string):
    pattern = re.compile(r'^(https?|ftp)://[^\s/$.?#].\S*$', re.IGNORECASE)
    return re.match(pattern, string) is not None


# ====== 下载器类 ======
class Downloader:
    def __init__(self, base_dir="dlc"):
        self.base_dir = base_dir
        self.headers = {"Referer": REFERER, "User-Agent": USER_AGENT}
        self.err_list = []

    def download(self, category, whole_name, name, file_url, ext):
        dir_path = os.path.join(self.base_dir, whole_name, category)
        os.makedirs(dir_path, exist_ok=True)

        base_filename = f"{name}.{ext}"
        filename = base_filename
        file_path = os.path.join(dir_path, filename)

        try:
            if os.path.exists(file_path):
                existing_size = os.path.getsize(file_path)
                response = requests.get(file_url, headers=self.headers, stream=True, timeout=10)
                response.raise_for_status()
                remote_size = int(response.headers.get("Content-Length", 0))
                response.close()
                if existing_size == remote_size:
                    LOGGER.info(f"文件已存在且大小相同，跳过下载：{file_path}")
                    return
                else:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"{name}_{timestamp}.{ext}"
                    file_path = os.path.join(dir_path, filename)

            LOGGER.info(f"开始下载 {category}：{file_path}")
            response = requests.get(file_url, headers=self.headers, stream=True)
            response.raise_for_status()
            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            LOGGER.info(f"{category.capitalize()}下载完成：{file_path}")
        except Exception as e:
            LOGGER.error(f"下载 {category} 失败：{file_path}", exc_info=True)
            self.err_list.append(f"{file_path} | {e}")

    def err_list_save(self):
        if not self.err_list:
            LOGGER.info("没有失败下载需要记录")
            return
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"download_failed_{timestamp}.log"
        path = os.path.join(log_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(self.err_list))
        LOGGER.warning(f"失败下载列表已保存：{path}")


# ====== 功能函数 ======
def scan_qr_code_from_full_image(image_path):
    LOGGER.info(f"正在扫描二维码：{image_path}")
    img = cv2.imread(image_path)
    if img is None:
        LOGGER.error("二维码图片读取失败，请检查图片路径")
        return None
    decoded_objects = decode(img)
    for obj in decoded_objects:
        if obj.type == 'QRCODE':
            qr_url = obj.data.decode('utf-8')
            LOGGER.info(f"扫描到 URL: {qr_url}")
            return qr_url
    LOGGER.warning("未检测到二维码")
    return None


def get_lottery_url(page_url):
    try:
        chrome_options = Options()
        chrome_options.binary_location = CHROME_BROWSER_PATH
        service = Service(executable_path=CHROME_DRIVER_PATH)
        chrome_options.add_argument("--headless")
        seleniumwire_options = {'disable_encoding': True}
        driver = webdriver.Chrome(
            service=service,
            options=chrome_options,
            seleniumwire_options=seleniumwire_options
        )

        LOGGER.info(f"访问 URL：{page_url}")
        driver.get(page_url)
        time.sleep(5)
        WebDriverWait(driver, 10).until(
            EC.frame_to_be_available_and_switch_to_it((By.ID, "mall-iframe"))
        )
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".card-tabs .tab"))
        )
        tabs = driver.find_elements(By.CSS_SELECTOR, ".card-tabs .tab")
        LOGGER.info(f"找到 {len(tabs)} 个 tab")
        for i in range(len(tabs)):
            tabs = driver.find_elements(By.CSS_SELECTOR, ".card-tabs .tab")
            name = tabs[i].find_element(By.CSS_SELECTOR, ".lottery-name").text
            LOGGER.info(f"点击第 {i + 1} 个 tab：{name}")
            tabs[i].click()
            time.sleep(2)

        target_url = []
        count = 0
        for request in driver.requests:
            if count == len(tabs):
                break
            if request.response and "lottery_home_detail" in request.url and request.url not in target_url:
                target_url.append(request.url)
                count += 1

        driver.quit()
        if target_url:
            query_params_list = []
            for target_ur in target_url:
                LOGGER.info(f"找到请求链接：{target_ur}")
                parsed_url = urlparse(target_ur)
                query_params = parse_qs(parsed_url.query)
                LOGGER.info(f"提取参数：{query_params}")
                query_params_list.append(query_params)
            return query_params_list
        else:
            LOGGER.warning("未找到 lottery_home_detail 请求")
            return None
    except Exception as e:
        LOGGER.error(f"获取 lottery URL 失败: {e}", exc_info=True)
        return None


def extract_card_downloads(card, video_type):
    video_urls, water_mark_video_urls, image_urls = [], [], []

    # 视频下载
    if video_type[1]:
        temp = card.get("video_list")
        if temp:
            video_urls.append((card.get("card_name", "unnamed"), temp[0]))

    if video_type[0]:
        temp = card.get("video_list_download")
        if temp:
            water_mark_video_urls.append((card.get("card_name", "unnamed"), temp[0]))

    # 图片下载
    image_url = card.get("card_img")
    if image_url:
        image_urls.append((card.get("card_name", "unnamed"), image_url))

    return video_urls, water_mark_video_urls, image_urls


def safe_filename(name: str) -> str:
    """处理文件名，替换非法字符"""
    name = name.replace("·", "_").replace(" ", "_")
    return re.sub(r'[<>:"/\\|?*]', '_', name)



def get_download_url(act_id, lottery_id, video_type=(True, True)):
    """
    获取活动视频和图片下载链接
    video_type = (watermark, normal) 是否获取水印/无水印视频
    返回: name, video_urls, image_urls, water_mark_video_urls
    """
    try:
        response = requests.get(API_URL, params={"act_id": act_id, "lottery_id": lottery_id},
                                headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        data = response.json().get("data", {})
        if not isinstance(data, dict):
            LOGGER.error(f"API 返回的数据不是字典: {data}")
            return None, [], [], []

        name = data.get("name", "未知活动名称")
        video_urls, water_mark_video_urls, image_urls = [], [], []

        # 处理 item_list
        item_list = data.get("item_list", [])
        if isinstance(item_list, list):
            for item in item_list:
                if not isinstance(item, dict):
                    continue
                card = item.get("card_info")
                if isinstance(card, dict):
                    v, wv, iv = extract_card_downloads(card, video_type)
                    video_urls.extend(v)
                    water_mark_video_urls.extend(wv)
                    image_urls.extend(iv)

        # 处理 collect_infos
        collect_list = data.get("collect_list", {})
        collect_infos = collect_list.get("collect_infos", []) if isinstance(collect_list, dict) else []
        if isinstance(collect_infos, list):
            for collect in collect_infos:
                if not isinstance(collect, dict):
                    continue
                card_item = collect.get("card_item")
                if not isinstance(card_item, dict):
                    continue
                card = card_item.get("card_type_info")
                if not isinstance(card, dict):
                    continue

                # 提取下载链接
                v, wv, iv = extract_card_downloads(card, video_type)
                video_urls.extend(v)
                water_mark_video_urls.extend(wv)
                image_urls.extend(iv)

        LOGGER.info(f"活动名称：{name}")
        LOGGER.info(f"视频链接数：{len(video_urls)}，带水印视频数：{len(water_mark_video_urls)}，图片数：{len(image_urls)}")
        return name, video_urls, image_urls, water_mark_video_urls

    except requests.RequestException as e:
        LOGGER.error(f"请求 API 失败: {e}")
    except Exception as e:
        LOGGER.error(f"解析下载链接失败: {e}", exc_info=True)

    return None, [], [], []


def deduplicate_videos_by_hash(video_dir, chunk_size=8 * 1024 * 1024):
    """
    对视频文件夹内的 mp4 文件按内容去重。
    chunk_size: 每次读取的字节数，默认 8MB
    """
    LOGGER.info(f"开始视频去重：{video_dir}")
    hash_map = {}

    for root, _, files in os.walk(video_dir):
        for file in files:
            if not file.lower().endswith(".mp4"):
                continue
            path = os.path.join(root, file)
            try:
                md5 = hashlib.md5()
                with open(path, "rb") as f:
                    while chunk := f.read(chunk_size):
                        md5.update(chunk)
                file_hash = md5.hexdigest()

                if file_hash in hash_map:
                    LOGGER.info(f"删除重复文件：{path}")
                    os.remove(path)
                else:
                    hash_map[file_hash] = path
            except Exception as e:
                LOGGER.warning(f"处理文件出错：{path} | {e}")

    LOGGER.info("视频去重完成")


def load_url(page_url):
    query_params_list = get_lottery_url(page_url)
    if not query_params_list:
        LOGGER.error("获取参数失败，无法继续操作")
        return
    for query_params in query_params_list:
        name, video_urls, image_urls, water_mark_video_urls = get_download_url(
            query_params['act_id'][0],
            query_params['lottery_id'][0],
            [VIDEO_WATER_TYPE, VIDEO_NO_WATER_TYPE]
        )
        if not video_urls and not image_urls:
            LOGGER.error("未获取到有效下载链接")
            return
        whole_name = name
        downloader = Downloader()
        for video_name, video_url in video_urls:
            downloader.download("video", whole_name, video_name, video_url, "mp4")
        for water_name, water_url in water_mark_video_urls:
            downloader.download("watermark_video", whole_name, water_name, water_url, "mp4")
        for img_name, img_url in image_urls:
            downloader.download("img", whole_name, img_name, img_url, "png")
        downloader.err_list_save()
        deduplicate_videos_by_hash(os.path.join(downloader.base_dir, whole_name, "video"))
        deduplicate_videos_by_hash(os.path.join(downloader.base_dir, whole_name, "watermark_video"))


# ====== 主程序 ======
# ====== 主程序入口 ======
if __name__ == "__main__":
    switch = input("选择方式\n1. 扫描 qrcodes 文件夹\n2. 读取 urls.txt\n请输入选择: ")
    urls = []

    video_water_type = input("选择视频类型\n1. 无水印低质量\n2. 有水印高质量\n输入如 '12' 表示两者: ")
    if "1" in video_water_type:
        VIDEO_NO_WATER_TYPE = True
    if "2" in video_water_type:
        VIDEO_WATER_TYPE = True

    if switch == "1":
        directory = 'qrcodes'
        os.makedirs(directory, exist_ok=True)  # 文件夹不存在则创建
        image_files = [f for f in os.listdir(directory) if f.lower().endswith(('.jpg', '.png'))]

        if not image_files:
            LOGGER.warning(f"{directory} 文件夹中没有图片，已创建空文件夹，等待添加二维码图片")

        for qrcode_img in image_files:
            text = scan_qr_code_from_full_image(os.path.join(directory, qrcode_img))
            if text and is_url(text.strip()):
                urls.append(text.strip())

    elif switch == "2":
        urls_file = 'urls.txt'
        if not os.path.exists(urls_file):
            LOGGER.warning(f"{urls_file} 不存在，已创建空文件")
            with open(urls_file, "w", encoding="utf-8") as f:
                f.write("")  # 创建空文件

        with open(urls_file, 'r', encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and is_url(line):
                    urls.append(line)

    LOGGER.info(f"找到 {len(urls)} 个 URL")
    for url in urls:
        load_url(url)

    LOGGER.info("全部操作完成")
