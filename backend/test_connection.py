import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

try:
    from openai import OpenAI
except ImportError:
    print("Please install openai: pip install openai")
    exit(1)

# 从环境变量获取配置
API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")
MODEL = os.getenv("MODEL_NAME", "gpt-3.5-turbo")

# 设置代理 (如果环境变量中存在)
if os.getenv("HTTP_PROXY"):
    os.environ["HTTP_PROXY"] = os.getenv("HTTP_PROXY")
if os.getenv("HTTPS_PROXY"):
    os.environ["HTTPS_PROXY"] = os.getenv("HTTPS_PROXY")

print("-" * 50)
print(f"开始测试模型连接性...")
print(f"Base URL: {BASE_URL}")
print(f"Model:    {MODEL}")
print(f"API Key:  {API_KEY[:8]}******")
print(f"Proxy:    {os.environ.get('HTTP_PROXY')}")
print("-" * 50)

def test_connection():
    try:
    # 构造临时 model_config
        model_config = {
            "api_key": API_KEY,
            "base_url": BASE_URL,
            "timeout": 30.0,
            # max_retries not supported in config dict yet, but standard OpenAI client accepts it.
            # LLMFactory params logic might filter it out if we passed it there.
            # But wait, LLMFactory only extracts api_key, base_url, default_headers.
            # And passes them to OpenAI constructor as **params.
            # So if we want to pass timeout/max_retries, we might need to modify Factory or just rely on default.
            # However, looking at LLMFactory implementation:
            # params = LLMFactory._prepare_params(model_config)
            # return OpenAI(**params)
            # It only prepares api_key, base_url, default_headers.
            # It ignores other keys in model_config for the OpenAI constructor!
            # So we can't pass timeout via model_config if Factory doesn't support it.
            # Let's inspect LLMFactory again.
            
            # Re-read LLMFactory code from memory or file.
            # Assuming LLMFactory only prepares the 3 keys.
            # If so, passing timeout in model_config won't work for the client init timeout argument.
            # BUT verify if OpenAI client takes timeout in init. Yes it does.
            # We should probably update Factory to pass through other kwargs or at least timeout/max_retries.
            # For now, let's just stick to what Factory provides to be consistent.
        }
        
        from llm_factory import LLMFactory
        # Note: We need to make sure LLMFactory is importable. 
        # Since this script is in backend root, it should be fine.
        
        client = LLMFactory.create_client(model_config)
        # Manually set timeout/retries if needed since factory strips them? 
        # Actually factory returns the client instance, we can set them if public props, 
        # but OpenAI client props are usually set at init.
        client.timeout = 30.0
        client.max_retries = 0
        
        print("发送请求中...")
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello! Reply with 'Connection Successful' if you receive this."}
            ],
            max_tokens=20
        )
        
        print("\n✅ 连接成功!")
        print(f"模型响应: {response.choices[0].message.content}")
        
    except Exception as e:
        print("\n❌ 连接失败!")
        print(f"错误类型: {type(e).__name__}")
        print(f"错误详情: {str(e)}")
        
        # 常见问题提示
        print("\n排查建议:")
        if "ConnectError" in str(e) or "Connection error" in str(e):
            print("1. 检查 Base URL 是否正确 (注意末尾的 /v1)")
            print("2. 检查网络是否正常，是否需要代理")
            print("3. 如果使用 VPN/代理，请尝试设置 HTTP_PROXY 和 HTTPS_PROXY 环境变量")
        elif "AuthenticationError" in str(e) or "401" in str(e):
            print("1. 检查 API Key 是否正确")
            print("2. 检查 Key 是否过期或欠费")
        elif "NotFoundError" in str(e) or "404" in str(e):
            print("1. 检查 Model 名称是否正确")
            print("2. 检查 Base URL 是否正确")

if __name__ == "__main__":
    test_connection()
