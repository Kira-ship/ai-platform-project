import os
import logging
from flask import Flask, jsonify, request
# 引入 CORS 支持 (需安装 flask-cors: pip install flask-cors)
from flask_cors import CORS

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
# 启用 CORS，允许所有来源访问 (生产环境建议限制具体域名)
CORS(app)

# 从环境变量读取配置
APP_NAME = os.environ.get('APP_NAME', 'MyBackendApp')
DEBUG_MODE = os.environ.get('DEBUG', 'False').lower() == 'true'

@app.route('/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    logger.info("Health check requested")
    return jsonify({
        'status': 'healthy',
        'service': APP_NAME,
        'debug_mode': DEBUG_MODE
    }), 200

@app.route('/api/info', methods=['GET'])
def get_info():
    """返回服务基本信息"""
    return jsonify({
        'name': APP_NAME,
        'version': '1.0.1', # 版本号微调，表示已更新
        'description': '樊富君的后端服务示例 (已优化)',
        'endpoints': ['/health', '/api/info', '/api/echo']
    })

@app.route('/api/echo', methods=['POST'])
def echo():
    """
    回显客户端发送的 JSON 数据
    仅支持 POST 方法，强制要求 Content-Type: application/json
    """
    # 1. 检查 Content-Type
    if not request.is_json:
        logger.warning(f"Received non-JSON request from {request.remote_addr}")
        return jsonify({
            'error': 'Unsupported Media Type',
            'message': 'Request Content-Type must be application/json'
        }), 415

    # 2. 尝试获取 JSON 数据
    try:
        data = request.get_json(force=False, silent=False)
    except Exception as e:
        logger.error(f"JSON parsing error: {str(e)}")
        return jsonify({
            'error': 'Bad Request',
            'message': 'Invalid JSON format'
        }), 400

    # 3. 检查数据是否为空
    if data is None:
        return jsonify({
            'error': 'Bad Request',
            'message': 'Request body cannot be empty or null'
        }), 400

    # 4. 记录日志并返回
    logger.info(f"Received data from {request.remote_addr}: {data}")
    
    return jsonify({
        'received': data,
        'message': 'Echo successful',
        'server_name': APP_NAME
    }), 200

# 专门处理 405 错误 (方法不允许)，给出更友好的提示
@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        'error': 'Method Not Allowed',
        'message': f'The method {request.method} is not allowed for this endpoint. Please use POST.'
    }), 405

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found', 'path': request.path}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.exception("Internal server error occurred")
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    # ⚠️ 注意：
    # 1. 开发环境可以直接运行此文件
    # 2. 生产环境 (Docker) 请务必使用 gunicorn:
    #    gunicorn -w 4 -b 0.0.0.0:5000 app:app
    logger.info(f"Starting {APP_NAME} in debug mode: {DEBUG_MODE}")
    app.run(host='0.0.0.0', port=5000, debug=DEBUG_MODE)
