#!/usr/bin/env python3
"""
Dockerfile 动态生成器 (增强版)
用于解析 backend/ 目录下的 requirements.txt 和 app.py，
自动生成优化的生产级 Dockerfile。

功能特点:
- 自动检测 Gunicorn/Uvicorn/Flask
- 智能端口推断
- 非 Root 用户安全运行
- 支持 CLI 参数定制
"""

import os
import re
import sys
import logging
import argparse
from pathlib import Path
from typing import Optional, Dict, List

# 配置日志
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

def parse_requirements(req_path: str) -> Dict:
    """解析 requirements.txt，提取关键依赖信息"""
    deps = {
        'has_gunicorn': False,
        'has_uvicorn': False,
        'has_flask': False,
        'raw_lines': []
    }
    
    if not os.path.exists(req_path):
        logger.error(f"❌ 找不到依赖文件: {req_path}")
        return deps

    logger.info(f"📄 正在解析依赖文件: {req_path}")
    with open(req_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            deps['raw_lines'].append(line)
            
            # 提取包名 (处理 ==, >=, <=, ~= 等情况)
            pkg_name = re.split(r'[=<>~!]', line)[0].lower().strip()
            
            if pkg_name == 'gunicorn':
                deps['has_gunicorn'] = True
            elif pkg_name == 'uvicorn':
                deps['has_uvicorn'] = True
            elif pkg_name == 'flask':
                deps['has_flask'] = True
                
    return deps

def parse_app_port(app_path: str) -> int:
    """尝试从 app.py 中解析运行端口"""
    default_port = 8000 
    
    if not os.path.exists(app_path):
        logger.warning(f"⚠️ 找不到应用入口文件: {app_path}, 将使用默认端口 {default_port}")
        return default_port

    with open(app_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    patterns = [
        r'app\.run\s*\([^)]*port\s*=\s*(\d+)',          # Flask: app.run(port=5000)
        r'uvicorn\.run\s*\([^)]*port\s*=\s*(\d+)',      # Uvicorn: uvicorn.run(..., port=8000)
        r'context\.run\s*\([^)]*port\s*=\s*(\d+)',      # 其他常见模式
    ]
    
    for pattern in patterns:
        match = re.search(pattern, content)
        if match:
            port = int(match.group(1))
            logger.info(f"🔍 从代码中检测到端口配置: {port}")
            # 生产环境建议统一使用 8000 或 5000，这里我们尊重代码配置，但给出提示
            return port
    
    logger.info(f"ℹ️ 未检测到显式端口配置，使用生产默认端口: {default_port}")
    return default_port

def determine_startup_cmd(has_gunicorn: bool, has_uvicorn: bool, has_flask: bool, port: int) -> str:
    """根据依赖决定启动命令"""
    
    # 优先级: Gunicorn (Flask/Django) > Uvicorn (FastAPI) > Python Direct
    if has_gunicorn:
        logger.info("✅ 检测到 Gunicorn，将使用生产级启动命令")
        return f'CMD ["gunicorn", "--workers", "4", "--threads", "2", "--bind", "0.0.0.0:{port}", "app:app"]'
    
    elif has_uvicorn:
        logger.info("✅ 检测到 Uvicorn，将使用 ASGI 启动命令")
        # 假设入口是 app:app 或 main:app，这里默认 app:app，实际可能需要更复杂的解析
        return f'CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "{port}"]'
    
    else:
        logger.warning("⚠️ 未检测到 Gunicorn 或 Uvicorn。")
        logger.warning("   生成的 Dockerfile 将使用 'python app.py' (仅适合开发/测试)。")
        logger.warning("   🚨 生产环境强烈建议安装 gunicorn 或 uvicorn！")
        return f'CMD ["python", "app.py"]'

def generate_dockerfile_content(target_port: int, startup_cmd: str, base_image: str = "python:3.11-slim") -> str:
    """生成 Dockerfile 字符串内容"""
    
    dockerfile_template = f"""# 🤖 自动生成的 Dockerfile
# 基础镜像：{base_image}
# 暴露端口：{target_port}

FROM {base_image}

# 设置工作目录
WORKDIR /app

# 环境变量配置
# PYTHONDONTWRITEBYTECODE: 防止生成 .pyc 文件
# PYTHONUNBUFFERED: 确保日志实时输出到 stdout
ENV PYTHONDONTWRITEBYTECODE=1 \\
    PYTHONUNBUFFERED=1 \\
    APP_ENV="production" \\
    PORT="{target_port}"

# 1. 安装系统级依赖 (如果需要编译 C 扩展，请取消下面注释)
# RUN apt-get update && apt-get install -y --no-install-recommends gcc python3-dev && rm -rf /var/lib/apt/lists/*

# 2. 复制依赖文件以利用 Docker 层缓存
COPY requirements.txt .

# 3. 安装 Python 依赖
RUN pip install --no-cache-dir --upgrade pip && \\
    pip install --no-cache-dir -r requirements.txt

# 4. 复制源代码
# 注意：此时还是以 root 身份复制
COPY . .

# 5. 安全加固：创建非 root 用户并赋予权限
# 创建用户 appuser (UID 1000)
RUN useradd -m -u 1000 appuser
# 修改应用目录所有权
RUN chown -R appuser:appuser /app
# 切换到非 root 用户
USER appuser

# 6. 暴露端口
EXPOSE {target_port}

# 7. 健康检查
# 使用 python 内置库进行轻量级检查，避免安装 curl 增加镜像体积
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \\
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:{target_port}/health')" || exit 1

# 8. 启动命令
{startup_cmd}
"""
    return dockerfile_template

def main():
    parser = argparse.ArgumentParser(description="动态生成优化的 Dockerfile")
    parser.add_argument("--write", action="store_true", help="直接写入文件而不是打印到屏幕")
    parser.add_argument("--output", type=str, default=None, help="指定输出文件路径 (默认: backend/Dockerfile)")
    parser.add_argument("--base-image", type=str, default="python:3.11-slim", help="指定基础镜像 (默认: python:3.11-slim)")
    parser.add_argument("--backend-dir", type=str, default=None, help="指定 backend 目录路径 (默认: 自动推断)")
    
    args = parser.parse_args()

    # 路径推断逻辑
    script_dir = Path(__file__).parent.resolve()
    
    if args.backend_dir:
        backend_dir = Path(args.backend_dir).resolve()
        project_root = backend_dir.parent
    else:
        # 默认假设脚本在 infra/scripts/, backend 在项目根目录的 backend/
        project_root = script_dir.parent.parent 
        backend_dir = project_root / "backend"
    
    req_file = backend_dir / "requirements.txt"
    app_file = backend_dir / "app.py"
    output_file = Path(args.output) if args.output else backend_dir / "Dockerfile"

    logger.info(f"🚀 开始分析项目...")
    logger.info(f"📂 项目根目录: {project_root}")
    logger.info(f"📂 Backend 目录: {backend_dir}")

    if not backend_dir.exists():
        logger.error(f"❌ Backend 目录不存在: {backend_dir}")
        sys.exit(1)

    # 1. 解析依赖
    deps = parse_requirements(str(req_file))
    
    # 2. 解析端口
    port = parse_app_port(str(app_file))
    
    # 3. 确定启动命令
    startup_cmd = determine_startup_cmd(
        deps['has_gunicorn'], 
        deps['has_uvicorn'], 
        deps['has_flask'], 
        port
    )
    
    # 4. 生成内容
    content = generate_dockerfile_content(port, startup_cmd, args.base_image)
    
    # 5. 输出策略
    if args.write:
        try:
            # 确保输出目录存在
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"✅ 成功! Dockerfile 已保存至: {output_file}")
        except Exception as e:
            logger.error(f"❌ 写入文件失败: {e}")
            sys.exit(1)
    else:
        print("\n" + "="*50)
        print("📄 生成的 Dockerfile 预览:")
        print("="*50 + "\n")
        print(content)
        print("="*50)
        logger.info("💡 提示: 添加 '--write' 参数直接保存文件。")
        logger.info(f"   示例: python {sys.argv[0]} --write")

if __name__ == "__main__":
    main()
