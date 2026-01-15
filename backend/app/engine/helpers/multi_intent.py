"""多意图优化模块 - 处理多意图拆分、优化和合并"""
from loguru import logger
import asyncio
import json
import re
from typing import Dict, Any, List, Optional, Callable
from app.core.prompts import PROMPT_SPLIT_INTENT, PROMPT_MERGE_INTENTS


class MultiIntentOptimizer:
    """
    多意图优化器
    
    实现 Split-Optimize-Merge 流程：
    1. 将提示词按意图拆分为子提示词
    2. 分别优化各个子提示词
    3. 合并优化后的子提示词
    """
    
    def __init__(
        self, 
        llm_helper=None,
        optimizer_callback: Optional[Callable] = None
    ):
        """
        初始化多意图优化器
        
        :param llm_helper: LLM 辅助类实例
        :param optimizer_callback: 单意图优化回调函数（用于递归调用主优化器）
        """
        self.llm_helper = llm_helper
        self.optimizer_callback = optimizer_callback
    
    def set_optimizer_callback(self, callback: Callable) -> None:
        """
        设置优化回调函数
        
        :param callback: 优化回调函数
        """
        self.optimizer_callback = callback
    
    async def optimize_multi_intent_flow(
        self,
        prompt: str,
        errors: List[Dict[str, Any]],
        dataset: List[Dict[str, Any]],
        diagnosis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行多意图优化流程（Split-Optimize-Merge）
        
        :param prompt: 原始提示词
        :param errors: 错误样例列表
        :param dataset: 完整数据集
        :param diagnosis: 诊断分析结果
        :return: 优化结果字典
        """
        logger.info("=== 进入多意图优化流程 ===")
        
        # 1. 获取意图列表
        intent_analysis: Dict[str, Any] = diagnosis.get("intent_analysis", {})
        # 从错误分布中获取所有出现过的意图
        all_intents: List[str] = list(
            intent_analysis.get("error_rate_by_intent", {}).keys()
        )
        
        if not all_intents:
            logger.warning("未识别到明确意图，回退到普通优化流程")
            return {
                "optimized_prompt": prompt,
                "diagnosis": diagnosis,
                "message": "无法识别意图，跳过多意图优化"
            }

        logger.info(f"识别到的意图列表: {all_intents}")
        
        # 2. 拆分 Prompt
        logger.info("Step 1: 拆分 Prompt 为子意图 Prompt...")
        sub_prompts: List[Dict] = await self._split_prompt_by_intents(
            prompt, all_intents
        )
        
        if not sub_prompts:
            logger.error("各意图 Prompt 拆分失败，放弃多意图优化")
            return {"optimized_prompt": prompt, "message": "Prompt 拆分失败"}
             
        # 3. 独立优化每个子 Prompt
        logger.info(f"Step 2: 并行优化 {len(sub_prompts)} 个子意图...")
        optimized_sub_prompts: List[Dict] = []
        
        # 准备任务
        tasks: List = []
        for item in sub_prompts:
            intent: str = item["intent"]
            sub_p: str = item["sub_prompt"]
            
            # 筛选该意图相关的 errors
            intent_errors: List[Dict] = [
                e for e in errors if str(e.get("target")) == intent
            ]
            
            if not intent_errors:
                logger.info(
                    f"意图 '{intent}' 无错误样例，跳过优化，保留原样"
                )
                optimized_sub_prompts.append(item)
                continue
                
            logger.info(
                f"意图 '{intent}' 关联 {len(intent_errors)} 个错误，准备优化..."
            )
            
            tasks.append(
                self._optimize_sub_intent(intent, sub_p, intent_errors, dataset)
            )

        results = await asyncio.gather(*tasks)
        
        # 收集结果
        task_result_map: Dict[str, Dict] = {
            res["intent"]: res for res in results
        }
        
        final_sub_prompts_map: List[Dict] = []
        for item in sub_prompts:
            intent: str = item["intent"]
            if intent in task_result_map:
                res = task_result_map[intent]
                final_sub_prompts_map.append({
                    "intent": intent,
                    "sub_prompt": res["optimized_prompt"]
                })
            else:
                # 没优化的（无错误样例）
                final_sub_prompts_map.append(item)
                
        # 4. 合并 Prompt
        logger.info("Step 3: 合并优化后的子 Prompt...")
        merged_prompt: str = await self._merge_sub_prompts(
            prompt, final_sub_prompts_map
        )
        
        return {
            "optimized_prompt": merged_prompt,
            "diagnosis": diagnosis,
            "intent_analysis": intent_analysis,
            "applied_strategies": [
                {"name": "multi_intent_split_merge", "success": True}
            ],
            "best_strategy": "multi_intent_recursion",
            "message": "多意图优化完成"
        }

    async def _optimize_sub_intent(
        self, 
        intent: str, 
        prompt: str, 
        errors: List[Dict], 
        dataset: List[Dict]
    ) -> Dict[str, Any]:
        """
        优化单个意图的子提示词
        
        :param intent: 意图名称
        :param prompt: 子提示词
        :param errors: 该意图的错误样例
        :param dataset: 完整数据集
        :return: 优化结果字典
        """
        try:
            if self.optimizer_callback:
                # 使用回调函数进行优化（防止递归死循环）
                res = await self.optimizer_callback(
                    prompt=prompt,
                    errors=errors,
                    dataset=dataset,
                    strategy_mode="precision_focus",
                    max_strategies=1
                )
                return {
                    "intent": intent,
                    "optimized_prompt": res["optimized_prompt"]
                }
            else:
                # 如果没有回调，返回原始提示词
                logger.warning(
                    f"未设置优化回调，意图 '{intent}' 保持原样"
                )
                return {
                    "intent": intent,
                    "optimized_prompt": prompt
                }
        except Exception as e:
            logger.error(f"优化子意图 '{intent}' 失败: {e}")
            return {
                "intent": intent,
                "optimized_prompt": prompt  # 回退
            }

    async def _split_prompt_by_intents(
        self, 
        prompt: str, 
        intents: List[str]
    ) -> List[Dict]:
        """
        使用 LLM 将提示词拆分为多个子意图提示词
        
        :param prompt: 原始提示词
        :param intents: 意图列表
        :return: 子提示词列表
        """
        try:
            input_text: str = PROMPT_SPLIT_INTENT.replace(
                "{original_prompt}", prompt
            ).replace(
                "{intent_list}", json.dumps(intents, ensure_ascii=False)
            ).replace(
                "{count}", str(len(intents))
            )
                
            response: str = await self.llm_helper.call_llm_async(input_text)
            
            # 解析 JSON
            result: List = self._parse_json_response(response)
            
            if isinstance(result, list):
                return result
            return []
            
        except Exception as e:
            logger.error(f"拆分 Prompt 失败: {e}")
            return []

    async def _merge_sub_prompts(
        self, 
        original_prompt: str, 
        sub_prompts: List[Dict]
    ) -> str:
        """
        使用 LLM 合并多个子提示词
        
        :param original_prompt: 原始提示词（用于回退）
        :param sub_prompts: 子提示词列表
        :return: 合并后的提示词
        """
        try:
            input_text: str = PROMPT_MERGE_INTENTS.replace(
                "{sub_prompts_json}", 
                json.dumps(sub_prompts, ensure_ascii=False)
            )
            
            response: str = await self.llm_helper.call_llm_async(input_text)
            
            # 清理可能的 markdown 标记
            clean_res: str = re.sub(r'^```markdown\s*', '', response)
            clean_res = re.sub(r'^```\s*', '', clean_res)
            clean_res = re.sub(r'\s*```$', '', clean_res)
            
            return clean_res.strip()
            
        except Exception as e:
            logger.error(f"合并 Prompt 失败: {e}")
            return original_prompt
    
    def _parse_json_response(self, response: str) -> Any:
        """
        解析 LLM 响应中的 JSON 内容
        
        :param response: LLM 响应内容
        :return: 解析后的对象
        """
        # 尝试提取 json 代码块
        match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
        if match:
            json_str: str = match.group(1)
        else:
            json_str = response
        
        return json.loads(json_str)
