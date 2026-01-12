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
        client = OpenAI(
            api_key=API_KEY, 
            base_url=BASE_URL,
            timeout=30.0,
            max_retries=0
        )
        
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
