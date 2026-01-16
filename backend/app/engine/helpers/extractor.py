
"""
Result Extraction Helper

Unified logic for extracting values from model outputs (JSON or string).
Supports:
1. JSON parsing
2. Direct field extraction
3. Custom Python code execution (prefix 'py:')
"""
import json
from typing import Any, Dict, Optional
from loguru import logger

class ResultExtractor:
    @staticmethod
    def extract(content: str, rule: Optional[str] = None) -> Any:
        """
        Extract data from content based on the rule.

        :param content: Raw output string (usually JSON).
        :param rule: Extraction rule.
                     - If starts with 'py:', executes as Python script.
                     - If simple string, extracts as JSON field.
                     - If None, returns the parsed JSON dict (or raw string if not JSON).
        :return: Extracted value. If extraction fails, may return None or raise error depending on context?
                 Current design: returns None on failure, or the raw/parsed data if no rule.
        """
        if not content:
            return None
            
        content = content.strip()
        data = None
        is_json = False
        
        # 1. Try Parse JSON
        if content.startswith("{"):
            try:
                data = json.loads(content)
                is_json = True
            except json.JSONDecodeError:
                pass
        
        # If not JSON, wrapped in simple dict for consistency in python exec
        if not is_json:
            # If strictly expecting JSON but got text, accessing 'data' in script might be weird.
            # But let's follow local_scope pattern.
            pass

        # 2. No Rule -> Return parsed data or raw content
        if not rule:
            return data if is_json else content
            
        # 3. Python Script Rule
        if rule.startswith("py:"):
            return ResultExtractor._execute_python(rule[3:].strip(), content, data, is_json)
            
        # 4. Simple Field Extraction
        if is_json and isinstance(data, dict):
            return data.get(rule)
            
        return None

    @staticmethod
    def _execute_python(code: str, raw_output: str, json_data: Any, is_json: bool) -> Any:
        """Execute custom python extraction code."""
        try:
            local_scope = {
                "data": json_data if is_json else {},
                "output": raw_output,
                "result": None
            }
            
            # Auto-unpack first-level keys for convenience if it's a dict
            if is_json and isinstance(json_data, dict):
                safe_data = {k: v for k, v in json_data.items() 
                           if k not in local_scope and isinstance(k, str)}
                local_scope.update(safe_data)
                
            exec(code, {"__builtins__": None}, local_scope)
            return local_scope.get("result")
        except Exception as e:
            logger.warning(f"Custom extraction script failed: {e}")
            return None
