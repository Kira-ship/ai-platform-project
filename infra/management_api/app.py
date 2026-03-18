# infra/management_api/app.py
import os
import subprocess
from flask import Flask, jsonify, request
from pathlib import Path

app = Flask(__name__)

# 项目根目录路径 (根据实际结构调整)
BASE_DIR = Path(__file__).parent.parent.parent
SCRIPT_PATH = BASE_DIR / "infra" / "scripts" / "generate_dockerfile.py"

@app.route('/api/generate-dockerfile', methods=['POST'])
def trigger_generation():
    """
    触发 Dockerfile 生成脚本
    期望接收 JSON: {"force": true} (可选)
    """
    try:
        # 验证脚本是否存在
        if not SCRIPT_PATH.exists():
            return jsonify({'error': 'Generator script not found'}), 500

        # 执行脚本 (模拟命令行运行)
        # 注意：生产环境需注意命令注入风险，这里固定参数
        result = subprocess.run(
            ['python', str(SCRIPT_PATH), '--write'],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(BASE_DIR)
        )

        if result.returncode == 0:
            return jsonify({
                'status': 'success',
                'message': 'Dockerfile generated successfully',
                'log': result.stdout
            }), 200
        else:
            return jsonify({
                'status': 'failed',
                'error': result.stderr
            }), 500
            
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Generation timed out'}), 504
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'service': 'InfraManager'}), 200

if __name__ == '__main__':
    # 监听 0.0.0.0 以便容器外访问
    app.run(host='0.0.0.0', port=5001) 
