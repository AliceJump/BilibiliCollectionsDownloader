# Copilot Instructions (BilibiliCollectionsDownloader)

## 项目概览

**单文件架构** - 所有功能集成在 [app.py](app.py)，便于 PyInstaller 打包成单个 EXE。

**发布方式**：
- **预构建 EXE**（推荐用户）：完整独立可执行程序，无需安装 Python
- **源码版本**（开发者）：Python 3.13.3 + 依赖包

## 核心模块（app.py 内部）

### 配置层 (Config)
- 集中管理所有常量（路径、API、超时等）
- Chrome 路径默认为相对路径（便于便携部署）

### 日志层
- `setup_logger()` - 初始化日志记录器
- `LazyErrorHandler` - 延迟创建错误日志（只有出错时才创建）
- 日志同时输出到控制台和文件

### 解析层 (Parser)
- `scan_qr_code()` - OpenCV + pyzbar 扫描二维码
- `get_lottery_params()` - Selenium 拦截 `lottery_home_detail` API 请求
- `get_download_urls()` - 调用 B 站 API 解析资源链接
- `extract_card_downloads()` - 从卡片提取视频/图片链接

### 下载层 (Downloader)
- `Downloader` 类 - 文件下载器，支持大文件、已存在跳过、失败记录
- `deduplicate_by_hash()` - MD5 哈希去重

### 主程序 (main)
- `load_urls_from_qrcode()` - 从二维码扫描获取 URL
- `load_urls_from_file()` - 从 urls.txt 读取 URL  
- `select_video_type()` - 交互式选择视频类型
- `process_url()` - 单个 URL 的完整流程
- `main()` - 程序入口

## 数据流

1. **输入** → 二维码或 urls.txt
2. **二维码扫描** (OpenCV) → URL
3. **页面访问** (Selenium) → 拦截 API 参数
4. **API 调用** (requests) → 下载链接
5. **文件下载** (requests stream) → 本地存储
6. **MD5 去重** → 清理重复文件
7. **日志输出** → logs 目录

## 打包工作流

### 本地打包
```bash
.\build\build_exe.ps1  # 编译 EXE + 下载 Chrome + 打包 zip
```

### GitHub Actions 自动构建
```bash
git tag v1.0.0
git push origin v1.0.0
# Actions 自动构建并上传 Release
```

**工作流文件**：[.github/workflows/release.yml](.github/workflows/release.yml)

## API 响应结构

```json
{
  "data": {
    "name": "活动名称",
    "item_list": [
      {
        "card_info": {
          "card_name": "资源名",
          "video_list": ["无水印视频链接"],
          "video_list_download": ["有水印视频链接"],
          "card_img": "缩略图链接"
        }
      }
    ],
    "collect_list": {
      "collect_infos": [
        {
          "card_item": {
            "card_type_info": {
              "name": "资源名",
              "content": {
                "animation": {
                  "1": ["无水印动画链接"]
                }
              },
              "watermark_animations": [
                {
                  "watermark_animation": "有水印链接"
                }
              ],
              "overview_image": "缩略图链接"
            }
          }
        }
      ]
    }
  }
}
```

## 常见扩展点

- **新增下载源**：修改 `load_urls_from_*()` 函数
- **修改下载策略**：在 `Downloader.download()` 中实现
- **新增 API 字段**：在 `extract_card_downloads()` 中处理
- **改变输出格式**：修改 `process_url()` 中的文件夹结构

## PyInstaller 配置

打包脚本使用以下参数：
- `--onefile` - 单文件输出
- `--console` - 保留控制台窗口
- `--hidden-import=cv2,selenium,seleniumwire,pyzbar,requests` - 显式依赖
- `--collect-all=seleniumwire` - 收集 seleniumwire 资源文件

参考：[build/build_exe.ps1](build/build_exe.ps1)
