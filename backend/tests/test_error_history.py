import sys
import os
import hashlib
from typing import List, Dict, Any

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.engine.helpers.error_history import update_error_optimization_history

def test_duplicate_errors_counting():
    """Test that duplicate errors are counted only once per optimization round"""
    print("Testing duplicate errors counting...")
    
    # Mock Data: Two identical errors
    errors = [
        {"query": "Test Query", "target": "Test Intent", "output": "Wrong Output"},
        {"query": "Test Query", "target": "Test Intent", "output": "Wrong Output"},
    ]
    
    history = {}
    optimized_intents = ["Test Intent"]
    
    # First update
    updated_history = update_error_optimization_history(errors, history, optimized_intents)
    
    # Verify
    hash_key = hashlib.md5("Test Query:Test Intent".encode()).hexdigest()[:16]
    
    if hash_key in updated_history:
        count = updated_history[hash_key]["optimization_count"]
        print(f"Optimization Count: {count}")
        
        # Before fix, this might be 2. After fix, it should be 1.
        if count == 1:
            print("SUCCESS: Count is 1 (Correct behavior for single round)")
        else:
            print(f"FAILURE: Count is {count} (Should be 1)")
    else:
        print("FAILURE: Key not found in history")

def test_attribution_filtering():
    """Test that only errors matching optimized_intents are tracked"""
    print("\nTesting attribution filtering...")
    
    errors = [
        {"query": "Q1", "target": "Intent A", "output": "O1"},
        {"query": "Q2", "target": "Intent B", "output": "O2"},
    ]
    
    history = {}
    optimized_intents = ["Intent A"]
    
    updated_history = update_error_optimization_history(errors, history, optimized_intents)
    
    # Check Intent A exists
    hash_key_a = hashlib.md5("Q1:Intent A".encode()).hexdigest()[:16]
    assert hash_key_a in updated_history, "Intent A should be tracked"
    
    # Check Intent B does NOT exist
    hash_key_b = hashlib.md5("Q2:Intent B".encode()).hexdigest()[:16]
    assert hash_key_b not in updated_history, "Intent B should NOT be tracked"
    
    print("SUCCESS: Attribution filtering works correctly")

if __name__ == "__main__":
    test_duplicate_errors_counting()
    test_attribution_filtering()
