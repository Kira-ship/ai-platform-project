import os
import logging
from flask import Flask, jsonify, request

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 从环境变量读取配置，支持容器化部署
APP_NAME = os.environ.get('APP_NAME', 'MyBackendApp')
DEBUG_MODE = os.environ.get('DEBUG', 'False').lower() == 'true'

@app.route('/health', methods=['GET'])
def health_check():
    """健康检查接口，用于探针和负载均衡"""
    return jsonify({
        'status': 'healthy',
        'service': APP_NAME
    }), 200

@app.route('/api/info', methods=['GET'])
def get_info():
    """返回服务基本信息"""
    return jsonify({
        'name': APP_NAME,
        'version': '1.0.0',
        'description': '樊富君的后端服务示例'
    })

@app.route('/api/echo', methods=['GET', 'POST'])
def echo():
    """回显客户端发送的 JSON 数据（示例 POST 接口）"""
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Request must be JSON'}), 400
    return jsonify({
        'received': data,
        'message': 'Echo from backend'
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.exception("Internal server error")
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    # 生产环境请使用 gunicorn 等 WSGI 服务器
    app.run(host='0.0.0.0', port=5000, debug=DEBUG_MODE)
