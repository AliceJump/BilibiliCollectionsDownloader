# Copilot Instructions (BilibiliCollectionsDownloader)

## 项目概览
- 单文件脚本，核心逻辑在 [bilicollectiondownloader.py](bilicollectiondownloader.py)。
- 主流程：读取二维码或文本 URL → Selenium 打开分享页抓取 API 参数 → 请求 API 拿到资源链接 → 下载资源 → 去重与日志输出。

## 关键数据流/组件
- 二维码识别：`scan_qr_code_from_full_image()` 使用 OpenCV + pyzbar 解析 `qrcodes` 目录下图片。
- 页面采集：`get_lottery_url()` 使用 Selenium Wire 拦截包含 `lottery_home_detail` 的请求并解析 `act_id/lottery_id`。
- 下载解析：`get_download_url()` 调用 `API_URL`，解析 `item_list` 与 `collect_list.collect_infos`，输出视频/图片链接。
- 下载与去重：`Downloader.download()` 按 `dlc/<活动名>/<类别>` 归档；`deduplicate_videos_by_hash()` 以 MD5 去重。

## 运行与环境
- 依赖与浏览器配置见 [README.md](README.md)。
- 必须配置常量：`CHROME_BROWSER_PATH`、`CHROME_DRIVER_PATH`。
- 运行入口为 `__main__` 的交互式命令行（选择二维码/文本方式与视频类型）。

## 项目约定/模式
- 日志统一通过 `log_info/log_warning/log_error` 写入内存缓存，结束时 `log_save()` 输出到 `log/` 目录。
- 资源命名会清洗特殊字符（例如 `card_name` 中的 `·` 和非法文件名字符）。
- 通过 `VIDEO_WATER_TYPE` / `VIDEO_NO_WATER_TYPE` 控制有/无水印下载；`get_download_url()` 同时产出不同视频列表。

## 集成点/外部依赖
- Selenium Wire 拦截请求（依赖 Chrome + ChromeDriver 匹配版本）。
- B 站 API：`API_URL = https://api.bilibili.com/x/vas/dlc_act/lottery_home_detail`，请求头需带 `User-Agent`。

## 常见扩展位置
- URL 来源：在 `__main__` 处扩展更多输入源（例如批量文件）。
- 解析逻辑：新增字段优先在 `get_download_url()` 中集中处理。
- 下载策略：并发/断点续传等集中在 `Downloader.download()` 中实现。
