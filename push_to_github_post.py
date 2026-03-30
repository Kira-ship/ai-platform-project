import requests
import json

def post_data_to_api(url: str, data: dict, headers: dict = None):
    """
    发送POST请求到指定接口
    :param url: 接口地址
    :param data: 请求参数（字典格式）
    :param headers: 请求头（可选）
    :return: 响应结果
    """
    # 默认请求头
    default_headers = {
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    # 合并自定义请求头
    final_headers = {**default_headers, **(headers or {})}
    
    try:
        # 发送POST请求
        response = requests.post(
            url=url,
            data=json.dumps(data, ensure_ascii=False),  # 中文不转码
            headers=final_headers,
            timeout=10
        )
        # 检查响应状态
        response.raise_for_status()
        print("✅ POST请求发送成功！")
        print(f"响应状态码：{response.status_code}")
        print(f"响应内容：{response.json()}")
        return response.json()
    
    except requests.exceptions.RequestException as e:
        print(f"❌ 请求失败：{str(e)}")
        return None

# 测试示例（可自行修改）
if __name__ == "__main__":
    # 测试接口（替换为你的实际接口地址）
    test_url = "http://localhost/chat/4UEmfEdNoeGlCdkG"
    # 测试数据
    test_data = {
        "username": "Kira-ship",
        "content": "测试POST提交",
        "timestamp": "2026-03-30"
    }
    # 执行请求
    post_data_to_api(test_url, test_data)
