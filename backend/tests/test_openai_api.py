"""
OpenAI API 测试用例

测试通过 OpenAI 兼容方式调用本地模型服务。
"""
import requests
from typing import Any


def test_openai_chat_completion() -> None:
    """
    测试 OpenAI Chat Completion API 调用。
    
    向本地模型服务发送聊天请求，验证响应格式和内容。
    """
    # API 配置
    base_url: str = "http://127.0.0.1:8045/v1"
    endpoint: str = f"{base_url}/chat/completions"
    
    # 请求头
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        # 如果需要 API Key，取消下面的注释
        # "Authorization": "Bearer your-api-key"
    }
    
    # 请求体 - OpenAI 格式
    payload: dict[str, Any] = {
        "model": "claude-opus-4-5-thinking",  # 根据实际模型名称修改
        "messages": [
            {
                "role": "system",
                "content": "你是一个有帮助的助手。"
            },
            {
                "role": "user",
                "content": "你好，请简单介绍一下你自己。"
            }
        ],
        "temperature": 0.7,
        "max_tokens": 256,
        "stream": False
    }
    
    print("=" * 50)
    print("OpenAI API 测试")
    print("=" * 50)
    print(f"请求地址: {endpoint}")
    print(f"请求模型: {payload['model']}")
    print(f"用户消息: {payload['messages'][-1]['content']}")
    print("-" * 50)
    
    try:
        # 发送请求
        response: requests.Response = requests.post(
            url=endpoint,
            headers=headers,
            json=payload,
            timeout=60
        )
        
        # 检查响应状态
        print(f"响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            result: dict[str, Any] = response.json()
            
            # 提取回复内容
            if "choices" in result and len(result["choices"]) > 0:
                content: str = result["choices"][0]["message"]["content"]
                print(f"模型回复:\n{content}")
            else:
                print(f"完整响应: {result}")
                
            # 显示 token 使用情况（如果有）
            if "usage" in result:
                usage: dict[str, int] = result["usage"]
                print("-" * 50)
                print(f"Token 使用: 输入={usage.get('prompt_tokens', 'N/A')}, "
                      f"输出={usage.get('completion_tokens', 'N/A')}, "
                      f"总计={usage.get('total_tokens', 'N/A')}")
        else:
            print(f"请求失败: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("错误: 无法连接到服务，请确保服务已启动在 http://127.0.0.1:8045")
    except requests.exceptions.Timeout:
        print("错误: 请求超时")
    except Exception as e:
        print(f"错误: {e}")
    
    print("=" * 50)


def test_openai_models_list() -> None:
    """
    测试获取可用模型列表。
    """
    base_url: str = "http://127.0.0.1:8045/v1"
    endpoint: str = f"{base_url}/models"
    
    print("\n获取模型列表...")
    
    try:
        response: requests.Response = requests.get(endpoint, timeout=10)
        
        if response.status_code == 200:
            result: dict[str, Any] = response.json()
            print(f"可用模型: {result}")
        else:
            print(f"获取失败: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"错误: {e}")


if __name__ == "__main__":
    # 运行测试
    test_openai_chat_completion()
    test_openai_models_list()
