"""提示词验证模块 - 验证优化后的提示词质量"""
from loguru import logger
import json
import re
from typing import Dict, Any, List, Optional, Callable
from app.core.prompts import PROMPT_VALIDATE_OPTIMIZATION


class PromptValidator:
    """
    提示词验证器
    
    通过 LLM 对比原始提示词与优化后提示词，检测是否存在：
    - 格式破坏（截断、乱码、语法错误）
    - 核心意图丢失
    - 模板变量丢失
    - 严重语义偏离
    - 无意义重复内容
    """
    
    def __init__(self, llm_helper=None):
        """
        初始化提示词验证器
        
        :param llm_helper: LLM 辅助类实例
        """
        self.llm_helper = llm_helper
    
    async def validate_optimized_prompt(
        self,
        original_prompt: str,
        optimized_prompt: str,
        should_stop: Optional[Callable[[], bool]] = None
    ) -> Dict[str, Any]:
        """
        验证优化后的提示词是否存在异常
        
        :param original_prompt: 原始提示词
        :param optimized_prompt: 优化后的提示词
        :param should_stop: 停止回调函数
        :return: 验证结果字典，包含 is_valid, issues, severity, failure_reason
        """
        logger.info("验证优化后的提示词...")
        
        # 如果优化后的提示词与原始提示词相同，则无需验证
        if original_prompt == optimized_prompt:
            logger.info("优化后的提示词与原始提示词相同，跳过验证")
            return {
                "is_valid": True,
                "issues": [],
                "severity": "none",
                "failure_reason": ""
            }
        
        # 构造验证请求
        validation_input: str = PROMPT_VALIDATE_OPTIMIZATION.replace(
            "{original_prompt}", original_prompt
        ).replace(
            "{optimized_prompt}", optimized_prompt
        )
        
        try:
            # 调用 LLM 进行验证
            response: str = await self.llm_helper.call_llm_with_cancellation(
                validation_input,
                should_stop=should_stop,
                task_name="提示词验证"
            )

            
            if not response:
                logger.warning("验证 LLM 返回为空，默认通过验证")
                return {
                    "is_valid": True,
                    "issues": [],
                    "severity": "none",
                    "failure_reason": ""
                }
            
            # 解析 JSON 响应
            result: Dict[str, Any] = self._parse_validation_response(response)
            
            is_valid: bool = result.get("is_valid", True)
            issues: List[str] = result.get("issues", [])
            severity: str = result.get("severity", "none")
            
            logger.info(f"验证结果: is_valid={is_valid}, severity={severity}")
            if issues:
                logger.warning(f"检测到的问题: {issues}")
            
            # 如果严重程度为 "high"，则标记为验证失败
            if severity == "high":
                failure_reason: str = "优化失败, 模型输出格式异常"
                if issues:
                    failure_reason += f" (详情: {'; '.join(issues[:2])})"
                return {
                    "is_valid": False,
                    "issues": issues,
                    "severity": severity,
                    "failure_reason": failure_reason
                }
            
            return {
                "is_valid": True,
                "issues": issues,
                "severity": severity,
                "failure_reason": ""
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"验证响应 JSON 解析失败: {e}")
            # JSON 解析失败时，默认通过验证（避免误杀）
            return {
                "is_valid": True,
                "issues": ["验证响应格式异常"],
                "severity": "low",
                "failure_reason": ""
            }
        except Exception as e:
            logger.error(f"验证过程发生错误: {e}")
            # 其他错误时，默认通过验证
            return {
                "is_valid": True,
                "issues": [f"验证出错: {str(e)}"],
                "severity": "low",
                "failure_reason": ""
            }
    
    def _parse_validation_response(self, response: str) -> Dict[str, Any]:
        """
        解析验证响应的 JSON 内容
        
        :param response: LLM 响应内容
        :return: 解析后的字典
        """
        # 尝试提取 json 代码块
        match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
        if match:
            json_str: str = match.group(1)
        else:
            json_str = response
        
        return json.loads(json_str)
