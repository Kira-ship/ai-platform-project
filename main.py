from fastapi import FastAPI, HTTPException
import os
import uuid
import shutil
import docker
import subprocess
import json
from typing import Dict, List, Any, Optional

app = FastAPI(
    title="运行验证接口（MCP协议适配版）",
    version="1.0",
    description="对接MCP协议，支持flake8/mypy/bandit全检测。"
)
docker_client = docker.from_env()

def mcp_protocol_adapter(request_data: Dict) -> Dict:
    if "content" in request_data and "payload" in request_data.get("content", {}):
        mcp_payload = request_data["content"]["payload"]
        if "code" in mcp_payload and "env" in mcp_payload:
            return mcp_payload
        else:
            raise HTTPException(400, "MCP协议请求错误：payload中缺少code/env核心字段")
    elif "code" in request_data and "env" in request_data:
        return request_data
    else:
        raise HTTPException(400, "请求格式错误：缺少code/env字段")

def run_flake8(file_path: str) -> List[Dict[str, Any]]:
    issues = []
    try:
        result = subprocess.run(
            ["flake8", file_path, "--format", "json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        if result.stdout:
            output = result.stdout.decode("utf-8", errors="ignore")
            for item in json.loads(output):
                issues.append({
                    "type": "代码风格",
                    "description": f"flake8: {item['text']} (规则{item['code']})",
                    "line": item["line_number"]
                })
    except Exception as e:
        issues.append({"type": "工具异常", "description": f"flake8执行失败：{str(e)}", "line": 0})
    return issues

def run_mypy(file_path: str) -> List[Dict[str, Any]]:
    issues = []
    try:
        result = subprocess.run(
            ["mypy", file_path, "--no-error-summary", "--json-report", "-"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        if result.stdout:
            output = result.stdout.decode("utf-8", errors="ignore")
            mypy_data = json.loads(output)
            for issue in mypy_data.get("issues", []):
                issues.append({
                    "type": "类型注解",
                    "description": f"mypy: {issue['message']} (错误码{issue['code']})",
                    "line": issue["line"]
                })
    except Exception as e:
        issues.append({"type": "工具异常", "description": f"mypy执行失败：{str(e)}", "line": 0})
    return issues

def run_bandit(file_path: str) -> List[Dict[str, Any]]:
    issues = []
    try:
        result = subprocess.run(
            ["bandit", "-q", "-f", "json", file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        if result.stdout:
            output = result.stdout.decode("utf-8", errors="ignore")
            bandit_data = json.loads(output)
            for issue in bandit_data.get("results", []):
                issues.append({
                    "type": issue.get("issue_severity", "高危"),
                    "description": f"bandit: {issue['issue_text']} (检测项{issue['test_id']})",
                    "line": issue["line_number"]
                })
    except Exception as e:
        issues.append({"type": "工具异常", "description": f"bandit执行失败：{str(e)}", "line": 0})
    return issues

@app.post("/verify")
def code_verify(request: Dict):
    tmp_id = uuid.uuid4().hex[:8]
    tmp_dir = os.path.join(os.getcwd(), f"verify_temp_{tmp_id}")
    docker_img_tag = f"verify_img_{tmp_id}"
    docker_ctn_name = f"verify_ctn_{tmp_id}"

    execution_logs = ""
    security_issues = []
    output_files: List[str] = []
    output_preview = ""

    try:
        req_data = mcp_protocol_adapter(request)
        code = req_data["code"]
        env = req_data["env"]

        if not isinstance(code, dict) or len(code) == 0:
            raise HTTPException(400, "code字段错误")
        if not isinstance(env, dict) or "dockerfile" not in env or "requirements.txt" not in env:
            raise HTTPException(400, "env字段错误")

        os.makedirs(tmp_dir, exist_ok=True)
        for file_name, file_content in code.items():
            with open(os.path.join(tmp_dir, file_name), "w", encoding="utf-8") as f:
                f.write(file_content)
        with open(os.path.join(tmp_dir, "Dockerfile"), "w", encoding="utf-8") as f:
            f.write(env["dockerfile"])
        with open(os.path.join(tmp_dir, "requirements.txt"), "w", encoding="utf-8") as f:
            f.write(env["requirements.txt"])

        for file_name in code.keys():
            file_path = os.path.join(tmp_dir, file_name)
            security_issues += run_flake8(file_path)
            security_issues += run_mypy(file_path)
            security_issues += run_bandit(file_path)

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

        all_files = os.listdir(tmp_dir)
        exclude_files = list(code.keys()) + ["Dockerfile", "requirements.txt"]
        output_files = [f for f in all_files if f not in exclude_files and os.path.isfile(f)]
        if output_files:
            with open(output_files[0], "r", encoding="utf-8", errors="ignore") as f:
                output_preview = f.read()[:200] + "..." if len(f.read()) > 200 else f.read()

        if run_success and len(security_issues) == 0:
            return {
                "success": True,
                "data": {"test_passed": True, "test_results": "全检测通过", "security_issues": [], "execution_logs": execution_logs, "output_files": output_files, "output_preview": output_preview},
                "mcp_status": "success", "mcp_msg": "MCP协议测试通过"
            }
        else:
            test_results = ""
            suggestions = []
            if not run_success:
                test_results += "代码运行失败；"
                suggestions.append("修复代码语法/逻辑错误")
            if len(security_issues) > 0:
                test_results += f"检测发现{len(security_issues)}个问题；"
                suggestions.append("按security_issues描述修复代码")
            test_results = test_results.rstrip("；")
            return {
                "success": False,
                "data": {"test_passed": False, "test_results": test_results, "security_issues": security_issues, "execution_logs": execution_logs, "suggestions": suggestions},
                "mcp_status": "failed", "mcp_error_detail": test_results
            }
    except Exception as e:
        return {
            "success": False,
            "data": {"test_passed": False, "test_results": f"异常：{str(e)}", "security_issues": [], "execution_logs": str(e), "suggestions": ["确认Docker已启动"]},
            "mcp_status": "error", "mcp_error_detail": str(e)
        }
    finally:
        try:
            if docker_ctn_name in [c.name for c in docker_client.containers.list(all=True)]:
                docker_client.containers.get(docker_ctn_name).stop().remove()
            if docker_img_tag in [i.tags[0] for i in docker_client.images.list() if i.tags]:
                docker_client.images.remove(docker_img_tag, force=True)
            if os.path.exists(tmp_dir):
                os.chdir(os.path.dirname(tmp_dir))
                shutil.rmtree(tmp_dir)
        except Exception as e:
            print(f"资源清理警告：{str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
