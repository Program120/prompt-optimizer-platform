import unittest
from fastapi.testclient import TestClient
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.main import app
from app.db import storage

class TestGlobalModelProtocol(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        # Clean up any existing test models
        self.created_ids = []

    def tearDown(self):
        # Clean up created models
        for model_id in self.created_ids:
            storage.delete_global_model(model_id)

    def test_create_global_model_with_protocol(self):
        # Test creating a model with specific protocol
        payload = {
            "name": "Test Anthropic Model",
            "base_url": "https://api.anthropic.com",
            "api_key": "sk-ant-test",
            "model_name": "claude-2",
            "protocol": "anthropic",
            "max_tokens": 1000
        }
        
        response = self.client.post("/global-models", json=payload)
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.created_ids.append(data["id"])
        
        # Verify protocol in response
        self.assertEqual(data["protocol"], "anthropic")
        
        # Verify persistence in DB
        db_model = storage.get_global_model(data["id"])
        self.assertEqual(db_model["protocol"], "anthropic")

    def test_update_global_model_protocol(self):
        # Create a model with default protocol (openai)
        payload = {
            "name": "Test Update Model",
            "base_url": "https://api.openai.com",
            "api_key": "sk-test",
            "model_name": "gpt-3.5",
        }
        response = self.client.post("/global-models", json=payload)
        self.assertEqual(response.status_code, 200)
        model_id = response.json()["id"]
        self.created_ids.append(model_id)
        
        # Update protocol to gemini
        update_payload = {
            "protocol": "gemini",
            "model_name": "gemini-pro"
        }
        
        response = self.client.put(f"/global-models/{model_id}", json=update_payload)
        self.assertEqual(response.status_code, 200, f"Update failed: {response.text}")
        
        data = response.json()
        self.assertEqual(data["protocol"], "gemini")
        
        # Verify persistence
        db_model = storage.get_global_model(model_id)
        self.assertEqual(db_model["protocol"], "gemini")

if __name__ == '__main__':
    unittest.main()
