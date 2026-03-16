# generate_dockerfile.py

from jinja2 import Template

DOCKERFILE_TEMPLATE = """
# 基于轻量级 Python 镜像
FROM python:{{ python_version }}-slim

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 创建非 root 用户（安全加固）
RUN useradd --create-home --shell /bin/bash appuser \\
    && chown -R appuser:appuser /app
USER appuser

# 复制应用源码
COPY . .

# 暴露端口（可选）
{% if exposed_ports %}
{% for port in exposed_ports %}
EXPOSE {{ port }}
{% endfor %}
{% endif %}

# 启动命令
CMD ["python", "{{ entry_point }}"]
""".strip()


def generate_dockerfile(
    dependencies,
    entry_point="main.py",
    python_version="3.9",
    exposed_ports=None,
    output_path="Dockerfile"
):
    # 生成 requirements.txt
    with open("requirements.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(dependencies))
    
    # 渲染 Dockerfile
    template = Template(DOCKERFILE_TEMPLATE)
    content = template.render(
        python_version=python_version,
        entry_point=entry_point,
        exposed_ports=exposed_ports or []
    )
    
    # 写入 Dockerfile
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    return content


if __name__ == "__main__":
    config = {
        "dependencies": ["flask==2.3.0", "requests"],
        "entry_point": "app.py",
        "python_version": "3.10",
        "exposed_ports": [5000]
    }
    dockerfile_str = generate_dockerfile(**config)
    print("✅ Dockerfile 和 requirements.txt 已生成！")
    print("\nDockerfile 内容预览：")
    print("-" * 50)
    print(dockerfile_str)