from flask import Flask, render_template, request, jsonify
import os

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

# 示例API接口，可根据实际功能扩展
@app.route('/api/download', methods=['POST'])
def download():
    data = request.json
    # TODO: 调用你的下载逻辑
    return jsonify({'status': 'success', 'message': '下载任务已提交'})

if __name__ == '__main__':
    app.run(debug=True)
