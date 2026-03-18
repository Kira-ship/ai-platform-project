#!/usr/bin/env python3
"""
Dockerfile 动态生成器
用于解析 backend/ 目录下的 requirements.txt 和 app.py，
自动生成优化的生产级 Dockerfile。
"""

import os
import re
import sys
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def parse_requirements(req_path: str) -> dict:
    """解析 requirements.txt，提取关键依赖信息"""
    deps = {
        'has_gunicorn': False,
        'has_flask': False,
        'raw_lines': []
    }
    
    if not os.path.exists(req_path):
        logger.error(f"找不到依赖文件: {req_path}")
        return deps

    with open(req_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            deps['raw_lines'].append(line)
            pkg_name = re.split(r'[>=<]', line)[0].lower()
            
            if pkg_name == 'gunicorn':
                deps['has_gunicorn'] = True
            elif pkg_name == 'flask':
                deps['has_flask'] = True
                
    return deps

def parse_app_port(app_path: str) -> int:
    """尝试从 app.py 中解析 Flask 运行的端口"""
    default_port = 8000 # 生产环境默认端口
    
    if not os.path.exists(app_path):
        logger.warning(f"找不到应用文件: {app_path}, 使用默认端口 {default_port}")
        return default_port

    with open(app_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # 正则匹配 app.run(..., port=XXXX, ...)
    # 匹配模式：port= 5000 或 port=5000
    match = re.search(r'app\.run\s*\([^)]*port\s*=\s*(\d+)', content)
    if match:
        port = int(match.group(1))
        logger.info(f"从代码中检测到 Flask 开发端口: {port}")
        # 注意：生产环境 Gunicorn 通常不使用开发端口，这里仅做记录或逻辑判断
        # 为了安全规范，我们强制返回 8000，除非有特殊逻辑需要保留原端口
        return 8000 
    
    logger.info(f"未检测到显式端口配置，使用生产默认端口: {default_port}")
    return default_port

def generate_dockerfile_content(has_gunicorn: bool, target_port: int) -> str:
    """生成 Dockerfile 字符串内容"""
    
    # 如果没有 gunicorn，给出警告提示（但在生成时仍假设用户会安装或手动处理）
    startup_cmd = f'CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:{target_port}", "app:app"]'
    
    if not has_gunicorn:
        logger.warning("⚠️  warnings: requirements.txt 中未检测到 'gunicorn'。")
        logger.warning("   生成的 Dockerfile 将尝试使用 gunicorn，构建可能会失败。")
        logger.warning("   建议在 requirements.txt 中添加 'gunicorn>=20.1.0'")
        # 备选方案：如果确实没有 gunicorn，只能退回到 flask run (不推荐生产环境)
        # startup_cmd = f'CMD ["python", "app.py"]' 

    dockerfile_template = f"""# 自动生成的 Dockerfile
# 生成时间: 由 generate_dockerfile.py 动态生成
# 基础镜像：Python 3.11 Slim
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 环境变量配置
ENV PYTHONDONTWRITEBYTECODE=1 \\
    PYTHONUNBUFFERED=1 \\
    APP_NAME="MyBackendApp" \\
    DEBUG="False"

# 1. 复制依赖文件以利用缓存
COPY requirements.txt .

# 2. 安装依赖
# 如果需要在 slim 镜像中编译 C 扩展，请取消下面注释
# RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt

# 3. 复制源代码
COPY . .

# 4. 安全加固：创建非 root 用户
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# 5. 暴露端口
EXPOSE {target_port}

# 6. 健康检查 (假设 /health 接口存在)
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \\
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:{target_port}/health')" || exit 1

# 7. 启动命令
{startup_cmd}
"""
    return dockerfile_template

def main():
    # 定义路径 (相对于脚本所在位置的上级目录结构)
    # 假设脚本在 infra/scripts/, 项目在根目录
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent # 回到 my-dachuang-test/
    
    backend_dir = project_root / "backend"
    req_file = backend_dir / "requirements.txt"
    app_file = backend_dir / "app.py"
    output_file = backend_dir / "Dockerfile"

    logger.info(f"🔍 正在分析项目结构: {project_root}")

    # 1. 解析依赖
    deps = parse_requirements(str(req_file))
    
    # 2. 解析端口
    port = parse_app_port(str(app_file))
    
    # 3. 生成内容
    content = generate_dockerfile_content(deps['has_gunicorn'], port)
    
    # 4. 输出策略
    # 如果有输出文件参数，则写入文件，否则打印到 stdout
    if len(sys.argv) > 1 and sys.argv[1] == "--write":
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"✅ Dockerfile 已成功生成并保存至: {output_file}")
    else:
        # 默认打印到屏幕，方便预览或重定向
        print(content)
        logger.info("💡 提示: 使用 '--write' 参数直接将结果保存为 backend/Dockerfile")

if __name__ == "__main__":
    main()
