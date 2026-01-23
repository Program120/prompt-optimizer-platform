import json
import requests
import httpx
from typing import Dict, Any, List, Optional, Union
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log

class RawResponse:
    def __init__(self, content: str, role: str = "assistant"):
        self.choices = [
            type('Choice', (), {
                'message': type('Message', (), {
                    'content': content,
                    'role': role
                })()
            })()
        ]

class RawHTTPSyncClient:
    def __init__(self, base_url: str, api_key: str, protocol: str = "openai", default_headers: Dict[str, str] = None):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.protocol = protocol
        self.default_headers = default_headers or {}
        self.chat = self

    @property
    def completions(self):
        return self

    @retry(
        retry=retry_if_exception_type(requests.exceptions.HTTPError),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before_sleep=before_sleep_log(logger, "WARNING"),
        reraise=True
    )
    def create(self, model: str, messages: List[Dict[str, str]], **kwargs) -> RawResponse:
        timeout = kwargs.pop("timeout", 60)
        url = ""
        headers = self.default_headers.copy()
        data = {}

        if self.protocol == "openai":
            # Robust URL construction for OpenAI
            if not self.base_url.endswith("/v1") and not self.base_url.endswith("/chat/completions"):
                 url = f"{self.base_url}/chat/completions"
                 # Ensure v1 if missing? original logic was less strict, but let's try to match it
                 # Original: if not /v1 and not /chat/completions -> append chat/completions
                 # But usually it's /v1/chat/completions. 
                 # Let's trust base_url but append endpoint if missing
            elif self.base_url.endswith("/v1"):
                 url = f"{self.base_url}/chat/completions"
            else:
                 # If base_url already has full path, use it? RawHTTPSyncClient init rstrips /.
                 if "chat/completions" not in self.base_url:
                    url = f"{self.base_url}/chat/completions"
                 else:
                    url = self.base_url

            headers["Authorization"] = f"Bearer {self.api_key}"
            data = {
                "model": model,
                "messages": messages,
                **kwargs
            }
        elif self.protocol == "anthropic":
            # Robust URL construction for Anthropic
            # Mimic original logic: check for /v1 suffix or /messages suffix
            if not self.base_url.endswith("/messages"):
                 base = self.base_url
                 if base.endswith("/v1"):
                     url = f"{base}/messages"
                 else:
                     # Check if we should add v1
                     # Original said: if not v1 -> v1/messages
                     url = f"{base}/v1/messages"
            else:
                url = self.base_url

            headers["x-api-key"] = self.api_key
            if "anthropic-version" not in headers:
                headers["anthropic-version"] = "2023-06-01"
            
            # Convert messages to Anthropic format
            system_message = ""
            user_messages = []
            for msg in messages:
                if msg["role"] == "system":
                    system_message = msg["content"]
                elif msg["role"] == "user" or msg["role"] == "assistant":
                    user_messages.append(msg)
            
            data = {
                "model": model,
                "messages": user_messages,
                **kwargs
            }
            if system_message:
                data["system"] = system_message
                
             # Max tokens is required for Anthropic usually, but we handle via kwargs or default
            if "max_tokens" not in data:
                 data["max_tokens"] = 2000 # Default for safety

        elif self.protocol == "gemini":
            url = f"{self.base_url}/models/{model}:generateContent?key={self.api_key}"
            headers["Content-Type"] = "application/json"
            
            # Convert to Gemini format
            contents = []
            system_instruction = None
            
            for msg in messages:
                role = "user" if msg["role"] == "user" else "model"
                if msg["role"] == "system":
                     system_instruction = {"parts": [{"text": msg["content"]}]}
                     continue
                contents.append({
                    "role": role,
                    "parts": [{"text": msg["content"]}]
                })
            
            data = {
                "contents": contents,
                **({"systemInstruction": system_instruction} if system_instruction else {}),
                # Map kwargs to generationConfig
                "generationConfig": {k: v for k, v in kwargs.items() if k in ["temperature", "maxOutputTokens", "topP", "topK"]}
            }
            # Map max_tokens to maxOutputTokens
            if "max_tokens" in kwargs:
                data["generationConfig"]["maxOutputTokens"] = kwargs["max_tokens"]

        try:
            response = requests.post(url, headers=headers, json=data, timeout=timeout)
            response.raise_for_status()
            response_json = response.json()
            
            content = ""
            if self.protocol == "openai":
                content = response_json["choices"][0]["message"]["content"]
            elif self.protocol == "anthropic":
                content = response_json["content"][0]["text"]
            elif self.protocol == "gemini":
                 if "candidates" in response_json and response_json["candidates"]:
                    parts = response_json["candidates"][0].get("content", {}).get("parts", [])
                    if parts:
                        content = parts[0].get("text", "")

            return RawResponse(content)

        except Exception as e:
            logger.error(f"Raw HTTP Sync Request failed: {e}")
            raise

class RawHTTPAsyncClient:
    def __init__(self, base_url: str, api_key: str, protocol: str = "openai", default_headers: Dict[str, str] = None):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.protocol = protocol
        self.default_headers = default_headers or {}
        self.chat = self

    @property
    def completions(self):
        return self

    @retry(
        retry=retry_if_exception_type(httpx.HTTPStatusError),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before_sleep=before_sleep_log(logger, "WARNING"),
        reraise=True
    )
    async def create(self, model: str, messages: List[Dict[str, str]], **kwargs) -> RawResponse:
        timeout = kwargs.pop("timeout", 60)
        url = ""
        headers = self.default_headers.copy()
        data = {}

        if self.protocol == "openai":
            # Robust URL construction for OpenAI
            if not self.base_url.endswith("/v1") and not self.base_url.endswith("/chat/completions"):
                 # Handle cases where user only inputs host
                 if "chat/completions" not in self.base_url:
                    # check if we should add v1. Standard is /v1/chat/completions
                    # If base url is just ip:port, append v1/chat/completions
                    # This is an assumption but safer for simple inputs
                    url = f"{self.base_url}/chat/completions" 
                    # Note: original config.py simply appended chat/completions if not present. 
                    # If base has NO v1, it appends chat/completions. 
                    # Raw client init striped /.
            elif self.base_url.endswith("/v1"):
                 url = f"{self.base_url}/chat/completions"
            else:
                 if "chat/completions" not in self.base_url:
                     url = f"{self.base_url}/chat/completions"
                 else:
                     url = self.base_url

            headers["Authorization"] = f"Bearer {self.api_key}"
            data = {
                "model": model,
                "messages": messages,
                **kwargs
            }
        elif self.protocol == "anthropic":
            # Robust URL construction
            if not self.base_url.endswith("/messages"):
                 base = self.base_url
                 if base.endswith("/v1"):
                     url = f"{base}/messages"
                 else:
                     url = f"{base}/v1/messages"
            else:
                url = self.base_url

            headers["x-api-key"] = self.api_key
            if "anthropic-version" not in headers:
                headers["anthropic-version"] = "2023-06-01"
            
            system_message = ""
            user_messages = []
            for msg in messages:
                if msg["role"] == "system":
                    system_message = msg["content"]
                elif msg["role"] == "user" or msg["role"] == "assistant":
                    user_messages.append(msg)
            
            data = {
                "model": model,
                "messages": user_messages,
                **kwargs
            }
            if system_message:
                data["system"] = system_message

            if "max_tokens" not in data:
                 data["max_tokens"] = 2000

        elif self.protocol == "gemini":
            url = f"{self.base_url}/models/{model}:generateContent?key={self.api_key}"
            headers["Content-Type"] = "application/json"
            
            contents = []
            system_instruction = None

            for msg in messages:
                role = "user" if msg["role"] == "user" else "model"
                if msg["role"] == "system":
                     system_instruction = {"parts": [{"text": msg["content"]}]}
                     continue
                contents.append({
                    "role": role,
                    "parts": [{"text": msg["content"]}]
                })
            
            data = {
                "contents": contents,
                **({"systemInstruction": system_instruction} if system_instruction else {}),
                 "generationConfig": {k: v for k, v in kwargs.items() if k in ["temperature", "maxOutputTokens", "topP", "topK"]}
            }
            if "max_tokens" in kwargs:
                data["generationConfig"]["maxOutputTokens"] = kwargs["max_tokens"]

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, headers=headers, json=data)
                response.raise_for_status()
                response_json = response.json()
                
                content = ""
                if self.protocol == "openai":
                    content = response_json["choices"][0]["message"]["content"]
                elif self.protocol == "anthropic":
                    content = response_json["content"][0]["text"]
                elif self.protocol == "gemini":
                     if "candidates" in response_json and response_json["candidates"]:
                        parts = response_json["candidates"][0].get("content", {}).get("parts", [])
                        if parts:
                            content = parts[0].get("text", "")
                
                return RawResponse(content)

        except Exception as e:
            logger.error(f"Raw HTTP Async Request failed: {e}")
            raise
