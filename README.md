
# B 站收藏集下载器

从 B 站收藏集中下载视频和图片。提供三种使用方式：

- **🖥️ 本地服务端模式（推荐）** — 启动轻量 Flask 服务器，后端代理 B 站 API（解决 CORS），前端展示下载链接，后端不存储任何文件
- **🌐 网页版（纯浏览器）** — 单个 HTML 文件，直接在浏览器中运行，无需安装任何依赖（可能受 CORS 限制）
- **💻 命令行版** — Python 脚本，支持批量自动下载到本地

---

## 🖥️ 本地服务端模式（推荐）

### 特点

- **解决 CORS**：后端代理转发对 `api.bilibili.com` 的请求，浏览器无跨域限制
- **不存储文件**：后端仅获取并返回下载链接，不保存任何视频或图片
- **轻量依赖**：只需 `flask` 和 `requests`

### 使用方法

1. 安装依赖：

   ```bash
   pip install flask requests
   # 或
   pip install -r requirements.txt
   ```

2. 启动服务器：

   ```bash
   python server.py
   ```

3. 用浏览器访问 <http://127.0.0.1:5000>，使用方式与网页版相同

---

## 🌐 网页版（`index.html`，纯浏览器）

### 特点

- **纯本地运行**：所有处理均在浏览器端完成，不依赖任何服务端转发
- **零安装**：只需一个 `index.html` 文件，用浏览器打开即可
- **多种输入方式**：粘贴链接 / 上传二维码 / 手动输入 ID

### 使用方法

1. 下载或克隆本仓库，直接用浏览器打开 `index.html`
2. 选择输入方式：
   - **粘贴链接**：将收藏集分享链接粘贴到文本框（每行一个）
   - **上传二维码**：上传收藏集分享二维码图片，自动识别链接
   - **手动输入 ID**：直接填写 `act_id` 和 `lottery_id`
3. 勾选需要下载的内容类型（图片 / 无水印视频 / 带水印视频）
4. 点击 **🚀 获取下载链接**
5. 在结果卡片中点击对应链接下载，或点击 **⬇️ 全部打开下载链接**

### 链接格式说明

收藏集分享链接须包含 `act_id` 和 `lottery_id` 两个参数，例如：

```
https://www.bilibili.com/h5/mall/dlc-collection?act_id=13688&lottery_id=12345
```

### 跨域（CORS）说明

浏览器的同源策略可能会阻止对 `api.bilibili.com` 的请求。如遇网络请求失败，可尝试：

- 安装浏览器扩展 **CORS Unblock**（Chrome/Edge）后重试
- 或以以下参数启动 Chrome（仅用于本地调试）：
  ```
  chrome.exe --disable-web-security --user-data-dir=C:\tmp\nocsec
  ```

---

## 🖥️ 命令行版

### 最简单的方式：使用便携版Python包（推荐）

从 [Releases](https://github.com/AliceJump/BilibiliCollectionsDownloader/releases) 下载 `BiliCollectionDownloader.7z`：

1. **解压文件**
2. **放置输入**：
   - 将收藏集分享二维码图片放入 `qrcodes` 文件夹，或
   - 编辑 `urls.txt`，每行一个链接
3. **运行程序**：
   - 双击 `start.bat`
4. **选择选项**：
   - 输入方式：1（二维码）或 2（urls.txt）
   - 视频类型：1（无水印）/ 2（有水印）/ 12（两者）


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
server.py                # 本地服务端（Flask 代理，推荐）
index.html               # 网页版前端（也可单独用浏览器打开）
requirements.txt         # 服务端依赖（flask, requests）
app.py                   # 命令行版主程序（包含所有功能）
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

## 常见问题

### 1. 二维码未能识别（命令行版）
确保二维码图片路径正确，并且二维码内容为有效的 B 站收藏集分享链接。

### 2. 无法下载视频或图片（命令行版）
请检查 Chrome 和 ChromeDriver 的配置是否正确，确保浏览器和驱动版本匹配。
