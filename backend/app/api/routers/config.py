from fastapi import APIRouter, Form
from typing import Dict, Any, Optional
from app.db import storage
from loguru import logger

router = APIRouter(prefix="/config", tags=["config"])


@router.get("")
async def get_config() -> Dict[str, Any]:
    """
    获取全局模型配置
    :return: 模型配置字典
    """
    config = storage.get_model_config()
    logger.debug("获取全局模型配置")
    return config


@router.post("")
async def save_config(
    base_url: str = Form(...), 
    api_key: str = Form(...),
    max_tokens: int = Form(2000),
    timeout: int = Form(60),
    model_name: str = Form("gpt-3.5-turbo"),
    protocol: str = Form("openai"),
    concurrency: int = Form(5),
    temperature: float = Form(0.0)
) -> Dict[str, str]:
    """
    保存全局模型配置
    :param base_url: API基础URL
    :param api_key: API密钥
    :param max_tokens: 最大Token数
    :param timeout: 超时时间
    :param model_name: 模型名称
    :param protocol: 协议类型
    :param concurrency: 并发数
    :param temperature: 温度参数
    :return: 操作状态
    """
    from starlette.concurrency import run_in_threadpool
    
    logger.info(f"保存全局配置: model={model_name}, protocol={protocol}, url={base_url}")
    await run_in_threadpool(storage.save_model_config, {
        "base_url": base_url, 
        "api_key": api_key,
        "max_tokens": max_tokens,
        "timeout": timeout,
        "model_name": model_name,
        "protocol": protocol,
        "concurrency": concurrency,
        "temperature": temperature
    })
    logger.info("全局模型配置已保存")
    return {"status": "success"}


@router.post("/test")
async def test_config(
    base_url: str = Form(...), 
    api_key: str = Form(None),
    model_name: str = Form("gpt-3.5-turbo"),
    protocol: str = Form("openai"),
    max_tokens: int = Form(5),
    temperature: float = Form(0.0),
    validation_mode: str = Form("llm"),
    interface_code: str = Form(""),
    extra_body: str = Form(None),
    default_headers: str = Form(None)
) -> Dict[str, Any]:
    """
    测试模型连接或接口代码
    :param base_url: API基础URL 或 接口地址
    :param api_key: API密钥
    :param model_name: 模型名称
    :param protocol: 协议类型 (openai/anthropic/gemini)
    :param max_tokens: 最大Token数
    :param temperature: 温度参数
    :param validation_mode: 验证模式 (llm/interface)
    :param interface_code: 接口转换代码
    :param extra_body: 额外请求体参数 (JSON)
    :param default_headers: 默认请求头 (JSON)
    :return: 测试结果
    """
    logger.info("-" * 30)
    logger.info(f"测试连接: URL={base_url} | 模式={validation_mode} | 协议={protocol}")
    
    try:
        import requests
        import json
        import os
        
        # 打印当前代理设置，帮助排查网络问题
        logger.info(f"当前 HTTP_PROXY: {os.environ.get('HTTP_PROXY')}")
        logger.info(f"当前 HTTPS_PROXY: {os.environ.get('HTTPS_PROXY')}")

        if validation_mode == "interface":
            # 接口验证模式测试
            
            if not base_url:
                raise ValueError("接口地址(base_url)是必需的")
                
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
                logger.error(f"脚本执行错误: {e}")
                raise ValueError(f"Python脚本语法错误或执行失败: {e}")
                
            if isinstance(params, dict):
                # 发起请求
                headers = {"Content-Type": "application/json"}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                    headers["api-key"] = api_key 
                
                logger.info(f"发送接口请求, 参数: {json.dumps(params, ensure_ascii=False)}")
                resp = requests.post(base_url, json=params, headers=headers, timeout=10)
                
                # 记录响应以便用户调试
                logger.info(f"接口响应: {resp.status_code} - {resp.text[:200]}...")
                
                resp.raise_for_status()
                return {"status": "success", "message": f"接口调用成功！状态码: {resp.status_code}"}
            else:
                 raise ValueError("脚本必须将有效的字典赋值给 'params' 变量")
            
        else:
            # LLM 模式测试 - 使用原生 HTTP 请求而不是 SDK
            logger.info(f"模型: {model_name}, 协议: {protocol}")
            logger.info(f"API Key: {api_key[:8]}******{api_key[-4:] if api_key and len(api_key) > 12 else ''}")
            
            # 通用请求头
            headers = {
                "Content-Type": "application/json"
            }
            
            # 解析 default_headers 并合并
            if default_headers:
                try:
                    user_headers = json.loads(default_headers)
                    if isinstance(user_headers, dict):
                        headers.update(user_headers)
                        logger.info(f"合并默认请求头: {user_headers}")
                except Exception as e:
                    logger.warning(f"解析 default_headers 失败: {e}")

            # 解析 extra_body
            extra_body_dict = {}
            if extra_body:
                try:
                    extra_body_dict = json.loads(extra_body)
                    logger.info(f"额外参数 (Extra Body): {extra_body_dict}")
                except Exception as e:
                    logger.warning(f"解析 extra_body 失败: {e}")
            
            request_url = base_url
            request_data = {}
            
            # 根据协议构建请求
            if protocol == "openai":
                # OpenAI 协议
                if not base_url.endswith("/v1") and not base_url.endswith("/chat/completions"):
                     if not base_url.endswith("/"):
                         base_url += "/"
                     request_url = f"{base_url}chat/completions"
                elif base_url.endswith("/v1"):
                     request_url = f"{base_url}/chat/completions"
                else:
                     request_url = base_url # 假设用户已经填了完整的

                headers["Authorization"] = f"Bearer {api_key}"
                
                request_data = {
                    "model": model_name,
                    "messages": [{"role": "user", "content": "Hi"}],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    **extra_body_dict
                }
                
            elif protocol == "anthropic":
                # Anthropic 协议
                if not base_url.endswith("/v1/messages") and not base_url.endswith("/messages"):
                     # 尝试自动修正
                     base = base_url.rstrip("/")
                     if base.endswith("/v1"):
                         request_url = f"{base}/messages"
                     else:
                         request_url = f"{base}/v1/messages"
                else:
                    request_url = base_url

                headers["x-api-key"] = api_key
                headers["anthropic-version"] = headers.get("anthropic-version", "2023-06-01")
                
                request_data = {
                    "model": model_name,
                    "messages": [{"role": "user", "content": "Hi"}],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    **extra_body_dict
                }
                
            elif protocol == "gemini":
                # Gemini 协议 (Google AI Studio)
                # URL 格式: https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent
                
                # 如果用户只填了 base domain
                base = base_url.rstrip("/")
                if "generativelanguage.googleapis.com" in base:
                     request_url = f"{base}/models/{model_name}:generateContent"
                else:
                     # 假设是兼容 Gemini 协议的第三方，或者用户填了完整 URL
                     if ":generateContent" not in base:
                         request_url = f"{base}/models/{model_name}:generateContent"
                     else:
                         request_url = base

                # Gemini通常把key放在query param
                if "?" not in request_url:
                    request_url += f"?key={api_key}"
                else:
                    request_url += f"&key={api_key}"
                
                # Gemini payload 结构不同
                request_data = {
                    "contents": [{
                        "parts": [{"text": "Hi"}]
                    }],
                    "generationConfig": {
                        "maxOutputTokens": max_tokens,
                        "temperature": temperature,
                        **extra_body_dict
                    }
                }
            else:
                raise ValueError(f"不支持的协议类型: {protocol}")

            logger.info(f"发送 HTTP 请求: POST {request_url}")
            # 隐藏敏感 key
            log_headers = headers.copy()
            if "Authorization" in log_headers:
                log_headers["Authorization"] = "Bearer ******"
            if "x-api-key" in log_headers:
                log_headers["x-api-key"] = "******"
                
            logger.debug(f"Headers: {log_headers}")
            logger.debug(f"Body: {json.dumps(request_data, ensure_ascii=False)}")
            
            resp = requests.post(request_url, json=request_data, headers=headers, timeout=10)
            
            logger.info(f"HTTP 响应: {resp.status_code}")
            if resp.status_code != 200:
                logger.error(f"响应内容: {resp.text[:500]}")
            
            resp.raise_for_status()
            
            # 简单验证响应格式
            resp_json = resp.json()
            if protocol == "openai":
                if "choices" not in resp_json:
                    logger.warning("响应格式似乎不是标准的 OpenAI 格式")
            elif protocol == "anthropic":
                if "content" not in resp_json:
                     logger.warning("响应格式似乎不是标准的 Anthropic 格式")
            elif protocol == "gemini":
                 if "candidates" not in resp_json:
                      logger.warning("响应格式似乎不是标准的 Gemini 格式")

            logger.info("连接测试成功！")
            return {"status": "success", "message": "连接成功！(Raw HTTP)"}
            
    except Exception as e:
        logger.error(f"连接失败: {str(e)}")
        logger.exception("完整堆栈信息:")
        return {"status": "error", "message": f"连接失败: {str(e)}"}
