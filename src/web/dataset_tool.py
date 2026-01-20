import os
import sys
import logging
from flask import Flask, send_from_directory
from flask_cors import CORS

# Ensure current directory is in sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from routes import register_blueprints

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

app = Flask(__name__, static_folder='dist', static_url_path='')
CORS(app)

# 注册路由
register_blueprints(app)

# 首页路由 (前端)
@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

# 静态资源路由 (Vue Router History Mode support)
@app.errorhandler(404)
def not_found(e):
    if app.static_folder:
        return send_from_directory(app.static_folder, 'index.html')
    return "Not Found", 404

if __name__ == '__main__':
    print("🎯 数据集工具启动中...")
    print("🌐 请在浏览器中打开: http://localhost:5001")
    
    # 检查 dist 目录是否存在
    dist_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dist')
    if not os.path.exists(dist_dir):
        print(f"⚠️ 警告: 前端静态文件目录 {dist_dir} 不存在。")
        print("   请确保已运行前端构建 (cd frontend && npm run build) 并将产物复制到 src/web/dist")
    
    app.run(host='0.0.0.0', port=5001, debug=True)
