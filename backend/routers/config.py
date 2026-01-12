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
    temperature: float = Form(0.0)
):
    logger.info("-" * 30)
    logger.info(f"Testing connection to: {base_url}")
    logger.info(f"Model: {model_name}")
    logger.info(f"API Key: {api_key[:8]}******{api_key[-4:] if len(api_key) > 12 else ''}")
    
    try:
        from openai import AsyncOpenAI
        import os
        
        # 打印当前代理设置，帮助排查网络问题
        logger.info(f"Current HTTP_PROXY: {os.environ.get('HTTP_PROXY')}")
        logger.info(f"Current HTTPS_PROXY: {os.environ.get('HTTPS_PROXY')}")
        
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        
        logger.info("Sending chat completion request...")
        await client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=5,
            timeout=10,
            temperature=temperature
        )
        logger.info("Connection test successful!")
        return {"status": "success", "message": "连接成功！"}
    except Exception as e:
        logger.error(f"Connection failed: {str(e)}")
        logger.exception("Full traceback:")
        return {"status": "error", "message": f"连接失败: {str(e)}"}
