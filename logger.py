"""日志管理模块"""
import os
import logging
from datetime import datetime
from pathlib import Path

class LazyErrorHandler(logging.Handler):
    """延迟创建错误日志文件，只有有错误时才创建"""
    
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
    
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # 控制台输出
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # 文件输出
    if not any(isinstance(h, logging.FileHandler) and h.baseFilename == os.path.abspath(log_file) for h in logger.handlers):
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # 延迟错误日志
    if not any(isinstance(h, LazyErrorHandler) for h in logger.handlers):
        lazy_error_handler = LazyErrorHandler(app_name, log_dir)
        logger.addHandler(lazy_error_handler)
    
    return logger
