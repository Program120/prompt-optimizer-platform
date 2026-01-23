import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import sys
import os
import asyncio

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.services.optimizer_service import optimize_prompt, multi_strategy_optimize
from app.core.http_client import RawHTTPSyncClient, RawHTTPAsyncClient, RawResponse

class TestOptimizerServiceRefactor(unittest.TestCase):
    
    @patch('app.services.optimizer_service.LLMFactory.create_raw_client')
    def test_optimize_prompt_raw_client(self, mock_create_client):
        # Setup mock behavior
        mock_client = MagicMock(spec=RawHTTPSyncClient)
        mock_create_client.return_value = mock_client
        
        # Mock completions.create return value
        mock_response = RawResponse("Optimized Prompt Content")
        # Ensure chat.completions.create returns mock_response
        mock_client.chat = MagicMock()
        mock_client.chat.completions = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        
        # Call function
        model_config = {
            "model_name": "gpt-3.5-turbo",
            "protocol": "openai",
             "api_key": "test",
             "base_url": "http://test"
        }
        result = optimize_prompt(
            old_prompt="Old Prompt",
            errors=[{"reason": "error", "query": "q", "target": "t", "output": "o"}],
            model_config=model_config
        )
        
        # Assertions
        self.assertEqual(result, "Optimized Prompt Content")
        mock_create_client.assert_called_once_with(model_config)
        mock_client.chat.completions.create.assert_called_once()
        
    @patch('app.services.optimizer_service.LLMFactory.create_raw_async_client')
    @patch('app.services.optimizer_service.MultiStrategyOptimizer')
    def test_multi_strategy_optimize_raw_client(self, mock_optimizer_cls, mock_create_async_client):
        # Setup mocks
        mock_client = AsyncMock(spec=RawHTTPAsyncClient)
        mock_create_async_client.return_value = mock_client
        
        mock_optimizer_instance = AsyncMock()
        mock_optimizer_cls.return_value = mock_optimizer_instance
        
        mock_optimizer_instance.optimize.return_value = {
            "optimized_prompt": "Multi Strategy Optimized",
            "diagnosis": {},
            "applied_strategies": [],
            "message": "Success"
        }
        
        # Run async test
        async def run_test():
            model_config = {
                "model_name": "gpt-4",
                "protocol": "openai",
                "api_key": "test",
                "base_url": "http://test"
            }
            result = await multi_strategy_optimize(
                old_prompt="Old Prompt",
                errors=[{"reason": "error", "query": "q", "target": "t", "output": "o"}],
                model_config=model_config
            )
            return result
            
        result = asyncio.run(run_test())
        
        # Assertions
        self.assertEqual(result["optimized_prompt"], "Multi Strategy Optimized")
        mock_create_async_client.assert_called()
        # Verify optimizer was initialized with our raw client
        mock_optimizer_cls.assert_called()
        call_args = mock_optimizer_cls.call_args
        self.assertEqual(call_args.kwargs['llm_client'], mock_client)

if __name__ == '__main__':
    unittest.main()
