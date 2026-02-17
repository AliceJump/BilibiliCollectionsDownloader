
# B 站收藏集下载脚本

这个 Python 脚本用于自动从 B 站的收藏集中下载视频和图片。通过扫描二维码获取收藏集 URL，并使用 Selenium 和 API 提取相关资源链接，最终实现批量下载。

## 快速开始

### 方式 1：使用预构建版本（推荐）

从 [Releases](https://github.com/AliceJump/BilibiliCollectionsDownloader/releases) 下载最新版本：

- **便携版**（推荐）：包含 Python 3.13.3 + Chrome + ChromeDriver，解压即用
- **EXE 版**：单文件可执行程序 + Chrome + ChromeDriver

使用步骤：
1. 解压下载的 zip 文件
2. 在 `qrcodes` 文件夹放置收藏集分享二维码图片（或编辑 `urls.txt` 添加链接）
3. 双击 `start.bat` 启动程序

### 方式 2：从源码运行

#### 1. 安装依赖

```bash
pip install -r requirements.txt
```

#### 2. 环境配置

将 Chrome 和 ChromeDriver 放到项目根目录：

```
chrome-win64/
  chrome.exe
chromedriver.exe
```

或者在 [config.py](config.py) 中配置路径。

#### 3. 运行程序

```bash
python main.py
```

程序启动后会提示选择：
- 输入方式：扫描二维码 / 读取 urls.txt
- 视频类型：无水印 / 有水印 / 两者都下载

## 开发者打包

本地打包（需要 Python 3.13.3）：

```bash
# Windows
build.bat

# 手动打包
.\build\package_portable.ps1  # 便携版
.\build\package_exe.ps1       # EXE 版
```

### 输出文件结构

下载的视频和图片将被存储在 `dlc` 目录下，按照活动名称和资源类型（视频/图片）进行分类：

```
dlc/
└── <活动名>/
    ├── video/              # 无水印视频
    ├── watermark_video/    # 有水印视频
    └── img/                # 图片
```


## 项目结构

```
.
├── main.py                      # 主程序入口
├── config.py                    # 配置管理
├── logger.py                    # 日志管理
├── parser.py                    # 网页解析（二维码、参数、API）
├── downloader.py                # 下载与去重
├── start.bat                    # 启动脚本（Windows）
├── qrcodes/                     # 放置收藏集二维码图片的目录
├── urls.txt                     # 收藏集链接（每行一个）
├── dlc/                         # 下载目录（自动创建）
│   └── <活动名>/
│       ├── video/               # 无水印视频
│       ├── watermark_video/     # 有水印视频
│       └── img/                 # 图片
└── logs/                        # 日志目录（自动创建）
```

## 项目约定

- **配置管理**：所有配置集中在 [config.py](config.py)
- **日志记录**：统一通过 logging 模块输出，日志保存到 logs/ 目录
- **文件命名**：自动清洗特殊字符（`·` 和非法文件名字符）
- **去重策略**：按 MD5 哈希去重，避免重复下载
- **错误处理**：失败的下载记录到 logs/download_failed_*.log

### 1. 二维码未能识别
确保二维码图片路径正确，并且二维码内容为有效的 B 站收藏集分享链接。

### 2. 无法下载视频或图片
请检查 Chrome 和 ChromeDriver 的配置是否正确，确保浏览器和驱动版本匹配。
