
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
| 桌面应用 | 嵌入式 Python、原生窗口、一键运行 | **推荐** Windows 用户 |
| 网页界面 | 浏览器访问、本地服务、交互直观 | 日常网页操作 |
| 服务端模式 | Flask 后端代理、无 CORS 限制 | API 调用 |

---

## 桌面应用模式（嵌入式 Python）

### 特点

- **原生窗口** — 使用 `pywebview` 嵌套 Flask，系统原生窗口渲染
- **一键运行** — 支持内嵌运行时，无需安装 Python
- **解决 CORS** — 本地 Flask 代理转发 B 站 API，无跨域限制

### 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt
pip install pyinstaller "pywebview[edgechromium]"

# 2. 运行
# 依赖内嵌 Python 运行时，无需额外打包
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

## 下载文件结构

当前版本的下载行为如下：

```shell
浏览器模式（默认）
└── 由浏览器下载到系统“下载”目录
   └── <合集名>_<类型>.zip

应用模式（pywebview）
└── downloads/
   └── <合集名>_<类型>.zip
```

## 项目结构

### 源码版本（开发用）

```shell
├── .github/                   # GitHub Actions 工作流
│   └── workflows/
│       └── build.yaml
├── app.py                    # 桌面应用入口（pywebview + Flask，可打包 EXE）
├── server.py                 # 本地服务端（Flask 代理）
├── run_web.py                # 本地网页服务启动入口
├── index.html                # 网页版前端
├── templates/
│   └── index.html            # Flask 模板页
├── web.py                    # 旧版模板示例（未作为主入口）
├── requirements.txt          # 运行时依赖
├── dev-requirements.txt      # 开发依赖
├── start.bat                 # 启动器（调用 start.ps1）
├── start.ps1                 # 启动菜单脚本（PowerShell）
├── downloads/                # 应用模式压缩包保存目录（自动创建）
└── logs/                     # 日志目录（自动创建）
```

打包产物目录（本地构建后可能出现）：

```shell
├── build/                    # 打包中间产物
└── dist/                     # 打包输出目录
```

---

## 常见问题

### 1. 网页界面打不开或请求失败

请先确认已启动本地服务（`python run_web.py` 或 `python server.py`），并通过  
`http://127.0.0.1:5000` 访问，而不是直接打开 `index.html` 文件。

### 2. 桌面窗口无法启动

请确认已安装依赖并通过 `python app.py` 启动；如果是 Windows，请确认系统可用 Microsoft Edge WebView2 运行时。

---

[![MIT License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)

Made with ❤ by [AliceJump](https://github.com/AliceJump)
