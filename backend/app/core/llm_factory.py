
from openai import OpenAI, AsyncOpenAI
from typing import Dict, Optional, Any

class LLMFactory:
    @staticmethod
    def _prepare_params(model_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare common parameters for OpenAI client initialization.
        """
        api_key = model_config.get("api_key", "")
        base_url = model_config.get("base_url", "https://api.openai.com/v1")
        
        # Construct default headers
        headers = {"Content-Type": "application/json; charset=utf-8"}
        
        # Merge user-provided default_headers
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
        Create a synchronous OpenAI client.
        """
        params = LLMFactory._prepare_params(model_config)
        return OpenAI(**params)

    @staticmethod
    def create_async_client(model_config: Dict[str, Any]) -> AsyncOpenAI:
        """
        Create an asynchronous OpenAI client.
        """
        params = LLMFactory._prepare_params(model_config)
        return AsyncOpenAI(**params)
