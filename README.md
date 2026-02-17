
# B 站收藏集下载脚本

这个 Python 脚本用于自动从 B 站的收藏集中下载视频和图片。通过扫描二维码获取收藏集 URL，并使用 Selenium 和 API 提取相关资源链接，最终实现批量下载。

## 快速开始

### 最简单的方式：使用预构建 EXE（推荐）

从 [Releases](https://github.com/AliceJump/BilibiliCollectionsDownloader/releases) 下载 `BilibiliCollectionsDownloader-Standalone-Windows.zip`：

1. **解压文件**
2. **放置输入**：
   - 将收藏集分享二维码图片放入 `qrcodes` 文件夹，或
   - 编辑 `urls.txt`，每行一个链接
3. **运行程序**：
   - 双击 `start.bat`，或
   - 直接运行 `BilibiliCollectionsDownloader.exe`
4. **选择选项**：
   - 输入方式：1（二维码）或 2（urls.txt）
   - 视频类型：1（无水印）/ 2（有水印）/ 12（两者）

完全独立，无需安装 Python！

### 从源码运行

需要 Python 3.13.3：

#### 1. 安装依赖

```bash
pip install -r requirements.txt
```

#### 2. 放置 Chrome 和 ChromeDriver

```
chrome-win64/
  chrome.exe
chromedriver.exe
```

#### 3. 运行程序

```bash
python app.py
# 或
.\start.bat
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

**源码版本**（用于开发）：
```
app.py                   # 单文件主程序（包含所有功能）
requirements.txt         # 依赖列表
start.bat               # 启动脚本
qrcodes/                # 放置二维码图片
urls.txt                # 链接列表
chrome-win64/           # Chrome 浏览器
chromedriver.exe        # Chrome 驱动
dlc/                    # 下载目录（自动创建）
logs/                   # 日志目录（自动创建）
```

**编译版本**（预构建 EXE）：
```
BilibiliCollectionsDownloader.exe   # 可执行程序
start.bat                           # 启动脚本
chrome-win64/                       # Chrome 浏览器
chromedriver.exe                    # Chrome 驱动
qrcodes/                            # 放置二维码图片
urls.txt                            # 链接列表
README.md                           # 使用说明
```

### 1. 二维码未能识别
确保二维码图片路径正确，并且二维码内容为有效的 B 站收藏集分享链接。

### 2. 无法下载视频或图片
请检查 Chrome 和 ChromeDriver 的配置是否正确，确保浏览器和驱动版本匹配。
