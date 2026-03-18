# 基础镜像：使用轻量级的 Python 3.11
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
# PYTHONDONTWRITEBYTECODE: 防止生成 .pyc 文件
# PYTHONUNBUFFERED: 确保日志实时输出到 stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_NAME="MyBackendApp" \
    DEBUG="False"

# 1. 先复制依赖文件 (利用 Docker 缓存机制)
# 如果 requirements.txt 未变化，这一步将直接使用缓存，加速构建
COPY requirements.txt .

# 2. 安装系统级依赖 (如果需要编译某些 Python 包，如 psycopg2, lxml 等)
# 注意：slim 镜像默认没有 gcc，如果纯 Python 包可跳过此步
# RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

# 3. 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 4. 复制项目源代码
COPY . .

# 5. 安全最佳实践：创建非 root 用户运行应用
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# 6. 暴露端口
# 虽然 app.py 默认是 5000，但生产环境 Gunicorn 通常绑定 8000
EXPOSE 8000

# 7. 健康检查 (利用 app.py 中的 /health 接口)
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# 8. 启动命令
# 使用 Gunicorn 作为 WSGI 服务器，替代 Flask 内置开发服务器
# --workers 4: 开启 4 个进程处理并发
# --bind 0.0.0.0:8000: 监听所有网卡的 8000 端口
# app:app: 指向 app.py 文件中的 app 对象
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:8000", "app:app"]
