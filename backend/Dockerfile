# backend/Dockerfile
FROM python:3.10-slim

WORKDIR /app

# 安装系统依赖 (gunicorn 需要 gcc)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制当前目录下的所有代码 (app.py 等)
COPY . .

# 暴露端口
EXPOSE 5000

# 环境变量
ENV APP_NAME=FanFuBackend
ENV DEBUG=False

# 【关键】使用 gunicorn 启动，指向 app.py 中的 app 对象
# 格式：gunicorn --bind 0.0.0.0:5000 文件名:变量名
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
