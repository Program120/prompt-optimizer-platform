"""
通用 Playground API 路由
提供模型即时测试功能
"""
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Optional, Dict, Any
import time
import asyncio
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
    :return: 包含模型输出结果、耗时及使用的模型名称
    """
    prompt = request.prompt
    query = request.query
    # 兼容前端可能传过来的 model_config (如果前端没更新)
    # 但 Pydantic verification 会在 request validation 阶段就报错如果名字不对
    # 所以前端必须更新
    model_config = request.llm_config

    # 校验逻辑优化：
    # 如果是 interface 模式，api_key 可能为空
    validation_mode = model_config.get("validation_mode", "llm")
    if validation_mode != "interface" and (not model_config or not model_config.get("api_key")):
         raise HTTPException(status_code=400, detail="未配置模型参数(API Key)")

    start_time = time.time()
    try:
        if validation_mode == "interface":
            # 接口模式：调用 Verifier._call_interface
            #由于 Playground 没有 target，传空字符串
            from app.engine.verifier import Verifier
            # Verifier._call_interface 是静态方法
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
            # LLM 模式
            # 使用 LLMFactory 创建客户端
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
                
            # 处理 extra_body
            if model_config.get("extra_body"):
                params["extra_body"] = model_config.get("extra_body")

            logger.info(f"Playground Test - Model: {model_name}, Prompt Len: {len(prompt)}, Query Len: {len(query)}")
            
            response = await client.chat.completions.create(**params)
            output = response.choices[0].message.content
        
        end_time = time.time()
        latency_ms = (end_time - start_time) * 1000
        
        return {
            "output": output,
            "latency_ms": round(latency_ms, 2),
            "model_used": model_name
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error(f"Playground Test Failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"调用失败: {str(e)}")
