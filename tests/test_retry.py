
import pytest
import requests
import httpx
from unittest.mock import patch, MagicMock
from tenacity import RetryError
from app.core.http_client import RawHTTPSyncClient, RawHTTPAsyncClient

class TestRawHTTPClientRetry:

    @patch('app.core.http_client.requests.post')
    def test_sync_client_retry_429(self, mock_post):
        # Mock a 429 response
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("429 Too Many Requests", response=mock_response)
        
        mock_post.return_value = mock_response

        client = RawHTTPSyncClient(base_url="https://api.openai.com/v1", api_key="sk-...", protocol="openai")
        
        # Expect RetryError because it will retry 5 times and then fail
        with pytest.raises(RetryError):
            client.create("gpt-3.5-turbo", [{"role": "user", "content": "hi"}])
        
        # Verify that it was called multiple times (5 attempts)
        assert mock_post.call_count == 5

    @patch('app.core.http_client.requests.post')
    def test_sync_client_success_after_retry(self, mock_post):
        # Mock 429 twice, then 200
        fail_response = MagicMock()
        fail_response.status_code = 429
        fail_response.raise_for_status.side_effect = requests.exceptions.HTTPError("429", response=fail_response)
        
        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {"choices": [{"message": {"content": "success"}}]}
        
        mock_post.side_effect = [fail_response, fail_response, success_response]

        client = RawHTTPSyncClient(base_url="https://api.openai.com/v1", api_key="sk-...", protocol="openai")
        
        response = client.create("gpt-3.5-turbo", [{"role": "user", "content": "hi"}])
        
        assert response.choices[0].message.content == "success"
        assert mock_post.call_count == 3
