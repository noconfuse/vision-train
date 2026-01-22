import os
import sys
import logging
from flask import Flask
from flask_cors import CORS

# Ensure current directory is in sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from routes import register_blueprints

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

app = Flask(__name__)
CORS(app)

# 注册路由
register_blueprints(app)

if __name__ == '__main__':
    print("🎯 数据集工具后端启动中...")
    print("🌐 API 服务地址: http://localhost:5001")
    
    app.run(host='0.0.0.0', port=5001, debug=True)
