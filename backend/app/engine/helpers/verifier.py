"""
验证器模块 - 封装单条数据的验证逻辑

统一 TaskService (任务执行) 和 PromptEvaluator (优化评估) 的验证行为
"""
from loguru import logger
import json
import re
from typing import Dict, Any, Optional
from app.core.llm_factory import LLMFactory

class Verifier:
    """
    通用验证器
    """
    
    @staticmethod
    def verify_single(
        index: int,
        query: str,
        target: str,
        prompt: str,
        model_config: Dict[str, Any],
        extract_field: Optional[str] = None,
        reason_col_value: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        验证单条数据
        
        :param index: 数据行索引
        :param query: 用户输入
        :param target: 预期输出
        :param prompt: 提示词
        :param model_config: 模型/验证配置
        :param extract_field: 提取字段 (可选)
        :param reason_col_value: 原因列的值 (可选)
        :return: 验证结果字典
        """
        try:
            mode = model_config.get("validation_mode", "llm")
            output = ""
            
            if mode == "interface":
                output = Verifier._call_interface(query, target, prompt, model_config)
            else:
                output = Verifier._call_llm(query, prompt, model_config)
                
            # 自动去除 markdown 代码块标记
            output = Verifier._clean_markdown(output)
            
            is_correct = Verifier.check_match(output, target, extract_field)
            
            return {
                "index": index,
                "query": query,
                "target": target,
                "reason": reason_col_value or "",
                "output": output,
                "is_correct": is_correct
            }
            
        except Exception as e:
            logger.error(f"[Verifier] Error index={index}: {str(e)}")
            return {
                "index": index,
                "query": query,
                "target": target,
                "reason": reason_col_value or "",
                "output": f"ERROR: {str(e)}",
                "is_correct": False
            }

    @staticmethod
    def _call_interface(query: str, target: str, prompt: str, config: Dict[str, Any]) -> str:
        """调用自定义接口"""
        import requests
        
        interface_code = config.get("interface_code", "")
        base_url = config.get("base_url", "")
        api_key = config.get("api_key", "")
        timeout = int(config.get("timeout", 60))
        
        if not base_url:
            raise ValueError("Interface URL is required")
            
        # 准备执行环境
        local_scope = {
            "query": query, 
            "target": target,
            "prompt": prompt,
            "params": None
        }
        
        # 执行参数转换脚本
        try:
            exec(interface_code, {"__builtins__": None}, local_scope)
            params = local_scope.get("params")
        except Exception as e:
            raise ValueError(f"Python script execution failed: {e}")
            
        if not isinstance(params, dict):
            raise ValueError("Script must assign a dict to 'params' variable")
            
        # 发起请求
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
            headers["api-key"] = api_key 
        
        resp = requests.post(base_url, json=params, headers=headers, timeout=timeout)
        resp.raise_for_status()
        
        # 获取输出
        try:
            return json.dumps(resp.json(), ensure_ascii=False)
        except:
            return resp.text

    @staticmethod
    def _call_llm(query: str, prompt: str, config: Dict[str, Any], client=None) -> str:
        """调用 LLM"""
        # 如果未提供 client，则临时创建一个 (这里主要是为了 TaskService 的逻辑保持一致，
        # 但要注意性能。TaskService 是传入 task_client 的。
        # 为了更好地复用，我们这里最好只处理 1次性调用，或者允许传入 client)
        
        # 修正：为了简单和复用，我们这里先每次创建 client (如果 LLMFactory 有缓存则更好，但它是轻量级的)
        # 实际上 TaskService 是复用 client 的。
        # 为了兼容，我们这里允许传入 client，如果没传则创建。
        
        if client is None:
            client = LLMFactory.create_client(config)
            
        response = client.chat.completions.create(
            model=config.get("model_name", "gpt-3.5-turbo"),
            messages=[
                {"role": "user", "content": prompt},
                {"role": "user", "content": query}
            ],
            temperature=float(config.get("temperature", 0)),
            max_tokens=int(config.get("max_tokens", 2000)),
            timeout=int(config.get("timeout", 60))
        )
        return response.choices[0].message.content

    @staticmethod
    def _clean_markdown(text: str) -> str:
        """去除 Markdown 代码块标记"""
        if "```" in text:
            match = re.search(r"```(?:\w+)?\s*(.*?)\s*```", text, re.DOTALL)
            if match:
                return match.group(1).strip()
            # 尝试简单去除
            return text.replace("```json", "").replace("```", "").strip()
        return text

    @staticmethod
    def check_match(output: str, target: str, extract_field: Optional[str] = None) -> bool:
        """检查结果是否匹配"""
        from .extractor import ResultExtractor
        
        output = output.strip()
        target = target.strip()
        
        # 使用统一提取器
        extracted_val = ResultExtractor.extract(output, extract_field)
        
        # 调试日志
        # logger.debug(f"[Verifier] check_match - target: '{target}', extract_field: '{extract_field}', extracted_val: '{extracted_val}', output[:100]: '{output[:100]}'")
        
        # 1. 提取到具体值的情况
        if extracted_val is not None:
            # 如果提取结果是字典（说明 extract_field 为空或无效），需要遍历值
            if isinstance(extracted_val, dict):
                 for val in extracted_val.values():
                    if str(val) == target:
                        return True
            else:
                # 提取到了具体值（布尔或字符串等）
                if isinstance(extracted_val, bool):
                    return extracted_val
                result = str(extracted_val) == target
                logger.debug(f"[Verifier] Extracted comparison: '{str(extracted_val)}' == '{target}' => {result}")
                return result
        
        # 2. 兜底逻辑：直接匹配字符串
        if target == output:
            return True
            
        return target in output
