import os
import logging
from flask import Flask, jsonify, request
from flask_cors import CORS  # 1. 引入 CORS 模块

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 2. 启用 CORS：允许所有域名访问（开发环境专用）
# 生产环境建议限制为特定域名，如：CORS(app, origins=["http://your-frontend.com"])
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
        'service': APP_NAME
    }), 200

@app.route('/api/info', methods=['GET'])
def get_info():
    """返回服务基本信息"""
    logger.info("Info requested")
    return jsonify({
        'name': APP_NAME,
        'version': '1.0.0',
        'description': '樊富君的后端服务示例 (已开启跨域支持)',
        'endpoints': [
            {'path': '/health', 'method': 'GET'},
            {'path': '/api/info', 'method': 'GET'},
            {'path': '/api/echo', 'method': 'POST'}
        ]
    })

@app.route('/api/echo', methods=['POST', 'OPTIONS']) # 3. 显式支持 OPTIONS 预检请求
def echo():
    """回显客户端发送的 JSON 数据"""
    # 处理浏览器的预检请求 (OPTIONS)
    if request.method == 'OPTIONS':
        return '', 200

    # 4. 增强容错：强制按 JSON 解析，即使头信息不全
    try:
        data = request.get_json(force=True, silent=True)
        if data is None:
            # 如果解析失败且没有数据，返回友好提示
            return jsonify({'error': 'Invalid or empty JSON body', 'hint': 'Please send valid JSON like {"key": "value"}'}), 400
        
        logger.info(f"Received data: {data}") # 打印接收到的数据方便调试
        
        return jsonify({
            'received': data,
            'message': 'Echo from backend successfully!',
            'success': True
        })
    except Exception as e:
        logger.error(f"Error parsing JSON: {str(e)}")
        return jsonify({'error': 'Failed to process JSON', 'details': str(e)}), 400

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found', 'available_routes': ['/health', '/api/info', '/api/echo']}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.exception("Internal server error occurred")
    return jsonify({'error': 'Internal server error', 'message': 'Please contact the administrator'}), 500

if __name__ == '__main__':
    logger.info(f"Starting {APP_NAME} on port 5000...")
    # host='0.0.0.0' 允许外部访问，不仅仅是 localhost
    app.run(host='0.0.0.0', port=5000, debug=DEBUG_MODE)
