
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
        """
        执行自定义Python提取代码。

        支持JSON和非JSON内容的提取。脚本可使用以下变量：
        - output: 原始文本内容（始终可用）
        - data: 解析后的JSON对象（非JSON时为空字典）
        - lines: 按行分割的列表（方便逐行解析）
        - is_json: 布尔值，指示内容是否为JSON
        - result: 脚本应将提取结果赋值给此变量

        :param code: 要执行的Python代码字符串
        :param raw_output: 原始输出文本
        :param json_data: 解析后的JSON数据（如果是JSON格式）
        :param is_json: 是否为JSON格式
        :return: 提取的结果值，失败时返回None
        """
        try:
            # 预处理：按行分割原始输出，方便逐行解析
            lines: list[str] = raw_output.strip().split('\n') if raw_output else []
            
            local_scope: dict[str, Any] = {
                "data": json_data if is_json else {},
                "output": raw_output,
                "raw_output": raw_output,  # 别名，保持兼容性
                "lines": lines,
                "is_json": is_json,
                "result": None
            }
            
            # 如果是JSON字典，自动解包第一层键作为变量（方便访问）
            if is_json and isinstance(json_data, dict):
                safe_data: dict[str, Any] = {
                    k: v for k, v in json_data.items() 
                    if k not in local_scope and isinstance(k, str)
                }
                local_scope.update(safe_data)
            
            # 提供有限的安全内置函数
            safe_builtins: dict[str, Any] = {
                "len": len,
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
                "list": list,
                "dict": dict,
                "tuple": tuple,
                "set": set,
                "range": range,
                "enumerate": enumerate,
                "zip": zip,
                "map": map,
                "filter": filter,
                "sorted": sorted,
                "reversed": reversed,
                "min": min,
                "max": max,
                "sum": sum,
                "abs": abs,
                "round": round,
                "isinstance": isinstance,
                "type": type,
                "None": None,
                "True": True,
                "False": False,
                "print": print,  # 支持调试输出
            }
                
            exec(code, {"__builtins__": safe_builtins}, local_scope)
            return local_scope.get("result")
        except Exception as e:
            logger.warning(f"自定义提取脚本执行失败: {e}, 代码: {code[:100]}...")
            return None
