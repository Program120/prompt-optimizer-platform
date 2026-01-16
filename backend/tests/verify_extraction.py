
import asyncio
from app.engine.diagnosis.intent import IntentAnalyzer
from app.engine.helpers.extractor import ResultExtractor
from loguru import logger

async def test_extraction():
    # Test case 1: Default extraction (intent field)
    json_output_1 = '{"intent": "default_intent", "confidence": 0.9}'
    extracted_1 = IntentAnalyzer._extract_intent_from_output(json_output_1)
    print(f"Test 1 (Default): Expected 'default_intent', Got '{extracted_1}'")
    assert extracted_1 == "default_intent"

    # Test case 2: Default extraction (intent_type clarification)
    json_output_2 = '{"intent_type": "clarification", "question": "what?"}'
    extracted_2 = IntentAnalyzer._extract_intent_from_output(json_output_2)
    print(f"Test 2 (Default Clarification): Expected 'clarification', Got '{extracted_2}'")
    assert extracted_2 == "clarification"

    # Test case 3: Custom extraction code (extracting from 'category')
    custom_code = """
try:
    if "category" in data:
        result = data["category"]
    else:
        result = "unknown"
except:
    result = None
"""
    json_output_3 = '{"category": "custom_category", "intent": "ignored"}'
    extracted_3 = IntentAnalyzer._extract_intent_from_output(json_output_3, custom_code=custom_code)
    print(f"Test 3 (Custom Code): Expected 'custom_category', Got '{extracted_3}'")
    assert extracted_3 == "custom_category"

    # Test case 4: Custom extraction code failure fallback
    bad_code = "result = 1 / 0"
    extracted_4 = IntentAnalyzer._extract_intent_from_output(json_output_1, custom_code=bad_code)
    print(f"Test 4 (Custom Code Failure): Expected 'default_intent', Got '{extracted_4}'")
    assert extracted_4 == "default_intent"
    
    # Test case 5: Custom extraction matching user scenario (with auto unpacking)
    user_custom_code = """
result = "多意图"
if intent_type == 'clarification':
    result = "需澄清"
elif intent_type == 'single':
    result = data.get('intent', '未知意图')
else:
    result = "未知意图类型"
"""
    json_output_5 = '{"intent_type": "single", "intent": "unpacked_intent"}'
    extracted_5 = IntentAnalyzer._extract_intent_from_output(json_output_5, custom_code=user_custom_code)
    print(f"Test 5 (Auto Unpack): Expected 'unpacked_intent', Got '{extracted_5}'")
    assert extracted_5 == "unpacked_intent"
    
    print("All tests passed!")

if __name__ == "__main__":
    asyncio.run(test_extraction())
