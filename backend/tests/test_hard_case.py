
import sys
import os
import logging
from typing import List, Dict, Any

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from optimizer_engine.hard_case_detection import HardCaseDetector

# Mock LLM Client
class MockLLMClient:
    class Embeddings:
        def create(self, input, model):
            class Response:
                class Data:
                    def __init__(self, embedding):
                        self.embedding = embedding
                def __init__(self, data):
                    self.data = data
            
            # Return random embeddings
            import random
            data_objs = []
            for _ in input:
                emb = [random.random() for _ in range(10)] # 10-dim embedding
                data_objs.append(Response.Data(emb))
            return Response(data_objs)
            
    embeddings = Embeddings()

def test_hard_case_detection():
    print("Testing HardCaseDetector...")
    
    # Mock Data
    predictions = [
        {"query": "User login failure", "target": "Authentication", "output": "General", "probs": {"Authentication": 0.4, "General": 0.5}, "case_id": 1},
        {"query": "Password reset error", "target": "Authentication", "output": "Authentication", "probs": {"Authentication": 0.9, "General": 0.1}, "case_id": 2}, 
        {"query": "Payment declined", "target": "Billing", "output": "Billing", "probs": {"Billing": 0.8, "Account": 0.2}, "case_id": 3},
        {"query": "Where is my invoice?", "target": "Billing", "output": "General", "probs": {"Billing": 0.45, "General": 0.55}, "case_id": 4},
        {"query": "Account locked", "target": "Authentication", "output": "Security", "probs": {"Authentication": 0.3, "Security": 0.4}, "case_id": 5},
    ]
    
    detector = HardCaseDetector(llm_client=MockLLMClient())
    
    hard_cases = detector.detect_hard_cases(predictions, top_k=5)
    
    print(f"Found {len(hard_cases)} hard cases.")
    for case in hard_cases:
        print(f"Case: {case['case']['query']}")
        print(f"  Reason: {case['reason']}")
        print(f"  Score: {case['score']:.4f}")
        print("-" * 20)
        
    assert len(hard_cases) > 0, "Should detect some hard cases"
    print("Test Passed!")

if __name__ == "__main__":
    test_hard_case_detection()
