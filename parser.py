"""网页解析模块 - 二维码识别、页面采集、API 解析"""
import os
import re
import time
import requests
import cv2
import logging
from urllib.parse import urlparse, parse_qs
from pyzbar.pyzbar import decode
from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from config import Config

logger = logging.getLogger(Config.APP_NAME)


def is_url(string: str) -> bool:
    """验证字符串是否为有效 URL"""
    pattern = re.compile(r'^(https?|ftp)://[^\s/$.?#].\S*$', re.IGNORECASE)
    return bool(re.match(pattern, string))


def scan_qr_code(image_path: str) -> str | None:
    """扫描二维码图片，返回 URL"""
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
    """
    使用 Selenium 获取分享页中的 lottery_home_detail API 参数
    返回: [{'act_id': [...], 'lottery_id': [...]}, ...]
    """
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
        
        # 点击所有 tab 以触发 API 请求
        for i in range(len(tabs)):
            tabs = driver.find_elements(By.CSS_SELECTOR, ".card-tabs .tab")
            try:
                name = tabs[i].find_element(By.CSS_SELECTOR, ".lottery-name").text
            except:
                name = f"tab-{i + 1}"
            logger.info(f"点击第 {i + 1} 个 tab：{name}")
            tabs[i].click()
            time.sleep(2)
        
        # 收集 lottery_home_detail 请求
        target_urls = []
        for request in driver.requests:
            if request.response and "lottery_home_detail" in request.url and request.url not in target_urls:
                target_urls.append(request.url)
        
        driver.quit()
        
        if not target_urls:
            logger.warning("未找到 lottery_home_detail 请求")
            return None
        
        # 解析参数
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
    """
    从卡片信息中提取视频和图片下载链接
    video_type: (水印视频, 无水印视频)
    返回: (video_urls, water_mark_urls, image_urls)
    """
    video_urls = []
    water_mark_urls = []
    image_urls = []
    
    card_name = safe_filename(card.get("card_name", card.get("name", "unnamed")))
    
    # 无水印视频
    if video_type[1]:
        temp = card.get("video_list")
        if temp and isinstance(temp, list) and temp[0]:
            video_urls.append((card_name, temp[0]))
    
    # 有水印视频
    if video_type[0]:
        temp = card.get("video_list_download")
        if temp and isinstance(temp, list) and temp[0]:
            water_mark_urls.append((card_name, temp[0]))
    
    # 图片
    image_url = card.get("card_img") or card.get("overview_image")
    if image_url:
        image_urls.append((card_name, image_url))
    
    return video_urls, water_mark_urls, image_urls


def safe_filename(name: str) -> str:
    """处理文件名，替换非法字符"""
    name = name.replace("·", "_").replace(" ", "_")
    return re.sub(r'[<>:"/\\|?*]', '_', name)


def get_download_urls(act_id: str, lottery_id: str, video_type: tuple[bool, bool]) -> tuple[str, list, list, list]:
    """
    请求 API 获取活动下载链接
    返回: (活动名, 无水印视频列表, 图片列表, 有水印视频列表)
    """
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
        
        # 处理 item_list（主容器）
        for item in data.get("item_list", []):
            if isinstance(item, dict):
                card = item.get("card_info")
                if isinstance(card, dict):
                    v, w, i = extract_card_downloads(card, video_type)
                    video_urls.extend(v)
                    water_mark_urls.extend(w)
                    image_urls.extend(i)
        
        # 处理 collect_infos（收藏容器）
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
