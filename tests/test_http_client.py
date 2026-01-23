
import pytest
from unittest.mock import patch, MagicMock
from app.core.http_client import RawHTTPSyncClient

class TestRawHTTPSyncClient:
    
    @patch('app.core.http_client.requests.post')
    def test_openai_url_construction(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "response"}}]}
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Case 1: Standard URL
        client = RawHTTPSyncClient(base_url="https://api.openai.com/v1", api_key="sk-...", protocol="openai")
        client.create("gpt-3.5-turbo", [{"role": "user", "content": "hi"}])
        args, kwargs = mock_post.call_args
        assert args[0] == "https://api.openai.com/v1/chat/completions"

        # Case 2: No v1, pure host
        client = RawHTTPSyncClient(base_url="https://api.openai.com", api_key="sk-...", protocol="openai")
        client.create("gpt-3.5-turbo", [{"role": "user", "content": "hi"}])
        args, kwargs = mock_post.call_args
        # Based on logic: if not v1 and not chat/completions -> append chat/completions
        # If the code assumes v1 if missing, or just appends. 
        # Code: if not /v1 and not /chat/completions -> url = f"{base}/chat/completions"
        assert args[0] == "https://api.openai.com/chat/completions"

        # Case 3: specific endpoint
        client = RawHTTPSyncClient(base_url="https://custom.host/v1/chat/completions", api_key="sk-...", protocol="openai")
        client.create("gpt-3.5-turbo", [{"role": "user", "content": "hi"}])
        args, kwargs = mock_post.call_args
        assert args[0] == "https://custom.host/v1/chat/completions"

    @patch('app.core.http_client.requests.post')
    def test_anthropic_url_construction(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"content": [{"text": "response"}]}
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Case 1: Standard URL
        client = RawHTTPSyncClient(base_url="https://api.anthropic.com", api_key="sk-...", protocol="anthropic")
        client.create("claude-2", [{"role": "user", "content": "hi"}])
        args, kwargs = mock_post.call_args
        # Code: if not /messages -> if not /v1 -> /v1/messages
        assert args[0] == "https://api.anthropic.com/v1/messages"

        # Case 2: With v1
        client = RawHTTPSyncClient(base_url="https://api.anthropic.com/v1", api_key="sk-...", protocol="anthropic")
        client.create("claude-2", [{"role": "user", "content": "hi"}])
        args, kwargs = mock_post.call_args
        # Code: if not /messages -> if v1 -> /messages
        assert args[0] == "https://api.anthropic.com/v1/messages"

        # Case 3: With messages
        client = RawHTTPSyncClient(base_url="https://api.anthropic.com/v1/messages", api_key="sk-...", protocol="anthropic")
        client.create("claude-2", [{"role": "user", "content": "hi"}])
        args, kwargs = mock_post.call_args
        assert args[0] == "https://api.anthropic.com/v1/messages"

    @patch('app.core.http_client.requests.post')
    def test_gemini_url_construction(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"candidates": [{"content": {"parts": [{"text": "response"}]}}]}
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        client = RawHTTPSyncClient(base_url="https://generativelanguage.googleapis.com/v1beta", api_key="key", protocol="gemini")
        client.create("gemini-pro", [{"role": "user", "content": "hi"}])
        args, kwargs = mock_post.call_args
        # Code: f"{self.base_url}/models/{model}:generateContent?key={self.api_key}"
        assert args[0] == "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key=key"
