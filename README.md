
# B 站收藏集下载脚本

这个 Python 脚本用于自动从 B 站的收藏集中下载视频和图片。通过扫描二维码获取收藏集 URL，并使用 Selenium 和 API 提取相关资源链接，最终实现批量下载。

## 使用须知
### 可以使用我打包的软件包
#### 1.在qrcodes文件夹内放置带有收藏集分享二维码的图片(.jpg或.png)
#### 2.然后点击"start.bat"文件则开始下载过程
## 或遵循以下步骤
### 1. 安装依赖
你可以通过以下命令安装依赖：
```bash
pip install pyzbar selenium-wire setuptools opencv-python requests selenium
```
执行完上面的命令后执行
```bash
pip install blinker==1.7.0
```

### 2. 环境配置
- 下载并配置 Chrome 浏览器
- 下载并配置 ChromeDriver（确保版本与您的 Chrome 浏览器版本匹配）。

### 3. 配置常量
修改py文件内以下常量以适应您的环境：
- `CHROME_BROWSER_PATH`：指向您本地的 Chrome 浏览器可执行文件路径。
- `CHROME_DRIVER_PATH`：指向与 Chrome 版本匹配的 ChromeDriver 可执行文件路径。
- `QRCODE_IMAGE_PATH`：指向保存二维码图片的目录，二维码图片可以通过分享收藏集页面后保存的二维码文件获得。

### 4. 下载视频和图片
脚本将扫描存放二维码的文件夹（`qrcodes`），提取二维码中包含的 URL，访问该 URL 获取收藏集信息，进而下载视频和图片。

### 5. 配置下载选项
- `VIDEO_WATER_TYPE`：设置为 `True` 时下载高质量水印版视频，设置为 `False` 时下载无水印版视频。

## 使用方法

1. 将二维码图片文件(可以在收藏集页面点击分享后保存图片)放入 `qrcodes` 文件夹。
2. 修改脚本中的常量配置。
3. 运行脚本，程序将自动扫描二维码并下载对应的视频和图片。

```bash
python bilicollectiondownloader.py
```

### 输出文件结构
下载的视频和图片将被存储在 `dlc` 目录下，按照活动名称和资源类型（视频/图片）进行分类。


## 日志
脚本会在终端输出日志信息，包括下载进度、错误信息以及去重过程。

## 常见问题

### 1. 二维码未能识别
确保二维码图片路径正确，并且二维码内容为有效的 B 站收藏集分享链接。

### 2. 无法下载视频或图片
请检查 Chrome 和 ChromeDriver 的配置是否正确，确保浏览器和驱动版本匹配。
