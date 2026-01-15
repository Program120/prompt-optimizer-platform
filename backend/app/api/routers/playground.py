"""
通用 Playground API 路由
提供模型即时测试功能
"""
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging
import time
import asyncio
from app.core.llm_factory import LLMFactory
from loguru import logger as loguru_logger

router = APIRouter(prefix="/playground", tags=["playground"])
logger = logging.getLogger(__name__)

class TestPromptRequest(BaseModel):
    prompt: str
    query: str
    llm_config: Dict[str, Any]

@router.post("/test")
async def test_prompt_output(request: TestPromptRequest):
    """
    测试提示词输出
    :param request: 请求参数
    :return: 模型输出和耗时
    """
    prompt = request.prompt
    query = request.query
    # 兼容前端可能传过来的 model_config (如果前端没更新)
    # 但 Pydantic verification 会在 request validation 阶段就报错如果名字不对
    # 所以前端必须更新
    model_config = request.llm_config

    if not model_config or not model_config.get("api_key"):
        raise HTTPException(status_code=400, detail="未配置模型参数(API Key)")

    start_time = time.time()
    try:
        # 使用 LLMFactory 创建客户端
        # 注意: 这里我们假设是简单的一问一答，Prompt作为System Message或者放在前面
        
        # 构造消息
        messages = []
        if prompt:
            messages.append({"role": "system", "content": prompt})
        messages.append({"role": "user", "content": query})

        # 异步调用模型
        client = LLMFactory.create_async_client(model_config)
        
        model_name = model_config.get("model_name", "gpt-3.5-turbo")
        
        # 准备参数
        params = {
            "model": model_name,
            "messages": messages,
            "temperature": model_config.get("temperature", 0.0),
        }
        
        if model_config.get("max_tokens"):
            params["max_tokens"] = int(model_config.get("max_tokens"))
            
        # 处理 extra_body (例如 Ollama 可能需要的 chat_template_kwargs 等)
        # 正确方式: 作为 extra_body 参数传递，而不是合并到顶层参数
        if model_config.get("extra_body"):
            params["extra_body"] = model_config.get("extra_body")

        loguru_logger.info(f"Playground Test - Model: {model_name}, Prompt Len: {len(prompt)}, Query Len: {len(query)}")
        
        response = await client.chat.completions.create(**params)
        
        end_time = time.time()
        latency_ms = (end_time - start_time) * 1000
        
        content = response.choices[0].message.content
        
        return {
            "output": content,
            "latency_ms": round(latency_ms, 2),
            "model_used": model_name
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        loguru_logger.error(f"Playground Test Failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"模型调用失败: {str(e)}")
