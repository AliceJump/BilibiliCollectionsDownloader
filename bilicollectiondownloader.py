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
from time import strftime
# ====== 使用须知 ======
'''
1. 自行搜索并安装依赖库：pyzbar, seleniumwire, opencv-python, requests, selenium
2. 下载并配置 Chrome 浏览器，下载并配置 ChromeDriver(自行寻找chromedriver和对应chrome版本)，下载并配置 B 站收藏集二维码图片(收藏集页面点分享后保存的分享二维码)
3. 修改 CHROME_BROWSER_PATH, CHROME_DRIVER_PATH, QRCODE_IMAGE_PATH 三个常量
'''

# ====== 常量配置 ======
'''
以下三个常量请自行配置
'''
# Chrome 浏览器的可执行程序路径，用于告诉 Selenium 使用哪个浏览器
CHROME_BROWSER_PATH = r"chrome-win64\chrome.exe"

# ChromeDriver 的路径，是与 Chrome 浏览器匹配的 WebDriver 控制工具
CHROME_DRIVER_PATH = r"chromedriver.exe"

# 存放收藏集二维码图片的路径，程序从该文件中读取并识别二维码内容

# VIDEO_WATER_TYPE=True为下载高质量水印版，VIDEO_WATER_TYPE=False为下载无水印版低质量
VIDEO_WATER_TYPE = False
VIDEO_NO_WATER_TYPE=False

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
# 将 logger 改为 print
log_all=""
log_err=""
log_warn=""
timestamp = strftime("%Y-%m-%d_%H-%M-%S")
def is_url(string):
    # 常见 http、https、ftp 开头的网址
    pattern = re.compile(
        r'^(https?|ftp)://[^\s/$.?#].[^\s]*$', re.IGNORECASE)
    return re.match(pattern, string) is not None
def log_save():
    with open("log/"+"log_"+timestamp+".txt", "w", encoding="utf-8") as f:
        f.write(log_all)
    log_info("日志已保存到"+"log/"+"log_"+timestamp+".txt")
    if log_err:
        with open("log/"+"log_err_"+timestamp+".txt", "w", encoding="utf-8") as f:
            f.write(log_err)
        log_info("错误日志已保存到"+"log/"+"log_err_"+timestamp+".txt")
    if log_warn:
        with open("log/"+"log_warn_"+timestamp+".txt", "w", encoding="utf-8") as f:
            f.write(log_warn)
def log_info(message):
    global log_all
    print(f"[INFO] {message}")
    log_all+=f"[INFO] {message}\n"
def log_warning(message):
    global log_all, log_warn
    print(f"[WARNING] {message}")
    log_all+=f"[WARNING] {message}\n"
    log_warn+=f"[WARNING] {message}\n"
def log_error(message):
    global log_all,log_err
    print(f"[ERROR] {message}")
    log_all+=f"[ERROR] {message}\n"
    log_err+=f"[ERROR] {message}\n"


# 将 logger 的部分替换为上述 print 函数

class Downloader:
    def __init__(self, base_dir="dlc"):
        self.base_dir = base_dir
        self.headers = {
            "Referer": REFERER,
            "User-Agent": USER_AGENT
        }
        self.err_list = []
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
                response = requests.get(url, headers=self.headers, stream=True, timeout=10)
                response.raise_for_status()
                remote_size = int(response.headers.get("Content-Length", 0))
                response.close()  # 关闭连接

                if existing_size == remote_size:
                    log_info(f"文件已存在且大小相同，跳过下载：{file_path.replace(os.sep, '/')}")
                    return
                else:
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    filename = f"{name}_{timestamp}.{ext}"
                    file_path = os.path.join(dir_path, filename)

            log_info(f"开始下载{category}：{file_path.replace(os.sep, '/')}")
            response = requests.get(url, headers=self.headers, stream=True)
            response.raise_for_status()

            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            log_info(f"{category.capitalize()}下载完成：{file_path.replace(os.sep, '/')}")
        except Exception as e:
            log_error(f"下载{category}失败：{file_path.replace(os.sep, '/')}")
            self.err_list.append(f"下载{category}失败：{file_path.replace(os.sep, '/')}, 错误: {e}")

    def err_list_save(self):


        dir_path = os.path.join(self.base_dir[:-4], "log")
        os.makedirs(dir_path, exist_ok=True)
        log_filename = f"log_err_list_{timestamp}.log"
        full_path = os.path.join(dir_path, log_filename)
        if len(self.err_list) == 0:
            log_info("没有错误下载URL需要记录")
            return
        with open(full_path, "w", encoding="utf-8") as f:
            for err in self.err_list:
                f.write(err + "\n")

        log_info(f"错误日志已保存到：{full_path.replace(os.sep, '/')}")


# ====== 功能函数 ======
def extract_images_and_videos(data, type):
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
            animation = card_type_info.get('animation')

    return image_urls, video_urls


# a) 扫描二维码并提取 URL
def scan_qr_code_from_full_image(image_path):
    log_info(f"正在扫描二维码，路径：{image_path}")
    img = cv2.imread(image_path)
    if img is None:
        log_error("二维码图片读取失败，请检查图片路径！")
        return None
    decoded_objects = decode(img)
    for obj in decoded_objects:
        if obj.type == 'QRCODE':
            url = obj.data.decode('utf-8')
            log_info(f"扫描到的 URL: {url}")
            return url
    log_warning("未检测到二维码！")
    return None


# b) 用 Selenium 获取请求 URL 并提取参数
def get_lottery_url(url):
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

        log_info(f"正在访问 URL：{url}")
        driver.get(url)
        time.sleep(5)
        WebDriverWait(driver, 10).until(
            EC.frame_to_be_available_and_switch_to_it((By.ID, "mall-iframe"))
        )

        # 等待所有 tab 加载出来
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".card-tabs .tab"))
        )

        # 获取所有 tab
        tabs = driver.find_elements(By.CSS_SELECTOR, ".card-tabs .tab")
        print(f"总共找到 {len(tabs)} 个 tab")

        # 挨个点击（注意每次点击后要重新获取 tab 元素）
        for i in range(len(tabs)):
            # 重新获取 tabs（每次点击可能页面更新，元素引用会失效）
            tabs = driver.find_elements(By.CSS_SELECTOR, ".card-tabs .tab")

            name = tabs[i].find_element(By.CSS_SELECTOR, ".lottery-name").text
            print(f"点击第 {i + 1} 个 tab：{name}")
            tabs[i].click()

            # 可以加一些等待时间让页面切换完成
            time.sleep(2)
        target_url = []
        count= 0
        for request in driver.requests:
            if count == len(tabs):
                break
            if request.response and "lottery_home_detail" in request.url and request.url not in target_url:
                target_url.append(request.url)
                count += 1

        driver.quit()

        if target_url:
            query_params_list=[]
            for target_ur in target_url:
                log_info(f"找到请求链接：{target_ur}")
                parsed_url = urlparse(target_ur)
                query_params = parse_qs(parsed_url.query)
                log_info(f"提取参数：{query_params}")
                query_params_list.append(query_params)
            return query_params_list
        else:
            log_warning("未找到包含 lottery_home_detail 的请求！")
            return None
    except Exception as e:
        log_error(f"获取 lottery URL 失败: {e}")
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
        log_info(f"正在请求 API 获取下载地址，参数：{params}")
        response = requests.get(API_URL, params=params, headers=headers)
        response.raise_for_status()  # 如果状态码不是 200，抛出异常
        data = response.json()

        video_urls = []
        water_mark_video_urls = []
        image_urls = []
        name = data.get('data', {}).get('name', '未知活动名称')
        item_list = data.get("data", {}).get("item_list", [])
        data_dict = data.get("data", {})
        collect_list = data_dict.get("collect_list", {})
        collect_infos = collect_list.get("collect_infos", []) if isinstance(collect_list, dict) else []

        log_info(f"活动名称：{name}")

        for item in item_list:
            card = item.get("card_info")
            if not card:
                continue

            # 视频下载链接处理
            downloads=[]
            if video_type[1]:
                temp=card.get("video_list")
                if temp:
                    downloads.append(temp[0])
            water_mark_downloads=[]
            if video_type[0]:
                temp = card.get("video_list_download")
                if temp:
                    water_mark_downloads.append(temp[0])
            video_name = card.get("card_name", "unnamed").replace("·", "_").replace(" ", "_")
            video_name = re.sub(r'[<>:"/\\|?*]', '_', video_name)
            if downloads:
                for url_temp in downloads:
                    video_urls.append((video_name, url_temp))
            if water_mark_downloads:
                for url_temp in water_mark_downloads:
                    water_mark_video_urls.append((video_name, url_temp))

            # 图片下载链接处理（使用 card_img 字段）
            image_url = card.get("card_img")
            if image_url:
                image_name = video_name  # 可复用视频名作为图片名
                image_urls.append((image_name, image_url))

        for collect in collect_infos:
            card = collect.get("card_item", {})
            if card:
                card = card.get("card_type_info", {})
                if card:
                    downloads = []
                    if card.get("content"):
                        animation = card["content"].get("animation")
                        if animation:
                            if video_type[1]:
                                temp=animation.get("1")
                                if temp:
                                    downloads.append(temp[0])
                    water_mark_downloads=[]
                    if video_type[0]:
                        temp = card.get("watermark_animations")
                        if temp:
                            temp=temp[0]
                            if temp:
                                temp=temp.get("watermark_animation",{})
                                if temp:
                                    water_mark_downloads.append(temp)
                    video_name = card.get("name", "unnamed").replace("·", "_").replace(" ", "_")
                    if downloads:
                        for url_temp in downloads:
                            video_urls.append((video_name, url_temp))
                    if water_mark_downloads:
                        for url_temp in water_mark_downloads:
                            water_mark_video_urls.append((video_name, url_temp))



                    # 图片下载链接处理（使用 card_img 字段）
                    image_url = card.get("overview_image")
                    if image_url:
                        image_name = video_name  # 可复用视频名作为图片名
                        image_urls.append((image_name, image_url))

        return name, video_urls, image_urls,water_mark_video_urls
    except requests.RequestException as e:
        log_error(f"请求 API 失败: {e}")
        return None, [], []
    except Exception as e:
        log_error(f"解析下载链接失败: {e}")
        return None, [], []


# ====== 主程序 ======

def load_url(url):
    # a) 扫描二维码获取 URL

    # b) 获取 URL 参数
    query_params_list = get_lottery_url(url)
    if not query_params_list:
        log_error("获取参数失败，无法继续操作！")
        return

        # c) 获取下载链接
    for query_params in query_params_list:
        name, video_urls, image_urls,water_mark_video_urls = get_download_url(query_params['act_id'][0], query_params['lottery_id'][0],
                                                        [VIDEO_WATER_TYPE,VIDEO_NO_WATER_TYPE])
        if not video_urls and not image_urls:
            log_error("未获取到有效的下载链接，程序结束！")
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
        for water_mark_name, water_mark_video_url in water_mark_video_urls:
            downloader.download("watermark_video", whole_name, water_mark_name, water_mark_video_url, "mp4")
        downloader.err_list_save()
        deduplicate_videos_by_hash(os.path.join(downloader.base_dir, whole_name, "video"))
        deduplicate_videos_by_hash(os.path.join(downloader.base_dir, whole_name, "watermark_video"))


def deduplicate_videos_by_hash(video_dir):
    log_info(f"开始对视频文件夹去重：{video_dir.replace(os.sep, '/')}")
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
                    log_info(f"删除重复文件：{path.replace(os.sep, '/')}")
                    os.remove(path)
                else:
                    hash_map[file_hash] = path
            except Exception as e:
                log_warning(f"处理文件出错：{path}, 错误: {e}")
    log_info("视频去重完成。")


if __name__ == "__main__":
    switch=input("选择你要选择的方式\n1.批量扫描qrcodes文件夹内的二维码\n2.批量载入urls.txt内的链接(以行为单位)\n请输入选择:")
    urls=[]
    method=""
    text=""
    video_water_type=input("选择视频类型\n1.无水印低质量版\n2.有水印高质量版\n如输入12为两个都要，1为要无水印低质量版\n请输入:")
    if "1" in video_water_type:
        VIDEO_NO_WATER_TYPE=True
    if "2" in video_water_type:
        VIDEO_WATER_TYPE=True
    if switch == "1":
        method="扫描方式"
        directory = 'qrcodes'
        image_files = []

        for file in os.listdir(directory):
            full_path = os.path.join(directory, file)
            if os.path.isfile(full_path):
                if file.lower().endswith(('.jpg', '.png')):
                    image_files.append(file)  # 只保存文件名
        for qrcode_img in image_files:
            text=scan_qr_code_from_full_image("qrcodes/" + qrcode_img)
            if text:
                if is_url(text.strip()):
                    urls.append(text.strip())
    if switch == "2":
        method="读取文本文件方式获得"
        directory = 'urls.txt'
        try:
            with open('urls.txt', 'r',encoding="utf-8") as f:
                for text in f:
                    if text:
                        if is_url(text.strip()):
                            urls.append(text.strip())
        except Exception as e:
            print("找不到urls.txt")
    for url in urls:
        print("找到{}个url".format(len(urls)))
        load_url(url)
    log_save()
    print("已完成")
    input("按任意键退出程序")
