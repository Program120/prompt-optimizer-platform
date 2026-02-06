"""
AI 辅助功能 API 路由
提供 AI 生成代码等辅助功能
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from loguru import logger
from app.core.llm_factory import LLMFactory
from app.db import storage

router = APIRouter(prefix="/ai", tags=["ai"])


class GenerateInterfaceCodeRequest(BaseModel):
    """
    生成接口转换代码请求模型
    """
    sample_request: str  # 用户提供的示例请求体 JSON
    llm_config: Dict[str, Any] = Field(..., alias="model_config")  # LLM 配置


@router.post("/generate-interface-code")
async def generate_interface_code(request: GenerateInterfaceCodeRequest) -> Dict[str, Any]:
    """
    根据用户提供的示例请求体，AI 自动生成 Python 参数转换脚本

    :param request: 包含示例请求体和模型配置
    :return: 生成的 Python 代码
    """
    sample_request = request.sample_request.strip()
    llm_config = request.llm_config

    if not sample_request:
        raise HTTPException(status_code=400, detail="示例请求体不能为空")

    if not llm_config or not llm_config.get("api_key"):
        raise HTTPException(status_code=400, detail="请先配置优化模型的 API Key")

    # 构造提示词
    system_prompt = """你是一个 Python 代码生成专家。你的任务是根据用户提供的目标 API 请求体示例，生成一个 Python 参数转换脚本。

## 可用变量
脚本中可以使用以下预定义变量：
- `query`: 字符串，当前用户输入的问题
- `target`: 字符串，期望的意图/分类结果
- `prompt`: 字符串，系统提示词
- `history`: 列表，历史对话记录，格式为 [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
- `session_id`: 字符串，会话ID（已预生成的 UUID）

## 可用的 Python 模块
脚本中可以直接使用以下已导入的模块：
- `uuid`: 用于生成 UUID，如 `str(uuid.uuid4())`
- `time`: 用于获取时间戳，如 `int(time.time() * 1000)` 获取毫秒级时间戳
- `json`: 用于 JSON 处理

## 输出要求
1. 生成的代码必须定义一个名为 `params` 的字典变量，这个字典将作为 HTTP POST 请求的 JSON body
2. 根据示例请求体的结构，将可用变量映射到对应的字段
3. 代码应该简洁、直接，不需要函数定义，不需要 import 语句
4. 如果示例中有历史消息相关字段（如 historyList、history、messages 等），使用 `history` 变量
5. 如果示例中有系统提示词相关字段，使用 `prompt` 变量
6. 如果示例中有当前问题/查询相关字段（如 question、query、input 等），使用 `query` 变量
7. 如果示例中有需要动态生成的 UUID 字段（如 sessionId、requestId 等占位符 {{$string.uuid}}），使用 `str(uuid.uuid4())` 生成
8. 如果示例中有需要动态生成的时间戳字段，使用 `int(time.time() * 1000)` 生成毫秒级时间戳
9. 对于固定值字段（如 scene、version、pinType 等），保持原样
10. 只输出纯 Python 代码，不要包含任何解释、注释或 markdown 标记

## 示例1：基础消息格式
输入：
```json
{
  "messages": [{"role": "user", "content": "你好"}],
  "system": "你是助手"
}
```
输出：
params = {
    "messages": [{"role": "user", "content": query}],
    "system": prompt
}

## 示例2：包含动态 UUID 和时间戳
输入：
```json
{
  "sessionId": "{{$string.uuid}}",
  "requestId": "{{$string.uuid}}",
  "question": "当前问题",
  "historyList": [{"role": "user", "content": "历史", "timestamp": 1234567890}]
}
```
输出：
params = {
    "sessionId": str(uuid.uuid4()),
    "requestId": str(uuid.uuid4()),
    "question": query,
    "historyList": history
}

## 示例3：复杂业务场景
输入：
```json
{
  "query": "问题",
  "history": [],
  "scene": "common",
  "version": 0,
  "login": true
}
```
输出：
params = {
    "query": query,
    "history": history,
    "scene": "common",
    "version": 0,
    "login": True
}"""

    user_prompt = f"""请根据以下目标 API 的示例请求体，生成 Python 参数转换脚本：

```json
{sample_request}
```

注意：
1. 识别哪些字段需要用变量替换（query、history、prompt 等）
2. 识别哪些字段需要动态生成（UUID、时间戳等，通常有 {{{{$string.uuid}}}} 这样的占位符）
3. 其他固定值字段保持原样

请直接输出 Python 代码，不要包含任何解释、import 语句或 markdown 代码块标记。"""

    try:
        # 创建 LLM 客户端
        llm = LLMFactory.create_raw_async_client(llm_config)
        model_name = llm_config.get("model_name", "gpt-3.5-turbo")

        logger.info(f"AI 生成接口代码 - Model: {model_name}")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        response = await llm.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.3,  # 使用较低温度以获得更稳定的代码
            max_tokens=llm_config.get("max_tokens", 2000)
        )

        content = response.choices[0].message.content
        if not content:
            raise HTTPException(status_code=500, detail="模型返回内容为空")

        # 清理可能存在的 markdown 标记
        code = content.strip()
        if code.startswith("```python"):
            code = code[9:]
        elif code.startswith("```"):
            code = code[3:]
        if code.endswith("```"):
            code = code[:-3]
        code = code.strip()

        logger.info(f"AI 生成接口代码成功，代码长度: {len(code)}")

        return {
            "code": code,
            "success": True
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI 生成接口代码失败: {e}")
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")


class GenerateExtractPathsRequest(BaseModel):
    """
    生成提取代码请求模型
    """
    sample_response: str  # 用户提供的 API 响应示例 JSON
    project_id: str  # 项目 ID，用于获取优化模型配置
    extra_description: Optional[str] = None  # 用户额外描述


@router.post("/generate-extract-paths")
async def generate_extract_paths(request: GenerateExtractPathsRequest) -> Dict[str, Any]:
    """
    根据用户提供的 API 响应示例，AI 自动生成 Python 提取代码

    :param request: 包含 API 响应示例、项目 ID 和额外描述
    :return: 意图提取代码和回复内容提取代码
    """
    sample_response = request.sample_response.strip()
    project_id = request.project_id
    extra_description = request.extra_description or ""

    if not sample_response:
        raise HTTPException(status_code=400, detail="API 响应示例不能为空")

    # 获取项目的优化模型配置
    project = storage.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    llm_config = project.get("optimization_model_config", {})
    if not llm_config or not llm_config.get("api_key"):
        raise HTTPException(status_code=400, detail="请先在【项目配置】-【优化配置】中设置模型 API Key")

    # 构造提示词
    system_prompt = """你是一个 Python 代码生成专家。你的任务是根据用户提供的 API 响应 JSON 示例，生成两段 Python 提取代码：
1. 意图提取代码：从响应中提取用户意图/分类结果
2. 回复内容提取代码：从响应中提取 AI 回复内容

## 代码格式要求
- 代码必须以 `py:` 前缀开头，然后换行开始写代码
- 代码中可以使用以下预定义变量：
  - `data`: 解析后的 JSON 对象（字典）
  - `output`: 原始文本内容
  - `is_json`: 布尔值，指示内容是否为 JSON
- 代码必须将提取结果赋值给 `result` 变量
- 代码应该简洁易读，适当换行，不要把所有代码挤在一行
- 可以使用基本的 Python 内置函数：len, str, int, float, bool, list, dict, isinstance 等

## 输出格式
你必须严格按照以下 JSON 格式输出，不要包含任何其他内容：
```json
{
  "intent_code": "py:\\n...",
  "response_code": "py:\\n..."
}
```

## 示例1：简单嵌套结构
输入 JSON：
```json
{
  "code": 0,
  "data": {
    "intent": "查询余额",
    "response": "您的余额是100元"
  }
}
```
输出：
```json
{
  "intent_code": "py:\\nresult = data.get('data', {}).get('intent', '')",
  "response_code": "py:\\nresult = data.get('data', {}).get('response', '')"
}
```

## 示例2：复杂嵌套结构
输入 JSON：
```json
{
  "result": {
    "intent_result": {
      "intent": "订单查询",
      "confidence": 0.95
    },
    "lastResponse": "您的订单已发货"
  }
}
```
输出：
```json
{
  "intent_code": "py:\\ninner = data.get('result', {}).get('intent_result', {})\\nresult = inner.get('intent', '')",
  "response_code": "py:\\nresult = data.get('result', {}).get('lastResponse', '')"
}
```

## 示例3：需要条件判断
输入 JSON：
```json
{
  "intent_type": "single",
  "intent": "查询余额",
  "multi_intents": ["查询余额", "转账"],
  "answer": "您的余额是100元"
}
```
用户描述：如果 intent_type 是 single 取 intent，否则取 multi_intents 的第一个
输出：
```json
{
  "intent_code": "py:\\nif data.get('intent_type') == 'single':\\n    result = data.get('intent', '')\\nelse:\\n    intents = data.get('multi_intents', [])\\n    result = intents[0] if intents else ''",
  "response_code": "py:\\nresult = data.get('answer', '')"
}
```

## 常见的意图字段名
intent, classification, category, type, action, skill, agent, agent_id, current_agent_id, intent_name, intent_type, intent_result

## 常见的回复内容字段名
response, answer, reply, content, message, text, output, result, lastResponse, data.response"""

    user_prompt = f"""请分析以下 API 响应 JSON，生成意图提取代码和回复内容提取代码：

```json
{sample_response}
```"""

    if extra_description:
        user_prompt += f"""

用户额外说明：
{extra_description}"""

    user_prompt += """

请严格按照 JSON 格式输出，只输出 JSON，不要包含任何解释或 markdown 标记。"""

    try:
        # 创建 LLM 客户端
        llm = LLMFactory.create_raw_async_client(llm_config)
        model_name = llm_config.get("model_name", "gpt-3.5-turbo")

        logger.info(f"AI 生成提取代码 - Model: {model_name}")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        response = await llm.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.2,  # 使用较低温度以获得更稳定的结果
            max_tokens=1000
        )

        content = response.choices[0].message.content
        if not content:
            raise HTTPException(status_code=500, detail="模型返回内容为空")

        # 清理可能存在的 markdown 标记
        result_text = content.strip()
        if result_text.startswith("```json"):
            result_text = result_text[7:]
        elif result_text.startswith("```"):
            result_text = result_text[3:]
        if result_text.endswith("```"):
            result_text = result_text[:-3]
        result_text = result_text.strip()

        # 解析 JSON
        import json
        try:
            result = json.loads(result_text)
        except json.JSONDecodeError as e:
            logger.error(f"AI 返回的 JSON 解析失败: {result_text}")
            raise HTTPException(status_code=500, detail=f"AI 返回格式错误: {str(e)}")

        intent_code = result.get("intent_code", "")
        response_code = result.get("response_code", "")

        if not intent_code and not response_code:
            raise HTTPException(status_code=500, detail="未能生成有效的提取代码")

        logger.info(f"AI 生成提取代码成功 - intent: {intent_code[:50]}..., response: {response_code[:50]}...")

        return {
            "intent_code": intent_code,
            "response_code": response_code,
            "success": True
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI 生成提取代码失败: {e}")
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")
