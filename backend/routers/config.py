from fastapi import APIRouter, Form
import storage
import logging

router = APIRouter(prefix="/config", tags=["config"])

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
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        await client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=5,
            timeout=10,
            temperature=temperature
        )
        return {"status": "success", "message": "连接成功！"}
    except Exception as e:
        return {"status": "error", "message": f"连接失败: {str(e)}"}
