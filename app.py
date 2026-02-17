"""
BilibiliCollectionsDownloader - 单文件版本
完整集成所有功能，可直接用 PyInstaller 打包成 EXE
"""
import os
import sys
import time
import requests
import cv2
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import re

from pyzbar.pyzbar import decode
from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ==================== 配置 ====================
class Config:
    APP_NAME = "BilibiliCollectionsDownloader"
    
    # 路径配置（便携版相对路径）
    CHROME_BROWSER_PATH = r"chrome-win64\chrome.exe"
    CHROME_DRIVER_PATH = r"chromedriver.exe"
    LOG_DIR = "logs"
    DOWNLOAD_DIR = "dlc"
    QRCODE_DIR = "qrcodes"
    URLS_FILE = "urls.txt"
    
    # API 配置
    API_URL = "https://api.bilibili.com/x/vas/dlc_act/lottery_home_detail"
    REFERER = "https://www.bilibili.com/"
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    
    # 下载配置
    TIMEOUT = 10
    CHUNK_SIZE = 8 * 1024 * 1024


# ==================== 日志管理 ====================
class LazyErrorHandler(logging.Handler):
    """延迟创建错误日志文件"""
    
    def __init__(self, app_name, log_dir="logs"):
        super().__init__(level=logging.ERROR)
        self.app_name = app_name
        self.log_dir = log_dir
        self.handler = None
    
    def emit(self, record):
        if not self.handler:
            Path(self.log_dir).mkdir(parents=True, exist_ok=True)
            date_str = datetime.now().strftime("%Y-%m-%d")
            err_file = os.path.join(self.log_dir, f"{self.app_name}_{date_str}.error.log")
            self.handler = logging.FileHandler(err_file, encoding="utf-8")
            formatter = logging.Formatter(
                "[%(asctime)s] [%(levelname)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            self.handler.setFormatter(formatter)
        self.handler.emit(record)


def setup_logger(app_name: str, log_dir="logs") -> logging.Logger:
    """设置日志记录器"""
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    
    date_str = datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(log_dir, f"{app_name}_{date_str}.log")
    
    logger = logging.getLogger(app_name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    
    if logger.handlers:
        return logger
    
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # 控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件输出
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # 延迟错误日志
    lazy_error_handler = LazyErrorHandler(app_name, log_dir)
    logger.addHandler(lazy_error_handler)
    
    return logger


logger = setup_logger(Config.APP_NAME, Config.LOG_DIR)


# ==================== 工具函数 ====================
def is_url(string: str) -> bool:
    """验证是否为有效 URL"""
    pattern = re.compile(r'^(https?|ftp)://[^\s/$.?#].\S*$', re.IGNORECASE)
    return bool(re.match(pattern, string))


def safe_filename(name: str) -> str:
    """处理文件名"""
    name = name.replace("·", "_").replace(" ", "_")
    return re.sub(r'[<>:"/\\|?*]', '_', name)


# ==================== 解析模块 ====================
def scan_qr_code(image_path: str) -> str | None:
    """扫描二维码图片"""
    logger.info(f"正在扫描二维码：{image_path}")
    img = cv2.imread(image_path)
    if img is None:
        logger.error(f"二维码图片读取失败：{image_path}")
        return None
    
    decoded_objects = decode(img)
    for obj in decoded_objects:
        if obj.type == 'QRCODE':
            qr_url = obj.data.decode('utf-8')
            logger.info(f"扫描到 URL: {qr_url}")
            return qr_url
    
    logger.warning(f"未检测到二维码：{image_path}")
    return None


def get_lottery_params(page_url: str) -> list[dict] | None:
    """获取 lottery_home_detail API 参数"""
    try:
        chrome_options = Options()
        chrome_options.binary_location = Config.CHROME_BROWSER_PATH
        service = Service(executable_path=Config.CHROME_DRIVER_PATH)
        chrome_options.add_argument("--headless")
        
        seleniumwire_options = {'disable_encoding': True}
        driver = webdriver.Chrome(
            service=service,
            options=chrome_options,
            seleniumwire_options=seleniumwire_options
        )
        
        logger.info(f"访问分享页：{page_url}")
        driver.get(page_url)
        time.sleep(5)
        
        # 切换到 iframe
        WebDriverWait(driver, 10).until(
            EC.frame_to_be_available_and_switch_to_it((By.ID, "mall-iframe"))
        )
        
        # 等待所有 tab 加载
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".card-tabs .tab"))
        )
        
        tabs = driver.find_elements(By.CSS_SELECTOR, ".card-tabs .tab")
        logger.info(f"找到 {len(tabs)} 个 tab")
        
        # 点击所有 tab
        for i in range(len(tabs)):
            tabs = driver.find_elements(By.CSS_SELECTOR, ".card-tabs .tab")
            try:
                name = tabs[i].find_element(By.CSS_SELECTOR, ".lottery-name").text
            except:
                name = f"tab-{i + 1}"
            logger.info(f"点击第 {i + 1} 个 tab：{name}")
            tabs[i].click()
            time.sleep(2)
        
        # 收集请求
        target_urls = []
        for request in driver.requests:
            if request.response and "lottery_home_detail" in request.url and request.url not in target_urls:
                target_urls.append(request.url)
        
        driver.quit()
        
        if not target_urls:
            logger.warning("未找到 lottery_home_detail 请求")
            return None
        
        query_params_list = []
        for target_url in target_urls:
            logger.debug(f"找到 API 请求：{target_url}")
            parsed_url = urlparse(target_url)
            query_params = parse_qs(parsed_url.query)
            query_params_list.append(query_params)
        
        return query_params_list
        
    except Exception as e:
        logger.error(f"获取 lottery 参数失败：{e}", exc_info=True)
        return None


def extract_card_downloads(card: dict, video_type: tuple[bool, bool]) -> tuple[list, list, list]:
    """从卡片提取下载链接"""
    video_urls = []
    water_mark_urls = []
    image_urls = []
    
    card_name = safe_filename(card.get("card_name", card.get("name", "unnamed")))
    
    if video_type[1]:
        temp = card.get("video_list")
        if temp and isinstance(temp, list) and temp[0]:
            video_urls.append((card_name, temp[0]))
    
    if video_type[0]:
        temp = card.get("video_list_download")
        if temp and isinstance(temp, list) and temp[0]:
            water_mark_urls.append((card_name, temp[0]))
    
    image_url = card.get("card_img") or card.get("overview_image")
    if image_url:
        image_urls.append((card_name, image_url))
    
    return video_urls, water_mark_urls, image_urls


def get_download_urls(act_id: str, lottery_id: str, video_type: tuple[bool, bool]) -> tuple[str, list, list, list]:
    """请求 API 获取下载链接"""
    try:
        params = {"act_id": act_id, "lottery_id": lottery_id}
        headers = {"User-Agent": Config.USER_AGENT}
        
        response = requests.get(Config.API_URL, params=params, headers=headers, timeout=Config.TIMEOUT)
        response.raise_for_status()
        
        data = response.json().get("data", {})
        if not isinstance(data, dict):
            logger.error(f"API 返回数据格式错误")
            return None, [], [], []
        
        activity_name = safe_filename(data.get("name", "Unknown"))
        video_urls = []
        water_mark_urls = []
        image_urls = []
        
        # 处理 item_list
        for item in data.get("item_list", []):
            if isinstance(item, dict):
                card = item.get("card_info")
                if isinstance(card, dict):
                    v, w, i = extract_card_downloads(card, video_type)
                    video_urls.extend(v)
                    water_mark_urls.extend(w)
                    image_urls.extend(i)
        
        # 处理 collect_infos
        collect_list = data.get("collect_list")
        if isinstance(collect_list, dict):
            collect_infos = collect_list.get("collect_infos", [])
            if isinstance(collect_infos, list):
                for collect in collect_infos:
                    if isinstance(collect, dict):
                        card_item = collect.get("card_item")
                        if isinstance(card_item, dict):
                            card = card_item.get("card_type_info")
                            if isinstance(card, dict):
                                v, w, i = extract_card_downloads(card, video_type)
                                video_urls.extend(v)
                                water_mark_urls.extend(w)
                                image_urls.extend(i)
        
        logger.info(f"活动：{activity_name} | 无水印视频：{len(video_urls)} | 有水印视频：{len(water_mark_urls)} | 图片：{len(image_urls)}")
        return activity_name, video_urls, image_urls, water_mark_urls
        
    except requests.RequestException as e:
        logger.error(f"API 请求失败：{e}")
    except Exception as e:
        logger.error(f"解析 API 响应失败：{e}", exc_info=True)
    
    return None, [], [], []


# ==================== 下载模块 ====================
class Downloader:
    """文件下载器"""
    
    def __init__(self, base_dir: str = Config.DOWNLOAD_DIR):
        self.base_dir = base_dir
        self.headers = {
            "Referer": Config.REFERER,
            "User-Agent": Config.USER_AGENT
        }
        self.failed_downloads = []
    
    def download(self, category: str, activity_name: str, file_name: str, file_url: str, ext: str) -> bool:
        """下载文件"""
        dir_path = os.path.join(self.base_dir, activity_name, category)
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        
        filename = f"{file_name}.{ext}"
        file_path = os.path.join(dir_path, filename)
        
        try:
            # 检查文件是否已存在且大小相同
            if os.path.exists(file_path):
                existing_size = os.path.getsize(file_path)
                try:
                    response = requests.head(file_url, headers=self.headers, timeout=Config.TIMEOUT)
                    remote_size = int(response.headers.get("Content-Length", 0))
                    
                    if existing_size == remote_size:
                        logger.info(f"[{category}] 文件已存在且大小相同，跳过：{file_path}")
                        return True
                except:
                    pass
                
                # 文件存在但大小不同，添加时间戳
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{file_name}_{timestamp}.{ext}"
                file_path = os.path.join(dir_path, filename)
            
            logger.info(f"[{category}] 开始下载：{file_path}")
            
            # 下载文件
            response = requests.get(file_url, headers=self.headers, stream=True, timeout=Config.TIMEOUT)
            response.raise_for_status()
            
            total_size = int(response.headers.get("Content-Length", 0))
            downloaded = 0
            
            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size:
                            progress = (downloaded / total_size) * 100
                            logger.debug(f"  进度：{progress:.1f}%")
            
            logger.info(f"[{category}] 下载完成：{file_path}")
            return True
            
        except Exception as e:
            error_msg = f"[{category}] 下载失败：{file_path} | {e}"
            logger.error(error_msg)
            self.failed_downloads.append(error_msg)
            return False
    
    def save_failed_list(self):
        """保存失败下载列表"""
        if not self.failed_downloads:
            logger.info("没有失败下载需要记录")
            return
        
        log_dir = Config.LOG_DIR
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"download_failed_{timestamp}.log"
        filepath = os.path.join(log_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(self.failed_downloads))
        
        logger.warning(f"失败列表已保存：{filepath}")


def deduplicate_by_hash(directory: str, extensions: list[str] = None) -> int:
    """按 MD5 哈希去重"""
    if extensions is None:
        extensions = ['.mp4']
    
    if not os.path.isdir(directory):
        logger.warning(f"目录不存在：{directory}")
        return 0
    
    logger.info(f"开始去重：{directory}")
    hash_map = {}
    deleted_count = 0
    
    for root, _, files in os.walk(directory):
        for file in files:
            if not any(file.lower().endswith(ext) for ext in extensions):
                continue
            
            file_path = os.path.join(root, file)
            try:
                md5 = hashlib.md5()
                with open(file_path, "rb") as f:
                    while chunk := f.read(Config.CHUNK_SIZE):
                        md5.update(chunk)
                
                file_hash = md5.hexdigest()
                
                if file_hash in hash_map:
                    logger.info(f"删除重复文件：{file_path}")
                    os.remove(file_path)
                    deleted_count += 1
                else:
                    hash_map[file_hash] = file_path
                    
            except Exception as e:
                logger.warning(f"处理文件失败：{file_path} | {e}")
    
    logger.info(f"去重完成，删除 {deleted_count} 个重复文件")
    return deleted_count


# ==================== 主程序 ====================
def load_urls_from_qrcode() -> list[str]:
    """从二维码文件夹扫描获取 URL"""
    urls = []
    qrcode_dir = Config.QRCODE_DIR
    Path(qrcode_dir).mkdir(parents=True, exist_ok=True)
    
    image_files = [f for f in os.listdir(qrcode_dir) if f.lower().endswith(('.jpg', '.png'))]
    
    if not image_files:
        logger.warning(f"未找到二维码图片（{qrcode_dir}），请添加 .jpg 或 .png 图片")
        return urls
    
    for image_file in image_files:
        image_path = os.path.join(qrcode_dir, image_file)
        url = scan_qr_code(image_path)
        if url and is_url(url):
            urls.append(url)
    
    return urls


def load_urls_from_file() -> list[str]:
    """从 urls.txt 读取 URL"""
    urls = []
    urls_file = Config.URLS_FILE
    
    if not os.path.exists(urls_file):
        logger.warning(f"未找到 {urls_file}，已创建空文件")
        with open(urls_file, "w", encoding="utf-8") as f:
            f.write("# 在此输入 B 站收藏集分享链接，每行一个\n")
        return urls
    
    with open(urls_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and is_url(line):
                urls.append(line)
    
    return urls


def select_video_type() -> tuple[bool, bool]:
    """选择视频类型"""
    print("\n选择视频类型：")
    print("  1. 无水印低质量")
    print("  2. 有水印高质量")
    print("  12. 两者都下载")
    choice = input("请输入选择 (默认: 12): ").strip() or "12"
    
    water = "2" in choice
    no_water = "1" in choice
    return (water, no_water)


def process_url(page_url: str, video_type: tuple[bool, bool]):
    """处理单个 URL"""
    logger.info(f"处理 URL：{page_url}")
    
    query_params_list = get_lottery_params(page_url)
    if not query_params_list:
        logger.error(f"获取参数失败：{page_url}")
        return
    
    for query_params in query_params_list:
        act_id = query_params.get('act_id', [None])[0]
        lottery_id = query_params.get('lottery_id', [None])[0]
        
        if not (act_id and lottery_id):
            logger.warning(f"参数不完整：act_id={act_id}, lottery_id={lottery_id}")
            continue
        
        activity_name, video_urls, image_urls, water_mark_urls = get_download_urls(
            act_id, lottery_id, video_type
        )
        
        if not activity_name:
            logger.error(f"API 请求失败")
            continue
        
        if not (video_urls or image_urls or water_mark_urls):
            logger.warning(f"未获取到下载链接：{activity_name}")
            continue
        
        # 创建下载器
        downloader = Downloader(Config.DOWNLOAD_DIR)
        
        # 下载资源
        for file_name, url in video_urls:
            downloader.download("video", activity_name, file_name, url, "mp4")
        
        for file_name, url in water_mark_urls:
            downloader.download("watermark_video", activity_name, file_name, url, "mp4")
        
        for file_name, url in image_urls:
            downloader.download("img", activity_name, file_name, url, "png")
        
        downloader.save_failed_list()
        
        # 去重
        video_dir = os.path.join(Config.DOWNLOAD_DIR, activity_name, "video")
        watermark_dir = os.path.join(Config.DOWNLOAD_DIR, activity_name, "watermark_video")
        deduplicate_by_hash(video_dir)
        deduplicate_by_hash(watermark_dir)


def main():
    """主函数"""
    logger.info(f"启动 {Config.APP_NAME}")
    
    print(f"\n{Config.APP_NAME}\n")
    print("选择输入方式：")
    print("  1. 扫描 qrcodes 文件夹中的二维码")
    print("  2. 读取 urls.txt 中的链接")
    choice = input("请选择 (默认: 1): ").strip() or "1"
    
    # 加载 URL
    if choice == "1":
        urls = load_urls_from_qrcode()
        source = "二维码"
    elif choice == "2":
        urls = load_urls_from_file()
        source = "urls.txt"
    else:
        logger.error("无效的选择")
        return
    
    if not urls:
        logger.error(f"未找到有效的 URL（来源：{source}）")
        return
    
    logger.info(f"找到 {len(urls)} 个 URL（来源：{source}）")
    
    # 选择视频类型
    video_type = select_video_type()
    logger.info(f"视频类型：无水印={video_type[1]}, 有水印={video_type[0]}")
    
    # 处理每个 URL
    for i, url in enumerate(urls, 1):
        logger.info(f"\n处理 URL {i}/{len(urls)}")
        process_url(url, video_type)
    
    logger.info(f"\n全部操作完成")
    print("\n按 Enter 键退出...")
    input()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("用户中断了程序")
    except Exception as e:
        logger.error(f"程序出现异常：{e}", exc_info=True)
    finally:
        logger.info("程序已退出")
