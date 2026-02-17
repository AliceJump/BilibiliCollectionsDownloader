# Copilot Instructions (BilibiliCollectionsDownloader)

## 项目概览
- 重构为模块化结构，核心逻辑分散到多个文件：
  - [main.py](main.py) - 主程序入口，交互式菜单和流程控制
  - [config.py](config.py) - 全局配置管理
  - [logger.py](logger.py) - 日志管理（支持延迟创建错误日志）
  - [parser.py](parser.py) - 网页解析（二维码识别、页面采集、API 解析）
  - [downloader.py](downloader.py) - 下载与去重（MD5 哈希）

主流程：读取二维码或文本 URL → Selenium 打开分享页抓取 API 参数 → 请求 API 拿到资源链接 → 下载资源 → 去重与日志输出。

## 关键数据流/组件

### 配置层 ([config.py](config.py))
- 集中管理所有常量：Chrome/ChromeDriver 路径、API 端点、日志目录、下载目录等
- 支持环境变量覆盖（如 `CHROME_BROWSER_PATH`）

### 日志层 ([logger.py](logger.py))
- `setup_logger()` - 初始化日志记录器，输出到控制台 + 文件
- `LazyErrorHandler` - 延迟创建错误日志，只有错误时才创建 .error.log 文件
- 日志格式统一：`[时间] [级别] 消息`，保存到 logs/ 目录

### 解析层 ([parser.py](parser.py))
- `scan_qr_code()` - 使用 OpenCV + pyzbar 扫描 qrcodes/ 目录下的二维码
- `get_lottery_params()` - 使用 Selenium Wire 拦截包含 `lottery_home_detail` 的请求，提取 `act_id/lottery_id` 参数
- `get_download_urls()` - 调用 B 站 API，解析 `item_list` 与 `collect_list.collect_infos`，提取视频/图片链接
- `extract_card_downloads()` - 从单张卡片提取下载链接（支持有/无水印视频）
- `safe_filename()` - 清洗文件名（替换 `·` 和非法字符）

### 下载层 ([downloader.py](downloader.py))
- `Downloader` 类 - 文件下载器，按 `dlc/<活动名>/<类别>` 归档，支持大文件流式下载
  - 检查本地文件大小与远程是否相同，相同则跳过
  - 支持失败记录（[Downloader.failed_downloads](downloader.py)）
- `deduplicate_by_hash()` - 按 MD5 哈希去重，避免重复下载

### 主程序 ([main.py](main.py))
- `load_urls_from_qrcode()` - 从 qrcodes/ 目录扫描二维码
- `load_urls_from_file()` - 从 urls.txt 读取链接（支持注释行 #）
- `select_video_type()` - 交互式选择视频类型（有/无水印）
- `process_url()` - 单个 URL 的完整处理流程

## 关键字段解析

**API 响应结构**（`get_download_urls()` 中）：
- `data.name` - 活动名称
- `data.item_list[].card_info` - 主容器卡片
  - `card_name` - 资源名
  - `video_list[0]` - 无水印视频链接
  - `video_list_download[0]` - 有水印视频链接
  - `card_img` - 缩略图链接
- `data.collect_list.collect_infos[].card_item.card_type_info` - 收藏容器卡片
  - `name` - 资源名
  - `content.animation.1[0]` - 无水印动画链接
  - `watermark_animations[0].watermark_animation` - 有水印动画链接
  - `overview_image` - 缩略图链接

## 运行与环境
- 依赖与浏览器配置见 [README.md](README.md)。
- 必须配置常量：`CHROME_BROWSER_PATH`、`CHROME_DRIVER_PATH`（或使用打包版本）。
- 运行入口为 [main.py](main.py)，使用交互式命令行选择输入方式和视频类型。

## 项目约定/模式
- 日志统一通过 logging 模块输出，结束时自动保存到 logs/ 目录，错误日志只在有错误时创建
- 资源命名自动清洗特殊字符（例如 `·` 和非法文件名字符）
- 通过 `CONFIG.VIDEO_WATER` / `CONFIG.VIDEO_NO_WATER` 控制有/无水印下载
- 下载按活动名称和资源类别分类存放

## 集成点/外部依赖
- Selenium Wire 拦截请求（依赖 Chrome + ChromeDriver 匹配版本）
- B 站 API：`API_URL = https://api.bilibili.com/x/vas/dlc_act/lottery_home_detail`，请求头需带 `User-Agent`
- Chrome for Testing 自动下载（[build/package.ps1](build/package.ps1) 中）

## 常见扩展位置
- URL 来源：在 [main.py](main.py) 的 `main()` 函数中扩展更多输入源（如 GUI、数据库等）
- 解析逻辑：新增字段优先在 [parser.py](parser.py) 的 `extract_card_downloads()` 中处理
- 下载策略：并发/断点续传等集中在 [downloader.py](downloader.py) 的 `Downloader.download()` 中实现
- 配置管理：新增常量在 [config.py](config.py) 中统一管理
