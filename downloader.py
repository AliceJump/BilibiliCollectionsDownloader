"""下载和去重模块"""
import os
import hashlib
import logging
from datetime import datetime
from pathlib import Path
import requests
from config import Config

logger = logging.getLogger(Config.APP_NAME)


class Downloader:
    """文件下载器，支持大文件、断点续传、去重"""
    
    def __init__(self, base_dir: str = Config.DOWNLOAD_DIR):
        self.base_dir = base_dir
        self.headers = {
            "Referer": Config.REFERER,
            "User-Agent": Config.USER_AGENT
        }
        self.failed_downloads = []
    
    def download(self, category: str, activity_name: str, file_name: str, file_url: str, ext: str) -> bool:
        """
        下载文件
        category: 'video', 'watermark_video', 'img'
        activity_name: 活动名称（作为文件夹名）
        file_name: 文件基础名
        file_url: 下载链接
        ext: 文件扩展名
        返回: 是否下载成功
        """
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
    """
    对指定目录内的文件按 MD5 内容哈希去重
    extensions: 要处理的文件扩展名，默认为 ['.mp4']
    返回: 删除的文件数
    """
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
