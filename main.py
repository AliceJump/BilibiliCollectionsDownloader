"""主程序入口"""
import os
import logging
from pathlib import Path
from config import Config
from logger import setup_logger
from parser import scan_qr_code, is_url, get_lottery_params, get_download_urls
from downloader import Downloader, deduplicate_by_hash

# 初始化日志
logger = setup_logger(Config.APP_NAME, Config.LOG_DIR)


def load_urls_from_qrcode() -> list[str]:
    """从 qrcodes 文件夹扫描二维码获取 URL"""
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
    """从 urls.txt 文件读取 URL"""
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
    """
    交互式选择视频类型
    返回: (水印视频, 无水印视频)
    """
    print("\n选择视频类型：")
    print("  1. 无水印低质量")
    print("  2. 有水印高质量")
    print("  12. 两者都下载")
    choice = input("请输入选择 (默认: 12): ").strip() or "12"
    
    water = "2" in choice
    no_water = "1" in choice
    return (water, no_water)


def process_url(page_url: str, video_type: tuple[bool, bool]):
    """处理单个收藏集 URL"""
    logger.info(f"处理 URL：{page_url}")
    
    # 获取 API 参数
    query_params_list = get_lottery_params(page_url)
    if not query_params_list:
        logger.error(f"获取参数失败：{page_url}")
        return
    
    # 处理每个 tab（活动）
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
        
        # 下载无水印视频
        for file_name, url in video_urls:
            downloader.download("video", activity_name, file_name, url, "mp4")
        
        # 下载有水印视频
        for file_name, url in water_mark_urls:
            downloader.download("watermark_video", activity_name, file_name, url, "mp4")
        
        # 下载图片
        for file_name, url in image_urls:
            downloader.download("img", activity_name, file_name, url, "png")
        
        # 保存失败列表
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
