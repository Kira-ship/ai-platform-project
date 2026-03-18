import os
import sys
from typing import List, Dict, Any, Optional
# 从 starlette 导入重定向响应，兼容性更好
from fastapi import FastAPI, HTTPException, status
from starlette.responses import RedirectResponse
from pydantic import BaseModel, Field
from pathlib import Path

app = FastAPI(
    title="Infra Management API",
    description="基础设施自动化接口，支持环境构建、Dockerfile生成等",
    version="1.0.0"
)

# --- 数据模型定义 ---

class BuildEnvRequest(BaseModel):
    code: Dict[str, str] = Field(..., description="代码生成接口返回的files")
    dependencies: List[str] = Field(..., description="意图解析里的依赖列表")

class EnvData(BaseModel):
    dockerfile: str = Field(..., description="生成的Dockerfile内容")
    requirements_txt: str = Field(..., description="生成的requirements.txt内容")
    build_command: str = Field(..., description="Docker构建命令")
    run_command: str = Field(..., description="Docker运行命令")
    environment_ready: bool = Field(default=True, description="环境是否就绪")

class SuccessResponse(BaseModel):
    success: bool = True
    data: EnvData

class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    suggestions: List[str] = []

# --- 业务逻辑辅助函数 ---

def mock_generate_dockerfile(deps: List[str]) -> tuple[str, str]:
    req_content = "\n".join([f"{dep}" for dep in deps])
    dockerfile_content = f"""FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py"]
"""
    return dockerfile_content, req_content

def check_dependency_conflicts(deps: List[str]) -> Optional[Dict[str, Any]]:
    return None

def process_build_logic(code: Dict[str, str], dependencies: List[str]) -> SuccessResponse:
    conflict = check_dependency_conflicts(dependencies)
    if conflict:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=conflict)

    dockerfile_content, req_content = mock_generate_dockerfile(dependencies)
    entry_point = "main.py" if "main.py" in code else "app.py"
    build_cmd = "docker build -t project ."
    run_cmd = f"docker run --rm project python {entry_point}"

    return SuccessResponse(
        data=EnvData(
            dockerfile=dockerfile_content,
            requirements_txt=req_content,
            build_command=build_cmd,
            run_command=run_cmd,
            environment_ready=True
        )
    )

# --- API 路由 ---

@app.post("/build-env", response_model=SuccessResponse, responses={400: {"model": ErrorResponse}})
async def build_environment_post(request: BuildEnvRequest):
    """
    [POST] 正式调用接口
    供程序或 Swagger 文档中的 'Try it out' 使用
    """
    try:
        return process_build_logic(request.code, request.dependencies)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"内部服务器错误：{str(e)}", "suggestions": ["请稍后重试"]}
        )

@app.get("/build-env")
async def build_environment_redirect():
    """
    [GET] 浏览器访问入口
    当用户在浏览器地址栏直接访问此链接时，自动跳转到 Swagger 文档页面 (/docs)
    """
    # 核心修改：返回重定向响应，指向 /docs
    return RedirectResponse(url="/docs")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "InfraManager"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)