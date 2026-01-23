from typing import Dict, Any
from openai import OpenAI, AsyncOpenAI
from loguru import logger

from .http_client import RawHTTPSyncClient, RawHTTPAsyncClient

class LLMFactory:
    """
    LLM 客户端工厂类，用于创建同步和异步的 OpenAI 客户端。
    """

    @staticmethod
    def _prepare_params(model_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        准备 OpenAI 客户端初始化所需的通用参数。

        :param model_config: 模型配置字典，包含 api_key, base_url 等信息
        :return: 处理后的参数字典
        """
        api_key = model_config.get("api_key", "")
        # 如果没有 api_key，打印警告日志，但在某些本地模型场景下可能允许为空
        if not api_key:
            logger.warning("未检测到 API Key，如果是本地模型请忽略此警告。")

        base_url = model_config.get("base_url", "https://api.openai.com/v1")
        
        # 构造默认请求头
        headers = {"Content-Type": "application/json; charset=utf-8"}
        
        # 合并用户自定义的 headers
        user_headers = model_config.get("default_headers")
        if user_headers and isinstance(user_headers, dict):
            headers.update(user_headers)
            
        return {
            "api_key": api_key,
            "base_url": base_url,
            "default_headers": headers
        }

    @staticmethod
    def create_client(model_config: Dict[str, Any]) -> OpenAI:
        """
        创建一个同步的 OpenAI 客户端。

        :param model_config: 模型配置信息
        :return: OpenAI 同步客户端实例
        """
        params = LLMFactory._prepare_params(model_config)
        masked_key = params['api_key'][:8] + "***" if params.get('api_key') else "None"
        logger.info(f"正在初始化同步 LLM 客户端 | BaseURL: {params.get('base_url')} | APIKey: {masked_key}")
        return OpenAI(**params)

    @staticmethod
    def create_async_client(model_config: Dict[str, Any]) -> AsyncOpenAI:
        """
        创建一个异步的 OpenAI 客户端。

        :param model_config: 模型配置信息
        :return: OpenAI 异步客户端实例
        """
        params = LLMFactory._prepare_params(model_config)
        masked_key = params['api_key'][:8] + "***" if params.get('api_key') else "None"
        logger.info(f"正在初始化异步 LLM 客户端 | BaseURL: {params.get('base_url')} | APIKey: {masked_key}")
        return AsyncOpenAI(**params)

    @staticmethod
    def create_raw_client(model_config: Dict[str, Any]) -> RawHTTPSyncClient:
        """
        创建一个原始 HTTP 同步客户端。

        :param model_config: 模型配置信息
        :return: RawHTTPSyncClient 实例
        """
        params = LLMFactory._prepare_params(model_config)
        protocol = model_config.get("protocol")
        
        # 自动推断协议，如果未指定
        if not protocol:
            base_url = params.get('base_url', '').lower()
            model_name = model_config.get('model_name', '').lower()
            
            if "anthropic" in base_url or "claude" in model_name:
                protocol = "anthropic"
            elif "generativelanguage.googleapis.com" in base_url or "gemini" in base_url or "gemini" in model_name:
                protocol = "gemini"
            else:
                protocol = "openai"
                
        masked_key = params['api_key'][:8] + "***" if params.get('api_key') else "None"
        logger.info(f"正在初始化 Raw HTTP 同步客户端 | Protocol: {protocol} | BaseURL: {params.get('base_url')}")
        
        return RawHTTPSyncClient(
            base_url=params['base_url'],
            api_key=params['api_key'],
            protocol=protocol,
            default_headers=params['default_headers']
        )

    @staticmethod
    def create_raw_async_client(model_config: Dict[str, Any]) -> RawHTTPAsyncClient:
        """
        创建一个原始 HTTP 异步客户端。

        :param model_config: 模型配置信息
        :return: RawHTTPAsyncClient 实例
        """
        params = LLMFactory._prepare_params(model_config)
        protocol = model_config.get("protocol")

        # 自动推断协议
        if not protocol:
            base_url = params.get('base_url', '').lower()
            model_name = model_config.get('model_name', '').lower()
            
            if "anthropic" in base_url or "claude" in model_name:
                protocol = "anthropic"
            elif "generativelanguage.googleapis.com" in base_url or "gemini" in base_url or "gemini" in model_name:
                protocol = "gemini"
            else:
                protocol = "openai"

        masked_key = params['api_key'][:8] + "***" if params.get('api_key') else "None"
        logger.info(f"正在初始化 Raw HTTP 异步客户端 | Protocol: {protocol} | BaseURL: {params.get('base_url')}")
        
        return RawHTTPAsyncClient(
            base_url=params['base_url'],
            api_key=params['api_key'],
            protocol=protocol,
            default_headers=params['default_headers']
        )
