import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.main import app

class TestModelVerification(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch('requests.post')
    def test_openai_verification(self, mock_post):
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": [{"message": {"content": "Hello"}}]}
        mock_post.return_value = mock_response

        response = self.client.post("/config/test", data={
            "base_url": "https://api.openai.com/v1",
            "api_key": "sk-test",
            "model_name": "gpt-3.5-turbo",
            "protocol": "openai",
            "validation_mode": "llm"
        })

        self.assertEqual(response.status_code, 200)
        json_resp = response.json()
        self.assertEqual(json_resp["status"], "success")

        # Verify request call
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://api.openai.com/v1/chat/completions")
        self.assertEqual(kwargs['headers']['Authorization'], "Bearer sk-test")
        self.assertEqual(kwargs['json']['model'], "gpt-3.5-turbo")

    @patch('requests.post')
    def test_anthropic_verification(self, mock_post):
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"content": [{"text": "Hello"}]}
        mock_post.return_value = mock_response

        response = self.client.post("/config/test", data={
            "base_url": "https://api.anthropic.com",
            "api_key": "sk-ant-test",
            "model_name": "claude-2",
            "protocol": "anthropic",
            "validation_mode": "llm"
        })

        self.assertEqual(response.status_code, 200)
        json_resp = response.json()
        self.assertEqual(json_resp["status"], "success")

        # Verify request call
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://api.anthropic.com/v1/messages")
        self.assertEqual(kwargs['headers']['x-api-key'], "sk-ant-test")
        self.assertEqual(kwargs['headers']['anthropic-version'], "2023-06-01")
        self.assertEqual(kwargs['json']['model'], "claude-2")

    @patch('requests.post')
    def test_gemini_verification(self, mock_post):
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"candidates": [{"content": {"parts": [{"text": "Hello"}]}}]}
        mock_post.return_value = mock_response

        response = self.client.post("/config/test", data={
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "api_key": "gemini-key",
            "model_name": "gemini-pro",
            "protocol": "gemini",
            "validation_mode": "llm"
        })

        self.assertEqual(response.status_code, 200)
        json_resp = response.json()
        self.assertEqual(json_resp["status"], "success")

        # Verify request call
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        expected_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key=gemini-key"
        self.assertEqual(args[0], expected_url)
        self.assertEqual(kwargs['json']['contents'][0]['parts'][0]['text'], "Hi")

if __name__ == '__main__':
    unittest.main()
