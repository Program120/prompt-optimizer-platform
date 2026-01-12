import unittest
import json
from task_manager import TaskManager

class TestExtraction(unittest.TestCase):
    def setUp(self):
        self.tm = TaskManager()

    def test_normal_field_extraction(self):
        output = '{"intent": "buy_ticket", "confidence": 0.9}'
        target = "buy_ticket"
        
        # Test basic match
        self.assertTrue(self.tm._check_match(output, target, "intent"))
        # Test mismatch
        self.assertFalse(self.tm._check_match(output, "other", "intent"))

    def test_expression_extraction_single(self):
        output = '{"intent_type": "single", "intent": "agent_id_name", "confidence": 0.95}'
        target = "agent_id_name"
        
        # Scenario: if intent_type is single, check intent field
        field = "py: data['intent'] if data.get('intent_type') == 'single' else 'NOMATCH'"
        self.assertTrue(self.tm._check_match(output, target, field))

    def test_expression_extraction_multiple(self):
        output = '''
        {
            "intent_type": "multiple",
            "intents": [
                {"intent": "agent_1"},
                {"intent": "agent_2"}
            ]
        }
        '''
        target = "agent_1"
        
        # Scenario: for multiple, maybe check first one
        field = "py: data['intents'][0]['intent'] if data.get('intent_type') == 'multiple' else data['intent']"
        self.assertTrue(self.tm._check_match(output, target, field))

    def test_expression_custom_return_bool(self):
         output = '{"intent_type": "single", "intent": "agent_id_name", "confidence": 0.95}'
         # Scenario: check directly in python
         field = "py: data.get('intent') == 'agent_id_name'"
         # Target doesn't matter if expression returns bool
         self.assertTrue(self.tm._check_match(output, "ignored", field))

    def test_expression_error_handling(self):
        output = '{"a": 1}'
        # Invalid python syntax
        field = "py: 1 / 0"
        self.assertFalse(self.tm._check_match(output, "1", field))
        
        # Key error
        field = "py: data['missing_key']"
        self.assertFalse(self.tm._check_match(output, "1", field))

if __name__ == '__main__':
    unittest.main()
