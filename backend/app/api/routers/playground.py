"""
通用 Playground API 路由
提供模型即时测试功能
"""
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Optional, Dict, Any
import time
import asyncio
import uuid
from app.core.llm_factory import LLMFactory
from loguru import logger

router = APIRouter(prefix="/playground", tags=["playground"])


class TestPromptRequest(BaseModel):
    """
    提示词测试请求模型
    """
    prompt: str
    query: str
    llm_config: Dict[str, Any]


@router.post("/test")
async def test_prompt_output(request: TestPromptRequest) -> Dict[str, Any]:
    """
    测试提示词输出
    
    :param request: 测试请求参数，包含提示词、查询输入和模型配置
    :return: 包含模型输出结果、耗时、使用的模型名称及请求ID
    """
    prompt = request.prompt
    query = request.query
    model_config = request.llm_config

    # 校验逻辑优化：
    # 如果是 interface 模式，api_key 可能为空
    validation_mode = model_config.get("validation_mode", "llm")
    if validation_mode != "interface" and (not model_config or not model_config.get("api_key")):
         raise HTTPException(status_code=400, detail="未配置模型参数(API Key)")

    # 生成请求 ID
    request_id: str = str(uuid.uuid4())
    
    start_time = time.time()
    try:
        if validation_mode == "interface":
            # 接口模式：调用 Verifier._call_interface
            # 由于 Playground 没有 target，传空字符串
            from app.engine.helpers.verifier import Verifier
            output = Verifier._call_interface(
                query=query, 
                target="", 
                prompt=prompt, 
                config=model_config
            )
            # 尝试去除 markdown (保持与 Verifier 一致)
            output = Verifier._clean_markdown(output)
            model_name = "Interface API"
            
        else:
            # LLM 模式：使用 Verifier._call_llm（支持 chatrhino 等自动切换到 raw HTTP）
            from app.engine.helpers.verifier import Verifier
            
            model_name = model_config.get("model_name", "gpt-3.5-turbo")
            
            # 将 request_id 注入到配置中，以便 _call_llm_raw 使用
            config_with_request_id = {**model_config, "_request_id": request_id}
            
            logger.info(f"Playground Test - Model: {model_name}, Prompt Len: {len(prompt)}, Query Len: {len(query)}, RequestId: {request_id}")
            
            # 使用线程池运行同步方法
            from starlette.concurrency import run_in_threadpool
            output = await run_in_threadpool(
                Verifier._call_llm,
                query,
                prompt,
                config_with_request_id,
                None
            )
        
        end_time = time.time()
        latency_ms = (end_time - start_time) * 1000
        
        return {
            "output": output,
            "latency_ms": round(latency_ms, 2),
            "model_used": model_name,
            "request_id": request_id
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error(f"Playground Test Failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"调用失败: {str(e)}")
