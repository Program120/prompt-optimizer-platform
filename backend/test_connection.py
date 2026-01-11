import os
try:
    from openai import OpenAI
except ImportError:
    print("Please install openai: pip install openai")
    exit(1)

# 请在此处替换为您的真实 API Key
API_KEY = "sk-356ce0e3bcf542ff9b3392346b555d46"
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL = "qwen-flash"

# 设置代理 (根据用户提供的信息)
os.environ["HTTP_PROXY"] = "http://192.168.91.1:7890"
os.environ["HTTPS_PROXY"] = "http://192.168.91.1:7890"

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
