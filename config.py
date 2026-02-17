"""配置管理模块"""
import os
from pathlib import Path

class Config:
    """应用配置"""
    # 浏览器和驱动路径
    CHROME_BROWSER_PATH = os.environ.get("CHROME_BROWSER_PATH", r"chrome-win64\chrome.exe")
    CHROME_DRIVER_PATH = os.environ.get("CHROME_DRIVER_PATH", r"chromedriver.exe")
    
    # API 配置
    API_URL = "https://api.bilibili.com/x/vas/dlc_act/lottery_home_detail"
    REFERER = "https://www.bilibili.com/"
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    
    # 应用配置
    APP_NAME = "BilibiliCollectionsDownloader"
    LOG_DIR = "logs"
    DOWNLOAD_DIR = "dlc"
    QRCODE_DIR = "qrcodes"
    URLS_FILE = "urls.txt"
    
    # 下载配置
    TIMEOUT = 10
    CHUNK_SIZE = 8 * 1024 * 1024  # 8MB
    MAX_RETRIES = 3
    
    # 视频类型配置
    VIDEO_WATER = True  # 是否下载水印视频
    VIDEO_NO_WATER = True  # 是否下载无水印视频
