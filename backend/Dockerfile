# 基于轻量级 Python 镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 创建非 root 用户（安全加固）
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

# 复制应用源码
COPY . .

# 暴露端口（可选）


EXPOSE 5000



# 启动命令
CMD ["python", "app.py"]