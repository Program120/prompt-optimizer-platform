from fastapi import APIRouter, Form
import storage
import logging

router = APIRouter(prefix="/config", tags=["config"])
logger = logging.getLogger(__name__)

@router.get("")
async def get_config():
    return storage.get_model_config()

@router.post("")
async def save_config(
    base_url: str = Form(...), 
    api_key: str = Form(...),
    max_tokens: int = Form(2000),
    timeout: int = Form(60),
    model_name: str = Form("gpt-3.5-turbo"),
    concurrency: int = Form(5),
    temperature: float = Form(0.0)
):
    from starlette.concurrency import run_in_threadpool
    await run_in_threadpool(storage.save_model_config, {
        "base_url": base_url, 
        "api_key": api_key,
        "max_tokens": max_tokens,
        "timeout": timeout,
        "model_name": model_name,
        "concurrency": concurrency,
        "temperature": temperature
    })
    return {"status": "success"}

@router.post("/test")
async def test_config(
    base_url: str = Form(...), 
    api_key: str = Form(...),
    model_name: str = Form("gpt-3.5-turbo"),
    temperature: float = Form(0.0),
    validation_mode: str = Form("llm"),
    interface_code: str = Form(""),
    extra_body: str = Form(None),
    default_headers: str = Form(None)
):
    logger.info("-" * 30)
    logger.info(f"Testing connection to: {base_url} | Mode: {validation_mode}")
    
    try:
        if validation_mode == "interface":
            # 接口验证模式测试
            import requests
            import json
            
            if not base_url:
                raise ValueError("Interface URL is required")
                
            # 准备 dummy 执行环境
            local_scope = {
                "query": "Hello", 
                "target": "World",
                "prompt": "You are a helpful assistant",
                "params": None
            }
            
            # 执行转换脚本
            try:
                exec(interface_code, {"__builtins__": None}, local_scope)
                params = local_scope.get("params")
            except Exception as e:
                raise ValueError(f"Python script syntax error or execution failed: {e}")
                
            if isinstance(params, dict):
                # 发起请求
                headers = {"Content-Type": "application/json"}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                    headers["api-key"] = api_key 
                
                logger.info(f"Sending interface request with params: {json.dumps(params, ensure_ascii=False)}")
                resp = requests.post(base_url, json=params, headers=headers, timeout=10)
                
                #记录响应以便用户调试
                logger.info(f"Interface response: {resp.status_code} - {resp.text[:200]}...")
                
                resp.raise_for_status()
                return {"status": "success", "message": f"接口调用成功！Status: {resp.status_code}"}
            else:
                 raise ValueError("Script must assign a valid dict to 'params' variable")
            
        else:
            # LLM 模式测试
            from openai import AsyncOpenAI
            import os
            import json as json_lib
            
            logger.info(f"Model: {model_name}")
            logger.info(f"API Key: {api_key[:8]}******{api_key[-4:] if len(api_key) > 12 else ''}")
            
            # 打印当前代理设置，帮助排查网络问题
            logger.info(f"Current HTTP_PROXY: {os.environ.get('HTTP_PROXY')}")
            logger.info(f"Current HTTPS_PROXY: {os.environ.get('HTTPS_PROXY')}")
            
            # 解析 extra_body 和 default_headers
            extra_body_dict = None
            if extra_body:
                try:
                    extra_body_dict = json_lib.loads(extra_body)
                    logger.info(f"Extra Body: {extra_body_dict}")
                except Exception as e:
                    logger.warning(f"Failed to parse extra_body: {e}")

            default_headers_dict = {"Content-Type": "application/json; charset=utf-8"}
            if default_headers:
                try:
                    user_headers = json_lib.loads(default_headers)
                    if isinstance(user_headers, dict):
                        default_headers_dict.update(user_headers)
                    logger.info(f"Default Headers: {default_headers_dict}")
                except Exception as e:
                    logger.warning(f"Failed to parse default_headers: {e}")
            
            client = AsyncOpenAI(
                api_key=api_key, 
                base_url=base_url,
                default_headers=default_headers_dict
            )
            
            logger.info("Sending chat completion request...")
            await client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5,
                timeout=10,
                temperature=temperature,
                extra_body=extra_body_dict
            )
            logger.info("Connection test successful!")
            return {"status": "success", "message": "连接成功！"}
            
    except Exception as e:
        logger.error(f"Connection failed: {str(e)}")
        logger.exception("Full traceback:")
        return {"status": "error", "message": f"连接失败: {str(e)}"}
