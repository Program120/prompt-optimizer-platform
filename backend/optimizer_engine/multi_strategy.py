"""多策略优化器 - 主逻辑"""
import logging
import asyncio
from typing import List, Dict, Any, Optional
from .diagnosis import diagnose_prompt_performance
from .strategy_matcher import StrategyMatcher
from .prompt_rewriter import PromptRewriter
from .fewshot_selector import FewShotSelector

class MultiStrategyOptimizer:
    """多策略优化器 - 协调多种策略进行提示词优化"""
    
    def __init__(
        self, 
        llm_client=None, 
        model_config: Dict[str, Any] = None
    ):
        self.llm_client = llm_client
        self.model_config = model_config or {}
        self.matcher = StrategyMatcher(llm_client, model_config)
        self.rewriter = PromptRewriter()
        self.selector = FewShotSelector()
        self.logger = logging.getLogger(__name__)
    
    async def optimize(
        self,
        prompt: str,
        errors: List[Dict[str, Any]],
        dataset: List[Dict[str, Any]] = None,
        total_count: int = None,
        strategy_mode: str = "auto",
        max_strategies: int = 3
    ) -> Dict[str, Any]:
        """
        执行多策略优化 (五阶段工作流)
        
        1. 诊断分析
        2. 策略匹配
        3. 并行优化(候选生成)
        4. 快速筛选
        5. 精细评估
        """
        if not errors:
            return {"optimized_prompt": prompt, "message": "无错误样例，无需优化"}
            
        dataset = dataset or errors  # 如果没有提供数据集，使用错误集作为数据源
        
        # 阶段1：诊断分析
        self.logger.info(f"Step 1: 诊断分析... (Errors: {len(errors)})")
        loop = asyncio.get_running_loop()
        diagnosis = await loop.run_in_executor(
            None,
            lambda: diagnose_prompt_performance(
                prompt, 
                errors, 
                total_count,
                llm_client=self.llm_client,
                model_config=self.model_config
            )
        )
        
        # 阶段2：策略匹配
        self.logger.info("Step 2: 策略匹配...")
        strategies = self.matcher.match_strategies(diagnosis, max_strategies)
        if hasattr(self.matcher, 'get_preset_strategies') and strategy_mode != 'auto':
             strategies = self.matcher.get_preset_strategies(strategy_mode)[:max_strategies]
             
        if not strategies:
             return {"optimized_prompt": prompt, "diagnosis": diagnosis, "message": "无匹配策略"}

        # 阶段3：候选生成 (并行优化)
        self.logger.info(f"Step 3: 候选生成... (Strategies: {len(strategies)})")
        candidates = await self._generate_candidates(prompt, strategies, errors, diagnosis, dataset)
        
        # 阶段4：快速筛选
        self.logger.info(f"Step 4: 快速筛选... (Candidates: {len(candidates)})")
        filtered_candidates = await self._rapid_evaluation(candidates, errors[:5]) # 使用前5个错误做快速验证
        
        # 阶段5：精细评估 (选择最佳)
        self.logger.info("Step 5: 选择最佳方案...")
        best_result = self._select_best_candidate(filtered_candidates, prompt)
        
        return {
            "optimized_prompt": best_result["prompt"],
            "diagnosis": diagnosis,
            "applied_strategies": [{"name": c["strategy"], "success": True} for c in filtered_candidates],
            "best_strategy": best_result["strategy"],
            "improvement": best_result.get("score", 0),
            "candidates": [
                {"strategy": c["strategy"], "score": c.get("score", 0)} 
                for c in filtered_candidates
            ]
        }
        
    async def _generate_candidates(
        self, 
        prompt: str, 
        strategies: List[Any], 
        errors: List[Dict], 
        diagnosis: Dict,
        dataset: List[Dict]
    ) -> List[Dict[str, Any]]:
        """生成优化候选集"""
        candidates = []
        
        # 并行执行策略应用 (这里简化为循环，实际可用 asyncio.gather)
        # 考虑到某些策略应用主要耗时在 LLM 调用，可以用 asyncio
        tasks = []
        for strategy in strategies:
            tasks.append(self._apply_strategy_wrapper(strategy, prompt, errors, diagnosis, dataset))
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for res in results:
            if isinstance(res, dict) and res.get("prompt"):
                candidates.append(res)
            elif isinstance(res, Exception):
                self.logger.error(f"Strategy execution failed: {res}")
                
        return candidates

    async def _apply_strategy_wrapper(self, strategy, prompt, errors, diagnosis, dataset):
        """包装策略执行逻辑"""
        try:
            # 策略应用可能涉及 LLM 调用，也可能涉及 Rewriter/Selector
            # 为了兼容现有 Strategy 类，我们先尝试调用其 apply 方法
            # 同时注入 rewriter/selector 的能力（如果 Strategy 支持）
            
            # 这里做一个扩展：如果 Strategy 是 DifficultExampleInjectionStrategy，我们使用 Selector
            if strategy.name == "difficult_example_injection":
                # 使用 Selector 选择困难案例
                hard_cases = self.selector.select(dataset, "difficulty", n=3)
                # 更新 diagnosis 里的 info 以便 strategy 使用，或者直接构造 prompt
                # 为了保持接口兼容，我们这里还是调用 strategy.apply
                # 但我们可以通过 modifying diagnosis 这里的 diagnosis 是引用，可能这会影响其他并发的策略？
                # 最好 copy 一份 diagnosis，但为了简单暂不深究，因为 strategy 通常只读 diagnosis
                # 或者只为该 strategy 创建特定的 context
                diagnosis_copy = diagnosis.copy()
                diagnosis_copy["error_patterns"] = diagnosis.get("error_patterns", {}).copy()
                diagnosis_copy["error_patterns"]["hard_cases"] = hard_cases
                diagnosis = diagnosis_copy
            
            loop = asyncio.get_running_loop()
            new_prompt = await loop.run_in_executor(
                None,
                lambda: strategy.apply(prompt, errors, diagnosis)
            )
            
            # 使用 Rewriter 进行后处理 (可选)
            # 例如统一添加 CoT
            # new_prompt = self.rewriter.rewrite(new_prompt, "add_cot") 
            
            return {
                "strategy": strategy.name,
                "prompt": new_prompt,
                "original_prompt": prompt
            }
        except Exception as e:
            self.logger.error(f"Error applying strategy {strategy.name}: {e}")
            raise e

    async def _rapid_evaluation(
        self, 
        candidates: List[Dict], 
        validation_set: List[Dict]
    ) -> List[Dict]:
        """快速评估候选效果"""
        if not validation_set:
            return candidates
            
        evaluated = []
        for cand in candidates:
            score = await self._evaluate_prompt(cand["prompt"], validation_set)
            cand["score"] = score
            evaluated.append(cand)
            
        # 按分数排序
        evaluated.sort(key=lambda x: x["score"], reverse=True)
        return evaluated
        
    async def _evaluate_prompt(self, prompt: str, test_cases: List[Dict]) -> float:
        """评估 Prompt 在测试集上的表现 (0-1)"""
        # 这里需要调用 LLM 运行推理
        # 简单实现：调用 LLM 对每个 case 预测，比较 output
        if not self.llm_client:
            return 0.5
            
        correct = 0
        total = len(test_cases)
        
        # 限制并发
        sem = asyncio.Semaphore(5)
        
        async def run_case(case):
            async with sem:
                try:
                    query = case.get('query', '')
                    target = case.get('target', '')
                    
                    # 构建简单的推理 prompt
                    eval_input = prompt.replace("{{input}}", query).replace("{{context}}", "")
                    # 如果没有替换变量，直接拼接
                    if eval_input == prompt:
                        eval_input = f"{prompt}\n\nInput: {query}"
                        
                    response = await self._call_llm_async(eval_input)
                    
                    # 简单匹配：只要包含目标值就算对 (模糊匹配)
                    if str(target).lower() in response.lower():
                        return 1
                    return 0
                except:
                    return 0

        tasks = [run_case(case) for case in test_cases]
        results = await asyncio.gather(*tasks)
        
        return sum(results) / total if total > 0 else 0

    def _select_best_candidate(self, candidates: List[Dict], original_prompt: str) -> Dict:
        """选择最佳候选"""
        if not candidates:
            return {"prompt": original_prompt, "strategy": "none", "score": 0}
            
        best = candidates[0]
        # 如果最佳的分数还不如原始的好? (这里没测原始的，假设优化总比不优化好，或者设置阈值)
        return best

    async def _call_llm_async(self, prompt: str) -> str:
        """异步调用 LLM"""
        # 适配同步的 llm_client 到异步
        # 假设 llm_client 是 openai 风格但同步的，或者支持 async
        # 这里为了保险，用 run_in_executor
        import functools
        loop = asyncio.get_event_loop()
        
        def run_sync():
            try:
                response = self.llm_client.chat.completions.create(
                    model=self.model_config.get("model_name", "gpt-3.5-turbo"),
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0,
                    max_tokens=500
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                self.logger.error(f"LLM call failed: {e}")
                return ""
                
        return await loop.run_in_executor(None, run_sync)

    def diagnose(
        self, 
        prompt: str, 
        errors: List[Dict[str, Any]],
        total_count: int = None
    ) -> Dict[str, Any]:
        """仅执行诊断分析"""
        return diagnose_prompt_performance(
            prompt, 
            errors, 
            total_count,
            llm_client=self.llm_client,
            model_config=self.model_config
        )
