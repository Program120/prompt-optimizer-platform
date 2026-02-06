"""
验证器模块 - 封装单条数据的验证逻辑

统一 TaskService (任务执行) 和 PromptEvaluator (优化评估) 的验证行为
"""
from loguru import logger
import json
import re
from typing import Dict, Any, Optional
from app.core.llm_factory import LLMFactory

class Verifier:
    """
    通用验证器
    """
    
    @staticmethod
    def verify_single(
        index: int,
        query: str,
        target: str,
        prompt: str,
        model_config: Dict[str, Any],
        extract_field: Optional[str] = None,
        reason_col_value: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        验证单条数据

        :param index: 数据行索引
        :param query: 用户输入
        :param target: 预期输出
        :param prompt: 提示词
        :param model_config: 模型/验证配置
        :param extract_field: 提取字段 (可选)
        :param reason_col_value: 原因列的值 (可选)
        :return: 验证结果字典，包含 latency_ms 和 request_id
        """
        import time
        import uuid
        from .extractor import ResultExtractor

        # 生成请求 ID
        request_id: str = str(uuid.uuid4())
        start_time: float = time.time()

        try:
            mode = model_config.get("validation_mode", "llm")
            output = ""
            request_params = None
            extracted_intent_value = None

            # 将 request_id 注入到配置中
            config_with_request_id = {**model_config, "_request_id": request_id}

            if mode == "interface":
                result = Verifier._call_interface(query, target, prompt, config_with_request_id)
                # _call_interface 可能返回 tuple (output, request_params) 或 str
                if isinstance(result, tuple):
                    output, request_params = result
                else:
                    output = result
            else:
                output = Verifier._call_llm(query, prompt, config_with_request_id)

            # 自动去除 markdown 代码块标记
            output = Verifier._clean_markdown(output)

            # 提取意图值
            if extract_field:
                extracted_intent = ResultExtractor.extract(output, extract_field)
                if extracted_intent is not None:
                    if isinstance(extracted_intent, bool):
                        extracted_intent_value = str(extracted_intent)
                    else:
                        extracted_intent_value = str(extracted_intent).strip()

            is_correct = Verifier.check_match(output, target, extract_field)

            # 计算耗时
            latency_ms: float = round((time.time() - start_time) * 1000, 2)

            result = {
                "index": index,
                "query": query,
                "target": target,
                "reason": reason_col_value or "",
                "output": output,
                "is_correct": is_correct,
                "latency_ms": latency_ms,
                "request_id": request_id
            }

            # 如果有完整入参，添加到结果中
            if request_params:
                result["request_params"] = request_params

            # 如果有提取的意图值，添加到结果中
            if extracted_intent_value is not None:
                result["extracted_intent"] = extracted_intent_value

            return result

        except Exception as e:
            logger.error(f"[Verifier] Error index={index}: {str(e)}")
            # 计算耗时（即使失败也记录）
            latency_ms: float = round((time.time() - start_time) * 1000, 2)
            return {
                "index": index,
                "query": query,
                "target": target,
                "reason": reason_col_value or "",
                "output": f"ERROR: {str(e)}",
                "is_correct": False,
                "latency_ms": latency_ms,
                "request_id": request_id
            }

    @staticmethod
    def verify_single_with_history(
        index: int,
        row_index: int,
        round_number: int,
        session_id: str,
        query: str,
        target: str,
        prompt: str,
        model_config: Dict[str, Any],
        history_messages: list,
        extract_field: Optional[str] = None,
        reason_col_value: Optional[str] = None,
        api_config: Optional[Dict[str, Any]] = None,
        response_extract_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        带历史上下文的单条数据验证（多轮验证专用）

        :param index: 全局索引（用于进度追踪）
        :param row_index: 原始数据行索引
        :param round_number: 当前轮次（1-based）
        :param session_id: 会话 ID（同一行数据的多轮请求共享）
        :param query: 当前轮用户输入
        :param target: 预期输出
        :param prompt: 提示词
        :param model_config: 模型配置
        :param history_messages: 历史消息列表
        :param extract_field: 意图提取字段/路径 (可选)
        :param reason_col_value: 原因列值 (可选)
        :param api_config: 自定义 API 配置 (可选)，包含 api_url, api_headers, api_timeout, request_template
        :param response_extract_path: 回复内容提取路径 (可选)，用于从响应中提取 assistant 回复构建历史
        :return: 验证结果字典
        """
        import time
        import uuid

        request_id: str = str(uuid.uuid4())
        start_time: float = time.time()

        try:
            output = ""
            extracted_response = ""  # 用于构建下一轮历史的回复内容
            extracted_intent_value = None  # 提取的意图值
            request_params = None  # 完整入参

            # 判断使用哪种 API 调用方式
            # 1. 如果 api_config 存在且 request_template 是有效的 JSON（以 { 开头），使用 _call_custom_api
            # 2. 否则使用 _call_interface（Python 脚本方式）
            use_custom_api = False
            if api_config and api_config.get("api_url"):
                request_template = api_config.get("request_template", "").strip()
                # 检查是否是 JSON 模板（以 { 开头）
                if request_template.startswith("{"):
                    use_custom_api = True

            if use_custom_api:
                # 使用自定义 API 接口（JSON 模板变量替换）
                output, request_params = Verifier._call_custom_api(
                    query=query,
                    target=target,
                    prompt=prompt,
                    api_config=api_config,
                    history_messages=history_messages,
                    session_id=session_id,
                    current_round=round_number
                )

                # 使用 ResultExtractor 提取意图和回复（支持 py: 前缀的 Python 代码）
                from .extractor import ResultExtractor

                intent_path = extract_field or ""
                extracted_intent = ResultExtractor.extract(output, intent_path) if intent_path else None

                # 保存提取的意图值（转为字符串）
                if extracted_intent is not None:
                    if isinstance(extracted_intent, bool):
                        extracted_intent_value = str(extracted_intent)
                    else:
                        extracted_intent_value = str(extracted_intent).strip()

                if response_extract_path:
                    extracted_response = ResultExtractor.extract(output, response_extract_path)
                    if extracted_response is None:
                        extracted_response = ""
                    elif not isinstance(extracted_response, str):
                        extracted_response = json.dumps(extracted_response, ensure_ascii=False)

                # 检查匹配（使用提取的意图值）
                is_correct = False
                if extracted_intent is not None:
                    if isinstance(extracted_intent, bool):
                        is_correct = extracted_intent
                    else:
                        is_correct = str(extracted_intent).strip() == target.strip()
                else:
                    # 兜底：直接匹配
                    is_correct = target.strip() in output

            elif api_config and api_config.get("api_url"):
                # 使用 _call_interface（Python 脚本方式）
                # 构建兼容的 config 对象
                interface_config = {
                    "base_url": api_config.get("api_url"),
                    "interface_code": api_config.get("request_template", ""),
                    "api_key": "",  # 从 api_headers 中提取或留空
                    "timeout": api_config.get("api_timeout", 60),
                    "_request_id": request_id
                }

                output, request_params = Verifier._call_interface(
                    query, target, prompt, interface_config,
                    history_messages=history_messages,
                    session_id=session_id
                )

                # 使用 ResultExtractor 提取意图和回复
                from .extractor import ResultExtractor

                intent_path = extract_field or ""
                extracted_intent = ResultExtractor.extract(output, intent_path) if intent_path else None

                if extracted_intent is not None:
                    if isinstance(extracted_intent, bool):
                        extracted_intent_value = str(extracted_intent)
                    else:
                        extracted_intent_value = str(extracted_intent).strip()

                if response_extract_path:
                    extracted_response = ResultExtractor.extract(output, response_extract_path)
                    if extracted_response is None:
                        extracted_response = ""
                    elif not isinstance(extracted_response, str):
                        extracted_response = json.dumps(extracted_response, ensure_ascii=False)

                # 检查匹配
                is_correct = False
                if extracted_intent is not None:
                    if isinstance(extracted_intent, bool):
                        is_correct = extracted_intent
                    else:
                        is_correct = str(extracted_intent).strip() == target.strip()
                else:
                    is_correct = target.strip() in output

            else:
                # 使用原有逻辑（LLM 或旧接口模式）
                mode = model_config.get("validation_mode", "llm")
                config_with_request_id = {**model_config, "_request_id": request_id}

                if mode == "interface":
                    output, request_params = Verifier._call_interface(
                        query, target, prompt, config_with_request_id,
                        history_messages=history_messages,
                        session_id=session_id
                    )
                else:
                    output = Verifier._call_llm(
                        query, prompt, config_with_request_id,
                        None, history_messages
                    )

                output = Verifier._clean_markdown(output)
                is_correct = Verifier.check_match(output, target, extract_field)

            latency_ms: float = round((time.time() - start_time) * 1000, 2)

            result = {
                "index": index,
                "row_index": row_index,
                "round_number": round_number,
                "session_id": session_id,
                "query": query,
                "target": target,
                "reason": reason_col_value or "",
                "output": output,
                "is_correct": is_correct,
                "latency_ms": latency_ms,
                "request_id": request_id,
                "history_context": json.dumps(history_messages, ensure_ascii=False)
            }

            # 如果有完整入参，添加到结果中
            if request_params:
                result["request_params"] = request_params

            # 如果有提取的意图值，添加到结果中
            if extracted_intent_value is not None:
                result["extracted_intent"] = extracted_intent_value

            # 如果有提取的回复内容，添加到结果中
            if extracted_response:
                result["extracted_response"] = extracted_response

            return result

        except Exception as e:
            logger.error(f"[Verifier] Error index={index}, round={round_number}: {str(e)}")
            latency_ms: float = round((time.time() - start_time) * 1000, 2)
            return {
                "index": index,
                "row_index": row_index,
                "round_number": round_number,
                "session_id": session_id,
                "query": query,
                "target": target,
                "reason": reason_col_value or "",
                "output": f"ERROR: {str(e)}",
                "is_correct": False,
                "latency_ms": latency_ms,
                "request_id": request_id,
                "history_context": json.dumps(history_messages, ensure_ascii=False)
            }

    @staticmethod
    def _call_interface(
        query: str,
        target: str,
        prompt: str,
        config: Dict[str, Any],
        history_messages: Optional[list] = None,
        session_id: Optional[str] = None
    ) -> tuple:
        """
        调用自定义接口（支持多轮历史消息）

        :param query: 用户输入
        :param target: 预期输出
        :param prompt: 提示词
        :param config: 接口配置
        :param history_messages: 历史消息列表（可选）
        :param session_id: 会话 ID（可选）
        :return: (接口响应内容, 请求参数字典)
        """
        import requests

        interface_code = config.get("interface_code", "")
        base_url = config.get("base_url", "")
        api_key = config.get("api_key", "")
        timeout = int(config.get("timeout", 60))

        if not base_url:
            raise ValueError("Interface URL is required")

        # 准备执行环境
        # 为多轮验证提供 history 和 session_id 变量
        local_scope = {
            "query": query,
            "target": target,
            "prompt": prompt,
            "history": history_messages if history_messages is not None else [],
            "session_id": session_id if session_id is not None else "",
            "params": None
        }

        # 提供安全的内置模块
        import uuid as uuid_module
        import time as time_module
        import json as json_module
        safe_globals = {
            "__builtins__": {
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
                "list": list,
                "dict": dict,
                "tuple": tuple,
                "len": len,
                "range": range,
                "True": True,
                "False": False,
                "None": None,
            },
            "uuid": uuid_module,
            "time": time_module,
            "json": json_module
        }

        # 执行参数转换脚本
        try:
            exec(interface_code, safe_globals, local_scope)
            params = local_scope.get("params")
        except Exception as e:
            raise ValueError(f"Python script execution failed: {e}")

        if not isinstance(params, dict):
            raise ValueError("Script must assign a dict to 'params' variable")

        # 发起请求
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
            headers["api-key"] = api_key

        resp = requests.post(base_url, json=params, headers=headers, timeout=timeout)
        resp.raise_for_status()

        # 获取输出
        try:
            return json.dumps(resp.json(), ensure_ascii=False), params
        except:
            return resp.text, params

    @staticmethod
    def _call_custom_api(
        query: str,
        target: str,
        prompt: str,
        api_config: Dict[str, Any],
        history_messages: Optional[list] = None,
        session_id: Optional[str] = None,
        current_round: int = 1
    ) -> tuple:
        """
        调用自定义 API 接口（使用 JSON 模板变量替换）

        :param query: 当前轮用户输入
        :param target: 预期输出
        :param prompt: 提示词
        :param api_config: API 配置，包含 api_url, api_headers, api_timeout, request_template
        :param history_messages: 历史消息列表（OpenAI 格式）
        :param session_id: 会话 ID
        :param current_round: 当前轮次编号
        :return: (API 响应内容, 请求参数字典)
        """
        import requests

        api_url = api_config.get("api_url", "")
        api_headers_str = api_config.get("api_headers", "{}")
        api_timeout = int(api_config.get("api_timeout", 60))
        request_template = api_config.get("request_template", "{}")

        if not api_url:
            raise ValueError("API URL 不能为空")

        # 解析请求头
        try:
            custom_headers = json.loads(api_headers_str) if api_headers_str else {}
        except json.JSONDecodeError:
            custom_headers = {}

        # 准备变量替换
        history = history_messages if history_messages is not None else []
        history_json = json.dumps(history, ensure_ascii=False)

        # 构建历史文本格式
        history_text_parts = []
        for msg in history:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user":
                history_text_parts.append(f"用户: {content}")
            elif role == "assistant":
                history_text_parts.append(f"助手: {content}")
        history_text = "\n".join(history_text_parts)

        # 变量替换映射
        variables = {
            "{{current_query}}": query,
            "{{current_round}}": str(current_round),
            "{{session_id}}": session_id or "",
            "{{history}}": history_json,
            "{{history_text}}": history_text,
            "{{prompt}}": prompt,
            "{{target}}": target
        }

        # 执行变量替换
        request_body_str = request_template
        for var_name, var_value in variables.items():
            # 对于 {{history}}，不加引号（因为它本身是 JSON 数组）
            if var_name == "{{history}}":
                request_body_str = request_body_str.replace(var_name, var_value)
            else:
                # 其他变量需要转义特殊字符
                escaped_value = var_value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
                request_body_str = request_body_str.replace(var_name, escaped_value)

        # 解析请求体
        try:
            request_body = json.loads(request_body_str)
        except json.JSONDecodeError as e:
            logger.error(f"[Verifier] 请求体 JSON 解析失败: {request_body_str[:500]}")
            raise ValueError(f"请求体 JSON 格式错误: {e}")

        # 构建请求头
        headers = {"Content-Type": "application/json"}
        headers.update(custom_headers)

        logger.debug(f"[Verifier] _call_custom_api - URL: {api_url}")
        logger.debug(f"[Verifier] _call_custom_api - 请求体: {json.dumps(request_body, ensure_ascii=False)[:500]}")

        # 发起请求
        try:
            resp = requests.post(api_url, json=request_body, headers=headers, timeout=api_timeout)
            resp.raise_for_status()
        except requests.exceptions.Timeout:
            logger.error(f"[Verifier] _call_custom_api - 请求超时 (timeout={api_timeout}s)")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"[Verifier] _call_custom_api - 请求失败: {str(e)}")
            raise

        # 强制 UTF-8 编码
        resp.encoding = 'utf-8'

        # 返回响应
        try:
            return json.dumps(resp.json(), ensure_ascii=False), request_body
        except:
            return resp.text, request_body

    @staticmethod
    def extract_by_path(data: Any, path: str) -> Any:
        """
        根据字段路径从数据中提取值

        :param data: 数据对象（字典或 JSON 字符串）
        :param path: 字段路径，如 "data.intent" 或 "response.content"
        :return: 提取的值，如果路径无效则返回 None
        """
        if not path:
            return data

        # 如果是字符串，先解析为 JSON
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                return None

        # 按点号分割路径
        parts = path.split(".")
        current = data

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            elif isinstance(current, list):
                # 支持数组索引，如 "items.0.name"
                try:
                    idx = int(part)
                    current = current[idx]
                except (ValueError, IndexError):
                    return None
            else:
                return None

        return current

    @staticmethod
    def _call_llm(
        query: str, 
        prompt: str, 
        config: Dict[str, Any], 
        client=None,
        history_messages: Optional[list] = None
    ) -> str:
        """
        调用 LLM
        
        :param query: 用户输入
        :param prompt: 提示词
        :param config: 模型配置
        :param client: OpenAI 客户端（可选，当前未使用）
        :param history_messages: 历史消息列表（可选），每条消息包含 role 和 content
        :return: LLM 响应内容
        """
        return Verifier._call_llm_raw(query, prompt, config, history_messages)

    @staticmethod
    def _call_llm_raw(
        query: str, 
        prompt: str, 
        config: Dict[str, Any],
        history_messages: Optional[list] = None
    ) -> str:
        """
        通过原生 HTTP POST 请求调用 LLM API (OpenAI 兼容格式)
        
        相比使用 OpenAI 客户端库，此方法直接发送 HTTP 请求，
        适用于需要完全自定义请求或调试网络问题的场景。
        
        :param query: 用户输入
        :param prompt: 提示词
        :param config: 模型配置，包含 base_url, api_key, model_name 等
        :param history_messages: 可选的历史消息列表，每条消息格式为 {"role": str, "content": str}
        :return: LLM 响应内容
        :raises ValueError: 当配置缺失或响应格式异常时抛出
        :raises requests.RequestException: 当网络请求失败时抛出
        """
        import requests
        
        # 获取配置参数
        base_url: str = config.get("base_url", "")
        api_key: str = config.get("api_key", "")
        model_name: str = config.get("model_name", "gpt-3.5-turbo")
        temperature: float = float(config.get("temperature", 0))
        max_tokens: int = int(config.get("max_tokens", 2000))
        timeout: int = int(config.get("timeout", 60))
        
        if not base_url:
            raise ValueError("base_url 配置缺失")
        
        # 构建请求 URL (OpenAI 兼容格式)
        # 如果 base_url 不以 /chat/completions 结尾，则自动补全
        request_url: str = base_url
        if not request_url.endswith("/chat/completions"):
            request_url = request_url.rstrip("/") + "/chat/completions"
        
        # 构建请求头
        # 优先使用配置中传入的 request_id，否则生成新的
        import uuid
        request_id: str = config.get("_request_id") or str(uuid.uuid4())
        
        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "x-ms-client-request-id": request_id
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
            # 兼容 Azure OpenAI 格式
            headers["api-key"] = api_key
        
        # 构建消息列表
        # 顺序: system prompt(作为user) + assistant确认 -> 历史消息(原生多轮格式) -> 任务提醒(可选) -> 当前 query
        messages: list = []

        # 配置参数
        max_history_rounds: int = int(config.get("max_history_rounds", 5))  # 最大保留历史轮数
        task_reminder: str = config.get("task_reminder", "")  # 调用方传入的精准任务提醒

        # 1. 将系统提示词作为第一轮对话，后跟 assistant 确认，形成完整轮次
        system_msg: Dict[str, str] = {
            "role": "user",
            "content": prompt
        }
        messages.append(system_msg)

        # 添加 assistant 确认消息，形成完整的第一轮对话
        ack_msg: Dict[str, str] = {
            "role": "assistant",
            "content": "好的，我已理解上述要求，请提供需要处理的内容。"
        }
        messages.append(ack_msg)

        # 2. 添加历史对话（保持原生 user/assistant 交替结构）
        #    排除最后一条（当前问题），仅取最近N轮历史会话
        if history_messages:
            # 限制历史轮数：每轮 = 1个user + 1个assistant，所以消息数 = 轮数 * 2
            max_messages: int = max_history_rounds * 2
            truncated_history: list = history_messages[-max_messages:] if len(history_messages) > max_messages else history_messages

            # 保持原生多轮对话结构，不再压缩成单条消息
            for msg in truncated_history:
                role: str = msg.get("role", "user")
                content: str = msg.get("content", "")
                if role in ("user", "assistant") and content:
                    history_msg: Dict[str, str] = {
                        "role": role,
                        "content": content
                    }
                    messages.append(history_msg)

        # 3. 使用调用方传入的精准任务提醒（可选）
        #    在历史消息后插入一轮"提醒-确认"对话，强化模型对任务的记忆
        if task_reminder and history_messages:
            messages.append({"role": "user", "content": f"【重要提醒】{task_reminder}"})
            messages.append({"role": "assistant", "content": "好的，我会严格按照上述要求执行任务。"})

        # 4. 添加当前用户请求
        if query and query.strip():
            current_msg: Dict[str, str] = {
                "role": "user",
                "content": query
            }
            messages.append(current_msg)
        
        # 构建请求体
        payload: Dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        # 可选参数：do_sample
        do_sample: Optional[bool] = config.get("do_sample")
        if do_sample is not None:
            payload["do_sample"] = do_sample
        
        logger.debug(f"[Verifier] _call_llm_raw - 请求 URL: {request_url}")
        logger.debug(f"[Verifier] _call_llm_raw - 模型: {model_name}, temperature: {temperature}")
        logger.debug(f"[Verifier] _call_llm_raw - 请求头: {json.dumps(headers, ensure_ascii=False)}")
        logger.debug(f"[Verifier] _call_llm_raw - 请求参数: {json.dumps(payload, ensure_ascii=False, indent=2)}")
        
        # 发送 POST 请求
        try:
            response = requests.post(
                url=request_url,
                json=payload,
                headers=headers,
                timeout=timeout
            )
            response.raise_for_status()
        except requests.exceptions.Timeout:
            logger.error(f"[Verifier] _call_llm_raw - 请求超时 (timeout={timeout}s)")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"[Verifier] _call_llm_raw - 请求失败: {str(e)}")
            raise
        
        # 解析响应
        # 强制设置 UTF-8 编码，确保中文正确解析
        response.encoding = 'utf-8'
        try:
            resp_json: Dict[str, Any] = response.json()
        except json.JSONDecodeError as e:
            logger.error(f"[Verifier] _call_llm_raw - JSON 解析失败: {response.text[:500]}")
            raise ValueError(f"响应 JSON 解析失败: {str(e)}")
        
        # 提取内容 (OpenAI 兼容格式)
        choices: list = resp_json.get("choices", [])
        if not choices:
            logger.error(f"[Verifier] _call_llm_raw - 响应中无 choices: {resp_json}")
            raise ValueError("响应中不包含 choices 字段")
        
        content: str = choices[0].get("message", {}).get("content", "")
        if not content:
            logger.warning(f"[Verifier] _call_llm_raw - 响应内容为空")
        
        # 打印完整响应内容
        logger.debug(f"[Verifier] _call_llm_raw - 完整响应: {json.dumps(resp_json, ensure_ascii=False, indent=2)}")
        logger.debug(f"[Verifier] _call_llm_raw - 响应长度: {len(content)} 字符")
        return content

    @staticmethod
    def _clean_markdown(text: str) -> str:
        """去除 Markdown 代码块标记"""
        if "```" in text:
            match = re.search(r"```(?:\w+)?\s*(.*?)\s*```", text, re.DOTALL)
            if match:
                return match.group(1).strip()
            # 尝试简单去除
            return text.replace("```json", "").replace("```", "").strip()
        return text

    @staticmethod
    def check_match(output: str, target: str, extract_field: Optional[str] = None) -> bool:
        """检查结果是否匹配"""
        from .extractor import ResultExtractor
        
        output = output.strip()
        target = target.strip()
        
        # 使用统一提取器
        extracted_val = ResultExtractor.extract(output, extract_field)
        
        # 调试日志
        # logger.debug(f"[Verifier] check_match - target: '{target}', extract_field: '{extract_field}', extracted_val: '{extracted_val}', output[:100]: '{output[:100]}'")
        
        # 1. 提取到具体值的情况
        if extracted_val is not None:
            # 如果提取结果是字典（说明 extract_field 为空或无效），需要遍历值
            if isinstance(extracted_val, dict):
                 for val in extracted_val.values():
                    if str(val) == target:
                        return True
            else:
                # 提取到了具体值（布尔或字符串等）
                if isinstance(extracted_val, bool):
                    return extracted_val
                result = str(extracted_val) == target
                # logger.debug(f"[Verifier] Extracted comparison: '{str(extracted_val)}' == '{target}' => {result}")
                return result
        
        # 2. 兜底逻辑：直接匹配字符串
        if target == output:
            return True
            
        return target in output
