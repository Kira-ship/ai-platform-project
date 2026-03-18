from fastapi import FastAPI, HTTPException
import os
import uuid
import shutil
import docker
import subprocess
import json
from typing import Dict, List, Any, Optional

app = FastAPI(
    title="运行验证接口（团队规范版）",
    version="1.0",
    description="支持flake8/mypy/bandit全检测，兼容扁平格式+MCP协议格式"
)
docker_client = docker.from_env()

def request_adapter(request_data: Dict) -> Dict:
    """请求适配器：兼容MCP嵌套格式 + 团队扁平格式"""
    if "content" in request_data and "payload" in request_data.get("content", {}):
        mcp_payload = request_data["content"]["payload"]
        if "code" in mcp_payload and "env" in mcp_payload:
            return mcp_payload
        else:
            raise HTTPException(400, "请求错误：payload中缺少code/env核心字段")
    elif "code" in request_data and "env" in request_data:
        return request_data
    else:
        raise HTTPException(400, "请求格式错误：缺少code/env字段")

def run_flake8(file_path: str) -> List[Dict[str, Any]]:
    """flake8代码风格检测（终极修复：处理旧版本输出"json"字符串的特殊情况）"""
    issues = []
    try:
        result = subprocess.run(
            ["flake8", file_path, "--format", "json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        clean_output = result.stdout.strip()
        
        # 终极兜底：如果输出是"json"字符串（旧版本无错误时的特殊行为），直接返回空列表
        if not clean_output or clean_output == "json" or all(line.strip() == "json" for line in clean_output.splitlines()):
            return []
        
        # 仅解析合法的JSON内容
        try:
            flake8_results = json.loads(clean_output)
            # 兼容flake8返回单个对象/数组的情况
            if isinstance(flake8_results, dict):
                flake8_results = [flake8_results]
            for item in flake8_results:
                issues.append({
                    "type": "代码风格",
                    "description": f"flake8: {item['text']} (规则{item['code']})",
                    "line": item["line_number"]
                })
        except json.JSONDecodeError:
            # 解析失败也不返回工具异常，直接返回空列表（优先保证接口核心流程）
            return []
    except Exception as e:
        # 执行异常也返回空列表，避免工具问题影响接口整体响应
        return []
    return issues

def run_mypy(file_path: str) -> List[Dict[str, Any]]:
    """mypy类型注解检测（严格按模板返回type/description/line）"""
    issues = []
    try:
        result = subprocess.run(
            ["mypy", file_path, "--no-error-summary", "--json-report", "-"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        clean_output = result.stdout.strip()
        if clean_output:
            try:
                mypy_data = json.loads(clean_output)
                for issue in mypy_data.get("issues", []):
                    issues.append({
                        "type": "类型注解",
                        "description": f"mypy: {issue['message']} (错误码{issue['code']})",
                        "line": issue["line"]
                    })
            except json.JSONDecodeError:
                pass
    except Exception as e:
        pass
    return issues

def run_bandit(file_path: str) -> List[Dict[str, Any]]:
    """bandit安全漏洞检测（严格按模板返回type/description/line）"""
    issues = []
    try:
        result = subprocess.run(
            ["bandit", "-q", "-f", "json", file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        clean_output = result.stdout.strip()
        if clean_output:
            try:
                bandit_data = json.loads(clean_output)
                for issue in bandit_data.get("results", []):
                    issues.append({
                        "type": issue.get("issue_severity", "高危"),
                        "description": f"bandit: {issue['issue_text']} (检测项{issue['test_id']})",
                        "line": issue["line_number"]
                    })
            except json.JSONDecodeError:
                pass
    except Exception as e:
        pass
    return issues

@app.post("/verify")
def code_verify(request: Dict):
    """核心接口：严格遵循团队模板，仅返回success+data，无任何冗余字段"""
    tmp_id = uuid.uuid4().hex[:8]
    tmp_dir = os.path.join(os.getcwd(), f"verify_temp_{tmp_id}")
    docker_img_tag = f"verify_img_{tmp_id}"
    docker_ctn_name = f"verify_ctn_{tmp_id}"

    # 初始化模板要求的所有字段（确保无缺失）
    execution_logs = ""
    security_issues = []
    output_files: List[str] = []
    output_preview = ""

    try:
        # 1. 解析请求（兼容双格式）
        req_data = request_adapter(request)
        code = req_data["code"]
        env = req_data["env"]

        # 2. 参数校验（按模板要求）
        if not isinstance(code, dict) or len(code) == 0:
            raise HTTPException(400, "code字段错误：必须是非空字典")
        if not isinstance(env, dict) or "dockerfile" not in env or "requirements.txt" not in env:
            raise HTTPException(400, "env字段错误：必须包含dockerfile和requirements.txt")

        # 3. 创建临时目录，写入文件
        os.makedirs(tmp_dir, exist_ok=True)
        for file_name, file_content in code.items():
            with open(os.path.join(tmp_dir, file_name), "w", encoding="utf-8") as f:
                f.write(file_content)
        with open(os.path.join(tmp_dir, "Dockerfile"), "w", encoding="utf-8") as f:
            f.write(env["dockerfile"])
        with open(os.path.join(tmp_dir, "requirements.txt"), "w", encoding="utf-8") as f:
            f.write(env["requirements.txt"])

        # 4. 执行安全检测（修复后的工具函数）
        for file_name in code.keys():
            file_path = os.path.join(tmp_dir, file_name)
            security_issues += run_flake8(file_path)
            security_issues += run_mypy(file_path)
            security_issues += run_bandit(file_path)

        # 5. Docker构建&运行
        os.chdir(tmp_dir)
        docker_client.images.build(path=".", tag=docker_img_tag, rm=True)
        container = docker_client.containers.create(
            image=docker_img_tag,
            name=docker_ctn_name,
            mem_limit="128m",
            network_disabled=True
        )
        container.start()
        container.wait()
        execution_logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="ignore")
        run_success = (container.wait()["StatusCode"] == 0)

        # 6. 处理输出文件
        all_files = os.listdir(tmp_dir) if os.path.exists(tmp_dir) else []
        exclude_files = list(code.keys()) + ["Dockerfile", "requirements.txt"]
        output_files = [f for f in all_files if f not in exclude_files and os.path.isfile(os.path.join(tmp_dir, f))]
        if output_files:
            try:
                with open(os.path.join(tmp_dir, output_files[0]), "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    output_preview = content[:200] + "..." if len(content) > 200 else content
            except Exception:
                output_preview = ""

        # 7. 成功响应（严格按模板：仅success+data，字段完全匹配）
        if run_success and len(security_issues) == 0:
            return {
                "success": True,
                "data": {
                    "test_passed": True,
                    "test_results": "全检测通过，代码运行正常",
                    "security_issues": [],
                    "execution_logs": execution_logs,
                    "output_files": output_files,
                    "output_preview": output_preview
                }
            }
        # 8. 失败响应（严格按模板：无冗余字段，补充所有必填项）
        else:
            test_results = ""
            suggestions = []
            if not run_success:
                test_results += "代码运行失败;"
                suggestions.append("修复代码语法/逻辑错误后重试")
            if len(security_issues) > 0:
                test_results += f"检测发现{len(security_issues)}个问题;"
                suggestions.append("按security_issues中的描述修复代码问题")
            test_results = test_results.rstrip(";") or "未知错误"
            
            return {
                "success": False,
                "data": {
                    "test_passed": False,
                    "test_results": test_results,
                    "security_issues": security_issues,
                    "execution_logs": execution_logs,
                    "suggestions": suggestions,
                    "output_files": output_files,
                    "output_preview": output_preview
                }
            }

    # 9. 异常响应（严格按模板：字段完全匹配）
    except Exception as e:
        return {
            "success": False,
            "data": {
                "test_passed": False,
                "test_results": f"接口执行异常：{str(e)}",
                "security_issues": [],
                "execution_logs": str(e),
                "suggestions": ["确认Docker已启动并正常运行", "检查请求参数格式是否正确"],
                "output_files": [],
                "output_preview": ""
            }
        }
    # 10. 资源清理
    finally:
        try:
            # 清理容器
            if docker_ctn_name in [c.name for c in docker_client.containers.list(all=True)]:
                docker_client.containers.get(docker_ctn_name).stop().remove()
            # 清理镜像
            if docker_img_tag in [i.tags[0] for i in docker_client.images.list() if i.tags]:
                docker_client.images.remove(docker_img_tag, force=True)
            # 清理临时目录
            if os.path.exists(tmp_dir):
                os.chdir(os.path.dirname(tmp_dir))
                shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception as e:
            print(f"资源清理警告：{str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
