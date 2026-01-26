"""
通用 Playground API 路由
提供模型即时测试功能
"""
from fastapi import APIRouter, HTTPException, Body, Query
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import time
import asyncio
import uuid
import json
from datetime import datetime
from sqlmodel import select, desc
from app.core.llm_factory import LLMFactory
from app.db.database import get_db_session
from app.models import PlaygroundHistory
from loguru import logger

router = APIRouter(prefix="/playground", tags=["playground"])


class HistoryMessage(BaseModel):
    """
    历史消息模型
    支持 role 和 content 字段，其他字段可选（如 timestamp、sessionId）
    """
    role: str
    content: str


class TestPromptRequest(BaseModel):
    """
    提示词测试请求模型
    """
    prompt: str
    query: str
    llm_config: Dict[str, Any]
    # 可选的历史消息列表（用于多轮对话测试）
    history_messages: Optional[List[HistoryMessage]] = None


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
    # 提取历史消息（转换为字典列表）
    history_messages: Optional[List[Dict[str, str]]] = None
    if request.history_messages:
        history_messages = [{"role": m.role, "content": m.content} for m in request.history_messages]

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
            
            history_count: int = len(history_messages) if history_messages else 0
            logger.info(f"Playground Test - Model: {model_name}, Prompt Len: {len(prompt)}, Query Len: {len(query)}, History Count: {history_count}, RequestId: {request_id}")
            
            # 使用线程池运行同步方法
            from starlette.concurrency import run_in_threadpool
            output = await run_in_threadpool(
                Verifier._call_llm,
                query,
                prompt,
                config_with_request_id,
                None,
                history_messages
            )
        
        end_time = time.time()
        latency_ms = (end_time - start_time) * 1000
        
        
        # 保存历史记录
        try:
            # 修正: 如果 query 为空但有历史消息，尝试从历史消息最后一条获取内容作为 query 记录
            # 这样在历史列表中能看到实际问的问题
            save_query = query
            if not save_query and history_messages:
                last_msg = history_messages[-1]
                if last_msg.get("role") == "user":
                    save_query = last_msg.get("content", "")

            with get_db_session() as session:
                history_record = PlaygroundHistory(
                    prompt=prompt,
                    query=save_query,
                    history_messages=json.dumps(history_messages) if history_messages else "[]",
                    model_config_data=json.dumps(model_config) if model_config else "{}",
                    output=output,
                    latency_ms=round(latency_ms, 2)
                )
                session.add(history_record)
                session.commit()
        except Exception as e:
            logger.error(f"Failed to save playground history: {e}")

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


@router.get("/history")
async def get_playground_history(limit: int = 50):
    """
    获取最近的测试记录（列表模式，不包含Prompt等大字段）
    """
    with get_db_session() as session:
        # 修正：使用 defer 在 session 关闭后会导致 lazy load 失败 (DetachedInstanceError)
        # 改为显式查询需要的字段
        statement = (
            select(
                PlaygroundHistory.id,
                PlaygroundHistory.query,
                PlaygroundHistory.output,
                PlaygroundHistory.created_at,
                PlaygroundHistory.latency_ms,
                PlaygroundHistory.history_messages 
            )
            .order_by(PlaygroundHistory.created_at.desc())
            .limit(limit)
        )
        results = session.exec(statement).all()
        
        # 转换为字典列表返回
        history_list = []
        for row in results:
            history_list.append({
                "id": row.id,
                "query": row.query,
                "output": row.output,
                "created_at": row.created_at,
                "latency_ms": row.latency_ms,
                "history_messages": row.history_messages
            })
            
        return history_list

@router.get("/history/{record_id}")
async def get_history_detail(record_id: int):
    """
    获取单条历史记录详情（包含所有字段）
    """
    with get_db_session() as session:
        record = session.get(PlaygroundHistory, record_id)
        if not record:
            raise HTTPException(status_code=404, detail="记录不存在")
        return record


@router.delete("/history/{history_id}")
async def delete_playground_history(history_id: int):
    """
    删除单条历史记录
    """
    with get_db_session() as session:
        record = session.get(PlaygroundHistory, history_id)
        if not record:
            raise HTTPException(status_code=404, detail="History not found")
        session.delete(record)
        session.commit()
        return {"success": True}
        
@router.delete("/history")
async def clear_playground_history():
    """
    清空所有历史记录
    """
    with get_db_session() as session:
        statement = select(PlaygroundHistory)
        results = session.exec(statement).all()
        for record in results:
            session.delete(record)
        session.commit()
        return {"success": True}


class FixJsonRequest(BaseModel):
    text: str
    llm_config: Optional[Dict[str, Any]] = None

@router.post("/fix_json")
async def fix_json(request: FixJsonRequest):
    """
    AI 辅助修复 JSON 格式
    """
    if not request.text or not request.text.strip():
        return {"fixed_text": ""}

    try:
        # 构造极其严格的格式化提示词，防止模型"回答"而非"格式化"
        system_instruction = (
            "# 任务：JSON 格式转换器（严禁修改内容）\n\n"
            "你的唯一任务是将用户提供的文本原封不动地包装成 JSON 数组格式。\n\n"
            "## 绝对禁止\n"
            "- 禁止修改、改写、翻译、补充、回应用户的任何文字内容\n"
            "- 禁止添加问候语、回复语或任何模型生成的内容\n"
            "- 禁止输出任何 Markdown 代码块标记（如 ```json）\n\n"
            "## 必须遵守\n"
            "- 将原始文本内容逐字放入 'content' 字段\n"
            "- 每条消息默认 role 为 'user'，除非原文明确标注了角色\n"
            "- 只输出一个纯净的 JSON 数组字符串\n\n"
            "## 示例\n"
            "输入: 你好啊\n"
            "输出: [{\"role\": \"user\", \"content\": \"你好啊\"}]\n\n"
            "输入: 用户：查余额\\n助手：您的余额是100元\n"
            '输出: [{"role": "user", "content": "查余额"}, {"role": "assistant", "content": "您的余额是100元"}]'
        )

        llm = LLMFactory.create_raw_async_client(request.llm_config)
        
        # 策略调整：将 System Prompt 并入 User Prompt，以防止某些模型忽略 System Role
        final_user_content = f"{system_instruction}\n\n## 待处理文本\n{request.text}"
        
        messages = [
            {"role": "user", "content": final_user_content}
        ]
        
        # 调用大模型
        # 获取 model_name
        model_name = request.llm_config.get("model_name", "gpt-3.5-turbo") if request.llm_config else "gpt-3.5-turbo"
        response = await llm.chat.completions.create(
            model=model_name,
            messages=messages
        )
        
        content = response.choices[0].message.content
        if not content:
            raise HTTPException(status_code=500, detail="模型返回内容为空")
        
        content = content.strip()
        
        # 清理可能存在的 markdown 标记
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
             content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
            
        return {"fixed_text": content.strip()}
        
    except Exception as e:
        logger.error(f"Fix JSON failed: {e}")
        # 如果失败，原样返回或抛出错误，这里选择抛出便于前端提示
        raise HTTPException(status_code=500, detail=f"修复失败: {str(e)}")
