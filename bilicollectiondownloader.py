import os
import time
import requests
import cv2
from pyzbar.pyzbar import decode
from seleniumwire import webdriver
from urllib.parse import urlparse, parse_qs
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import logging
import hashlib

# ====== 使用须知 ======
'''
1. 自行搜索并安装依赖库：pyzbar, seleniumwire, opencv-python, requests, selenium
2. 下载并配置 Chrome 浏览器，下载并配置 ChromeDriver(自行寻找chromedriver和对应chrome版本)，下载并配置 B 站收藏集二维码图片(收藏集页面点分享后保存的分享二维码)
3. 修改 CHROME_BROWSER_PATH, CHROME_DRIVER_PATH, QRCODE_IMAGE_PATH 三个常量
4. 配置ffmpeg环境或者禁用main函数最后一条语句
'''

# ====== 常量配置 ======
'''
以下三个常量请自行配置
'''
# Chrome 浏览器的可执行程序路径，用于告诉 Selenium 使用哪个浏览器
CHROME_BROWSER_PATH = r"C:\Users\26309\OneDrive\desktop\Python\os\chrome_test\chrome-win64\chrome.exe"

# ChromeDriver 的路径，是与 Chrome 浏览器匹配的 WebDriver 控制工具
CHROME_DRIVER_PATH = r"C:\Users\26309\OneDrive\desktop\Python\os\chrome_test\chromedriver.exe"

# 存放收藏集二维码图片的路径，程序从该文件中读取并识别二维码内容
QRCODE_IMAGE_PATH = r"QRcode.png"
# VIDEO_WATER_TYPE=True为下载高质量水印版，VIDEO_WATER_TYPE=False为下载无水印版低质量
VIDEO_WATER_TYPE=False

'''
以下两个常量请勿自行配置
'''
# B 站收藏集接口的 URL，通过该接口获取包含视频下载地址的 JSON 数据
API_URL = "https://api.bilibili.com/x/vas/dlc_act/lottery_home_detail"

# 请求视频下载链接时所需的 Referer，模拟从 B 站页面发出的请求
REFERER = "https://www.bilibili.com/"

# 浏览器 User-Agent 字符串，用于伪装请求头，防止被目标服务器识别为机器人
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"

# ====== 配置日志 ======
# 配置日志输出格式
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class Downloader:
    def __init__(self, base_dir="dlc"):
        self.base_dir = base_dir
        self.headers = {
            "Referer": REFERER,
            "User-Agent": USER_AGENT
        }

    def download(self, category, whole_name, name, url, ext):
        """
        category: 'video' or 'img'
        whole_name: 活动名，用作子文件夹名
        name: 文件基础名
        url: 下载地址
        ext: 文件扩展名，如 'mp4' 或 'png'
        """
        dir_path = os.path.join(self.base_dir, whole_name, category)
        os.makedirs(dir_path, exist_ok=True)

        base_filename = f"{name}.{ext}"
        filename = base_filename
        file_path = os.path.join(dir_path, filename)

        try:
            # 检查是否已存在
            if os.path.exists(file_path):
                existing_size = os.path.getsize(file_path)
                response = requests.head(url, headers=self.headers)
                response.raise_for_status()
                remote_size = int(response.headers.get("Content-Length", 0))

                if existing_size == remote_size:
                    logger.info(f"文件已存在且大小相同，跳过下载：{file_path.replace(os.sep, '/')}")
                    return
                else:
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    filename = f"{name}_{timestamp}.{ext}"
                    file_path = os.path.join(dir_path, filename)

            logger.info(f"开始下载{category}：{file_path.replace(os.sep, '/')}")
            response = requests.get(url, headers=self.headers, stream=True)
            response.raise_for_status()

            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info(f"{category.capitalize()}下载完成：{file_path.replace(os.sep, '/')}")
        except Exception as e:
            logger.error(f"下载{category}失败：{file_path.replace(os.sep, '/')}, URL: {url}, 错误: {e}")

# ====== 功能函数 ======
def extract_images_and_videos(data,type):
    image_urls = []  # 存储所有图片的列表
    video_urls = []  # 存储所有视频的列表

    # 遍历 collect_infos
    for collect_info in data['collect_list']['collect_infos']:
        # 检查是否存在 card_item 和 card_type_info
        if collect_info.get('card_item'):
            card_info = collect_info['card_item']
            card_type_info = card_info.get('card_type_info')

            # 提取图片
            overview_image_url = card_type_info.get('overview_image')
            if overview_image_url:
                image_urls.append(overview_image_url)
            # 提取视频
            animation=card_type_info.get('animation')



    return image_urls, video_urls

# a) 扫描二维码并提取 URL
def scan_qr_code_from_full_image(image_path):
    logger.info(f"正在扫描二维码，路径：{image_path}")
    img = cv2.imread(image_path)
    if img is None:
        logger.error("二维码图片读取失败，请检查图片路径！")
        return None
    decoded_objects = decode(img)
    for obj in decoded_objects:
        if obj.type == 'QRCODE':
            url = obj.data.decode('utf-8')
            logger.info(f"扫描到的 URL: {url}")
            return url
    logger.warning("未检测到二维码！")
    return None

# b) 用 Selenium 获取请求 URL 并提取参数
def get_lottery_url(url):
    try:
        chrome_options = Options()
        chrome_options.binary_location = CHROME_BROWSER_PATH
        service = Service(executable_path=CHROME_DRIVER_PATH)

        seleniumwire_options = {'disable_encoding': True}
        driver = webdriver.Chrome(
            service=service,
            options=chrome_options,
            seleniumwire_options=seleniumwire_options
        )

        logger.info(f"正在访问 URL：{url}")
        driver.get(url)
        time.sleep(5)

        target_url = None
        for request in driver.requests:
            if request.response and "lottery_home_detail" in request.url:
                target_url = request.url
                break

        driver.quit()

        if target_url:
            logger.info(f"找到请求链接：{target_url}")
            parsed_url = urlparse(target_url)
            query_params = parse_qs(parsed_url.query)
            logger.info(f"提取参数：{query_params}")
            return query_params
        else:
            logger.warning("未找到包含 lottery_home_detail 的请求！")
            return None
    except Exception as e:
        logger.error(f"获取 lottery URL 失败: {e}")
        return None

# c) 请求接口获取下载地址
def get_download_url(act_id, lottery_id, video_type):
    params = {
        "act_id": act_id,
        "lottery_id": lottery_id
    }
    headers = {
        "User-Agent": USER_AGENT
    }

    try:
        logger.info(f"正在请求 API 获取下载地址，参数：{params}")
        response = requests.get(API_URL, params=params, headers=headers)
        response.raise_for_status()  # 如果状态码不是 200，抛出异常
        data = response.json()

        video_urls = []
        image_urls = []
        name = data.get('data', {}).get('name', '未知活动名称')
        item_list = data.get("data", {}).get("item_list", [])
        collect_list= data.get("data", {}).get("collect_list", []).get("collect_infos", [])

        logger.info(f"活动名称：{name}")

        for item in item_list:
            card = item.get("card_info")
            if not card:
                continue

            # 视频下载链接处理
            downloads = card.get("video_list_download") if video_type else card.get("video_list")
            video_name = card.get("card_name", "unnamed").replace("·", "_").replace(" ", "_")
            if downloads:
                for url in downloads:
                    video_urls.append((video_name, url))

            # 图片下载链接处理（使用 card_img 字段）
            image_url = card.get("card_img")
            if image_url:
                image_name = video_name  # 可复用视频名作为图片名
                image_urls.append((image_name, image_url))
        for collect in collect_list:
            card = collect.get("card_item",{})
            if card:
                card=card.get("card_type_info",{})
                if card:
                    downloads = card.get("content").get("animation").get("animation_video_urls") if not video_type else card.get("watermark_animations")
                    video_name = card.get("name", "unnamed").replace("·", "_").replace(" ", "_")
                    if downloads and not video_type:
                        for url in downloads:
                            video_urls.append((video_name, url))
                    if downloads and video_type:
                        for url in downloads:
                            video_urls.append((video_name, url.get("watermark_animation")))

                    # 图片下载链接处理（使用 card_img 字段）
                    image_url = card.get("overview_image")
                    if image_url:
                        image_name = video_name  # 可复用视频名作为图片名
                        image_urls.append((image_name, image_url))

        return name, video_urls, image_urls
    except requests.RequestException as e:
        logger.error(f"请求 API 失败: {e}")
        return None, [], []
    except Exception as e:
        logger.error(f"解析下载链接失败: {e}")
        return None, [], []


# ====== 主程序 ======

def main():
    # a) 扫描二维码获取 URL
    url = scan_qr_code_from_full_image(QRCODE_IMAGE_PATH)
    if not url:
        logger.error("二维码扫描失败，无法继续操作！")
        return

    # b) 获取 URL 参数
    query_params = get_lottery_url(url)
    if not query_params:
        logger.error("获取参数失败，无法继续操作！")
        return

    # c) 获取下载链接
    name, video_urls, image_urls = get_download_url(query_params['act_id'][0], query_params['lottery_id'][0], VIDEO_WATER_TYPE)
    if not video_urls and not image_urls:
        logger.error("未获取到有效的下载链接，程序结束！")
        return

    # 将活动名称作为下载目录
    whole_name = name

    downloader = Downloader()

    # 下载视频
    for video_name, video_url in video_urls:
        downloader.download("video", whole_name, video_name, video_url, "mp4")

    # 下载图片
    for image_name, image_url in image_urls:
        downloader.download("img", whole_name, image_name, image_url, "png")
    deduplicate_videos_by_hash(os.path.join(downloader.base_dir, whole_name, "video"))

def deduplicate_videos_by_hash(video_dir):
    logger.info(f"开始对视频文件夹去重：{video_dir}")
    hash_map = {}
    for root, _, files in os.walk(video_dir):
        for file in files:
            if not file.lower().endswith(".mp4"):
                continue
            path = os.path.join(root, file)
            try:
                with open(path, "rb") as f:
                    file_hash = hashlib.md5(f.read()).hexdigest()
                if file_hash in hash_map:
                    # 重复文件，删除
                    logger.info(f"删除重复文件：{path.replace(os.sep, '/')}")
                    os.remove(path)
                else:
                    hash_map[file_hash] = path
            except Exception as e:
                logger.warning(f"处理文件出错：{path}, 错误: {e}")
    logger.info("视频去重完成。")

if __name__ == "__main__":
    main()
