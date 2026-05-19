
# B 站收藏集下载器

[![Python](https://img.shields.io/badge/Python-3.12+-3776ab?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](./LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078d4?style=flat-square&logo=windows)](https://www.microsoft.com/windows)

从 B 站收藏集中一键下载视频和图片 | 支持多种使用模式 | 开箱即用

</div>

---

## 使用模式

| 模式 | 特点 | 适用场景 |
| ------ | ------ | -------- |
| 服务端模式 | 轻量 Flask、后端代理、无 CORS 限制 | **推荐** 日常使用 |
| 网页界面 | 浏览器访问、本地服务提供 API、交互直观 | 日常网页操作 |
| 命令行版 | 批量处理、自动化下载 | 批量操作 |
| 桌面应用 | EXE 打包、原生窗口、一键运行 | Windows 用户 |

---

## 桌面应用模式（EXE 打包）

### 特点

- **原生窗口** — 使用 `pywebview` 嵌套 Flask，系统原生窗口渲染
- **一键运行** — 单个 `BiliCollectionDownloader.exe`，无需安装 Python
- **解决 CORS** — 本地 Flask 代理转发 B 站 API，无跨域限制

### 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt
pip install pyinstaller "pywebview[edgechromium]"

# 2. 打包
pyinstaller build.spec

# 3. 运行
# 输出文件：dist/BiliCollectionDownloader.exe
```

### 直接运行（不打包）

```bash
python app.py
```

> **Windows 提示**：`pywebview` 的 `edgechromium` 后端需要 Microsoft Edge WebView2 运行时（Windows 10/11 已内置）。如遇问题，请到 [微软官网](https://developer.microsoft.com/microsoft-edge/webview2/) 下载。

---

## 本地服务端模式

### 特点

- **解决 CORS** — 后端代理转发 API，无跨域限制
- **不存储文件** — 仅返回下载链接，不保存任何内容
- **轻量依赖** — 依赖 `flask`、`requests`、`bilibili-api-python`

### 使用步骤

```bash
# 1. 安装依赖
pip install flask requests bilibili-api-python
# 或
pip install -r requirements.txt

# 2. 启动服务器
python server.py

# 3. 访问
# 浏览器打开：http://127.0.0.1:5000
```

---

## 网页界面模式

### 特点

- **浏览器操作** — 使用网页界面完成参数输入与批量下载
- **本地服务支持** — 通过 Flask 提供 `/api/*` 接口，避免跨域问题
- **多种输入** — `act_id` / 含 `act_id` 的链接 / b23 短链 / 二维码

### 使用步骤

1. **启动本地服务**（任选其一）：

```bash
python run_web.py
# 或
python server.py
```

2. **打开页面**：浏览器访问 `http://127.0.0.1:5000`

3. **输入内容**（任选其一）：

   • 输入 `act_id`
   • 粘贴链接   — 含 `act_id` 的完整链接或 b23 短链
   • 上传二维码 — 上传收藏集分享二维码图片

4. **选择类型**：勾选要下载的内容

```shell
   □ 图片
   □ 无水印视频
   □ 带水印视频
```

5. **获取链接**：点击 **获取下载链接**

6. **下载文件**：点击卡片中的链接或点击 **下载全部**

### 链接格式示例

> <https://www.bilibili.com/h5/mall/dlc-collection?act_id=13688&lottery_id=12345>

分享链接至少需要能解析出 `act_id`（完整链接通常同时包含 `lottery_id`）。

> 注意：当前网页界面依赖本地后端接口，请不要直接双击 `index.html` 打开。

---

## 命令行版

### 快速方式（推荐）

从 [Releases](https://github.com/AliceJump/BilibiliCollectionsDownloader/releases) 下载便携包：

`BilibiliCollectionsDownloader-portable-windows.zip`

**快速开始**：

```bash
1. 解压文件夹

2. 放置输入内容（选一个）：
• 方案 A：将二维码图片放入 qrcodes/ 文件夹
• 方案 B：编辑 urls.txt，每行一个链接

3. 双击运行
start.bat

4. 按提示选择：
• 先选模式：1（App 版本）→ 桌面窗口模式
• 再选输入方式：1（二维码）或 2（urls.txt）
• 再选视频类型：1（无水印）/ 2（有水印）/ 12（两者）
```

### 从源码运行

**系统要求**：Python 3.12.7+

```bash
1. 安装依赖
pip install -r requirements.txt

2. 配置 Chrome
需要将以下文件放在项目根目录：
├── chrome-win64/chrome.exe
└── chromedriver.exe

3. 运行程序
python main.py
或
.\start.bat
```

> **说明**：打包后的 EXE 仅保留桌面窗口模式，不再提供 `--cli` 终端模式；如果需要命令行交互，请直接运行 `python main.py`。

### 下载文件结构

下载的文件会按活动和类型自动分类：

```shell
dlc/
└── <活动名>/
    ├── video/           # 无水印视频
    ├── watermark_video/ # 有水印视频
    └── img/             # 图片
```

## 项目结构

### 源码版本（开发用）

```shell
├── app.py                    # 桌面应用入口（pywebview + Flask，可打包 EXE）
├── server.py                 # 本地服务端（Flask 代理）
├── run_web.py                # 本地网页服务启动入口
├── index.html                # 网页版前端
├── web.py                    # 旧版模板示例（未作为主入口）
├── main.py                   # 命令行版主程序
├── requirements.txt          # 运行时依赖
├── dev-requirements.txt      # 开发依赖
├── build.spec                # PyInstaller 打包配置
├── start.bat                 # 启动器（调用 start.ps1）
├── start.ps1                 # 启动菜单脚本（PowerShell）
├── qrcodes/                  # 二维码存放目录（运行时自动创建）
├── urls.txt                  # 链接列表（运行时自动创建）
├── chrome-win64/             # Chrome 浏览器（主程序按需提供）
├── chromedriver.exe          # Chrome 驱动（主程序按需提供）
├── dlc/                      # 下载目录（自动创建）
└── logs/                     # 日志目录（自动创建）
```

### 编译版本（预构建 EXE）

```shell
├── BiliCollectionDownloader.exe                # 可执行程序
├── start.bat                                   # 启动器（调用 start.ps1）
├── start.ps1                                   # 启动菜单脚本（PowerShell）
├── python/                                     # 嵌入式 Python 运行时
├── run_web.py                                  # 本地网页服务启动入口
├── server.py                                   # Flask 后端
├── index.html                                  # 网页前端
├── requirements.txt                            # 依赖清单
└── README.md                                   # 使用说明
```

---

## 常见问题

### 1. 二维码未能识别（命令行版）

确保二维码图片路径正确，并且二维码内容为有效的 B 站收藏集分享链接。

### 2. 无法下载视频或图片（命令行版）

请检查 Chrome 和 ChromeDriver 的配置是否正确，确保浏览器和驱动版本匹配。

### 3. 网页界面打不开或请求失败

请先确认已启动本地服务（`python run_web.py` 或 `python server.py`），并通过  
`http://127.0.0.1:5000` 访问，而不是直接打开 `index.html` 文件。

---

[![MIT License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)

Made with ❤ by [AliceJump](https://github.com/AliceJump)
