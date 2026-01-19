"""
困难案例注入策略 - 将困难案例注入到 Few-Shot 示例中

基于 text2vec 向量化评估样本难区分程度，智能管理 Few-Shot 样本的注入、
配额限制和低分样本替换。

核心功能：
1. 使用向量相似度计算样本难度评分
2. 按意图分组控制样本数量：
   - 普通单意图: 不超过该意图在数据集中对应数量的 10%
   - 澄清意图: 不超过数据集总数的 10%
   - 多意图: 不超过数据集总数的 10%
3. 达到配额时自动替换低分样本
"""
import json
from loguru import logger
from typing import List, Dict, Any, Optional, Tuple
from .base import BaseStrategy
from ..helpers.fewshot_sample_manager import FewShotSampleManager


class DifficultExampleInjectionStrategy(BaseStrategy):
    """
    困难案例注入策略
    
    将难区分的困难案例作为 Few-Shot 示例注入提示词，
    使用向量化评分和配额管理确保示例质量和数量可控。
    """
    
    name: str = "difficult_example_injection"
    priority: int = 70
    description: str = "困难案例注入策略：将难处理的案例作为示例注入提示词"
    module_name: str = "Few-Shot 场景示例"
    
    def is_applicable(self, diagnosis: Dict[str, Any]) -> bool:
        """
        当存在较多困难案例时适用
        
        :param diagnosis: 诊断结果
        :return: 是否适用
        """
        hard_cases: List[Dict[str, Any]] = diagnosis.get("error_patterns", {}).get("hard_cases", [])
        return len(hard_cases) >= 5
    
    def get_priority(self, diagnosis: Dict[str, Any]) -> int:
        """
        困难案例越多，优先级越高
        
        :param diagnosis: 诊断结果
        :return: 优先级数值
        """
        hard_cases: List[Dict[str, Any]] = diagnosis.get("error_patterns", {}).get("hard_cases", [])
        if len(hard_cases) >= 10:
            return int(self.priority * 1.3)
        elif len(hard_cases) >= 5:
            return int(self.priority * 1.1)
        return self.priority
    
    def apply(
        self, 
        prompt: str, 
        errors: List[Dict[str, Any]], 
        diagnosis: Dict[str, Any]
    ) -> str:
        """
        应用困难案例注入策略
        
        主要流程：
        1. 获取困难案例和数据集统计信息
        2. 使用 FewShotSampleManager 对案例进行评分
        3. 仅将高分（≥7）样本尝试注入，自动处理配额和替换
        4. 获取最终注入样本并构建优化指令
        
        :param prompt: 当前提示词
        :param errors: 错误样例列表
        :param diagnosis: 诊断分析结果
        :return: 优化后的提示词
        """
        logger.info(f"策略 {self.name} 开始执行...")
        
        # 获取项目 ID 和文件 ID
        project_id: str = diagnosis.get("project_id", "")
        file_id: str = diagnosis.get("file_id", "")
        
        # 获取数据集统计信息
        total_count: int = diagnosis.get("overall_metrics", {}).get("total_count", 100)
        
        # 获取困难案例
        hard_cases: List[Dict[str, Any]] = diagnosis.get("error_patterns", {}).get("hard_cases", [])
        if not hard_cases:
            # 如果没有识别到 hard_cases，使用前 10 个错误
            hard_cases = errors[:10]
        
        logger.info(f"[{self.name}] 困难案例数: {len(hard_cases)}, 总样本数: {total_count}")
        
        # 初始化样本管理器
        sample_manager: FewShotSampleManager = FewShotSampleManager(project_id, file_id)
        
        # 统计各意图的样本数量
        intent_sample_counts: Dict[str, int] = self._count_samples_by_intent(errors, total_count)
        
        # 获取当前 Few-Shot 样本
        current_fewshot_samples: List[Dict[str, Any]] = self._get_current_fewshot_samples(
            project_id, file_id
        )
        
        # 批量计算难度评分
        # 使用 errors 作为参考样本（全集），hard_cases 作为目标样本
        difficulty_scores: List[float] = sample_manager.batch_calculate_difficulty_scores(
            hard_cases, errors
        )
        
        # 对困难案例进行处理并尝试添加
        selected_samples: List[Dict[str, Any]] = []
        replaced_samples: List[Dict[str, Any]] = []
        
        for i, case in enumerate(hard_cases):
            # 获取对应的难度评分
            difficulty_score: float = difficulty_scores[i]
            
            # 更新案例的难度评分
            case_with_score: Dict[str, Any] = case.copy()
            case_with_score["difficulty_score"] = difficulty_score
            
            # 尝试添加为 Few-Shot 样本
            added, replaced = sample_manager.add_fewshot_sample(
                case_with_score,
                difficulty_score,
                intent_sample_counts,
                total_count,
                current_fewshot_samples
            )
            
            if added:
                selected_samples.append(case_with_score)
                # 更新当前 Few-Shot 样本列表
                if replaced:
                    replaced_samples.append(replaced)
                    current_fewshot_samples = [
                        s for s in current_fewshot_samples 
                        if s.get("query") != replaced.get("query")
                    ]
                current_fewshot_samples.append(case_with_score)
                
                # 持久化到 IntentIntervention 表
                self._save_fewshot_sample(project_id, file_id, case_with_score)
        
        # 处理被替换的样本
        for replaced in replaced_samples:
            self._unmark_fewshot_sample(project_id, file_id, replaced)
        
        logger.info(
            f"[{self.name}] 样本评分完成: "
            f"新增={len(selected_samples)}, 替换={len(replaced_samples)}"
        )
        
        # 获取最终用于注入的样本（按分数排序，每个意图最多 3 个）
        injection_samples: List[Dict[str, Any]] = sample_manager.get_fewshot_samples_for_injection(
            current_fewshot_samples, max_per_intent=3
        )
        
        # 构建优化指令
        hard_cases_text: str = self._build_hard_cases_text(injection_samples[:5])
        example_cases_text: str = self._build_example_cases_from_errors(injection_samples[:3])
        
        optimization_instruction: str = self._build_optimization_instruction(
            hard_cases_text, example_cases_text
        )
        
        # 使用通用元优化方法
        return self._meta_optimize(
            prompt, injection_samples, optimization_instruction, 
            conservative=True, diagnosis=diagnosis,
            module_name=self.module_name
        )
    
    def _count_samples_by_intent(
        self, 
        errors: List[Dict[str, Any]], 
        total_count: int
    ) -> Dict[str, int]:
        """
        统计各意图的样本数量
        
        :param errors: 错误样本列表
        :param total_count: 总样本数
        :return: 各意图的样本数量
        """
        intent_counts: Dict[str, int] = {}
        
        for err in errors:
            intent: str = str(err.get("target", "unknown"))
            intent_counts[intent] = intent_counts.get(intent, 0) + 1
        
        # 估算所有样本的意图分布（基于错误样本推算）
        if errors and total_count > len(errors):
            ratio: float = total_count / len(errors)
            intent_counts = {k: int(v * ratio) for k, v in intent_counts.items()}
        
        return intent_counts
    
    def _get_current_fewshot_samples(
        self, 
        project_id: str, 
        file_id: str
    ) -> List[Dict[str, Any]]:
        """
        获取当前项目的 Few-Shot 样本
        
        :param project_id: 项目 ID
        :param file_id: 文件 ID
        :return: Few-Shot 样本列表
        """
        if not project_id:
            return []
        
        try:
            from app.services import intervention_service
            
            # 获取所有标记为 Few-Shot 的干预记录
            interventions = intervention_service.get_interventions_by_project(
                project_id, file_id
            )
            
            fewshot_samples: List[Dict[str, Any]] = []
            for intervention in interventions:
                if getattr(intervention, 'is_fewshot_sample', False):
                    fewshot_samples.append({
                        "query": intervention.query,
                        "target": intervention.target,
                        "reason": intervention.reason,
                        "difficulty_score": getattr(intervention, 'difficulty_score', 0.0)
                    })
            
            logger.debug(f"[{self.name}] 已加载 {len(fewshot_samples)} 个现有 Few-Shot 样本")
            return fewshot_samples
            
        except Exception as e:
            logger.warning(f"[{self.name}] 加载 Few-Shot 样本失败: {e}")
            return []
    
    def _save_fewshot_sample(
        self, 
        project_id: str, 
        file_id: str, 
        sample: Dict[str, Any]
    ) -> None:
        """
        保存 Few-Shot 样本到 IntentIntervention 表
        
        :param project_id: 项目 ID
        :param file_id: 文件 ID
        :param sample: 样本数据
        """
        if not project_id:
            return
        
        try:
            from app.db.database import get_db_session
            from app.models import IntentIntervention
            from sqlmodel import select
            from datetime import datetime
            
            query: str = str(sample.get("query", "")).strip()
            target: str = str(sample.get("target", "")).strip()
            difficulty_score: float = float(sample.get("difficulty_score", 0.0))
            
            with get_db_session() as session:
                # 查找是否已存在
                stmt = select(IntentIntervention).where(
                    IntentIntervention.project_id == project_id,
                    IntentIntervention.query == query
                )
                if file_id:
                    stmt = stmt.where(IntentIntervention.file_id == file_id)
                
                existing = session.exec(stmt).first()
                
                if existing:
                    # 更新现有记录
                    existing.is_fewshot_sample = True
                    existing.difficulty_score = difficulty_score
                    existing.updated_at = datetime.now().isoformat()
                else:
                    # 创建新记录
                    new_intervention = IntentIntervention(
                        project_id=project_id,
                        query=query,
                        target=target,
                        reason=str(sample.get("reason", "")),
                        difficulty_score=difficulty_score,
                        is_fewshot_sample=True,
                        file_id=file_id or ""
                    )
                    session.add(new_intervention)
                
                session.commit()
                logger.debug(f"[{self.name}] 保存 Few-Shot 样本: query='{query[:30]}...'")
                
        except Exception as e:
            logger.error(f"[{self.name}] 保存 Few-Shot 样本失败: {e}")
    
    def _unmark_fewshot_sample(
        self, 
        project_id: str, 
        file_id: str, 
        sample: Dict[str, Any]
    ) -> None:
        """
        取消样本的 Few-Shot 标记
        
        :param project_id: 项目 ID
        :param file_id: 文件 ID
        :param sample: 样本数据
        """
        if not project_id:
            return
        
        try:
            from app.db.database import get_db_session
            from app.models import IntentIntervention
            from sqlmodel import select
            from datetime import datetime
            
            query: str = str(sample.get("query", "")).strip()
            
            with get_db_session() as session:
                stmt = select(IntentIntervention).where(
                    IntentIntervention.project_id == project_id,
                    IntentIntervention.query == query
                )
                if file_id:
                    stmt = stmt.where(IntentIntervention.file_id == file_id)
                
                existing = session.exec(stmt).first()
                
                if existing:
                    existing.is_fewshot_sample = False
                    existing.updated_at = datetime.now().isoformat()
                    session.commit()
                    logger.debug(f"[{self.name}] 取消 Few-Shot 标记: query='{query[:30]}...'")
                
        except Exception as e:
            logger.error(f"[{self.name}] 取消 Few-Shot 标记失败: {e}")
    
    def _deduplicate_cases(self, cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        对案例列表进行去重，基于 query 字段
        
        :param cases: 原始案例列表
        :return: 去重后的案例列表
        """
        seen_queries: set = set()
        unique_cases: List[Dict[str, Any]] = []
        
        for case in cases:
            query: str = str(case.get('query', '')).strip()
            if query and query not in seen_queries:
                seen_queries.add(query)
                unique_cases.append(case)
        
        logger.debug(f"案例去重: 原始 {len(cases)} 个, 去重后 {len(unique_cases)} 个")
        return unique_cases
    
    def _build_hard_cases_text(self, hard_cases: List[Dict[str, Any]]) -> str:
        """
        构建困难案例 JSON 文本
        
        :param hard_cases: 困难案例列表
        :return: JSON 格式的案例文本
        """
        unique_cases: List[Dict[str, Any]] = self._deduplicate_cases(hard_cases)
        
        if not unique_cases:
            return "暂无困难案例"
        
        cases_list: List[Dict[str, Any]] = []
        
        for case in unique_cases:
            case_data: Dict[str, Any] = {
                "query": str(case.get('query', ''))[:100],
                "correct_intent": str(case.get('target', '')),
                "model_output": str(case.get('output', ''))[:50]
            }
            # 如果有难度评分，添加到输出
            if "difficulty_score" in case:
                case_data["difficulty_score"] = round(case["difficulty_score"], 1)
            cases_list.append(case_data)
        
        return json.dumps({"hard_cases": cases_list}, ensure_ascii=False, indent=2)
    
    def _build_example_cases_from_errors(self, cases: List[Dict[str, Any]]) -> str:
        """
        从实际错误案例中构建示例 JSON，供 LLM 参考生成业务相关的 Few-Shot 示例
        
        :param cases: 错误案例列表
        :return: JSON 格式的示例文本
        """
        unique_cases: List[Dict[str, Any]] = self._deduplicate_cases(cases)
        
        if not unique_cases:
            return "暂无实际业务案例可供参考"
        
        examples_list: List[Dict[str, str]] = []
        
        for case in unique_cases:
            examples_list.append({
                "query": str(case.get('query', ''))[:100],
                "correct_intent": str(case.get('target', '')),
                "wrong_output": str(case.get('output', ''))[:50]
            })
        
        return json.dumps({"reference_cases": examples_list}, ensure_ascii=False, indent=2)
    
    def _build_optimization_instruction(
        self, 
        hard_cases_text: str, 
        example_cases_text: str
    ) -> str:
        """
        构建优化指令
        
        :param hard_cases_text: 困难案例文本
        :param example_cases_text: 示例案例文本
        :return: 完整的优化指令
        """
        return f"""当前提示词的 Few-Shot 示例需要优化，重点是**保留现有示例，并精选添加新的困难案例示例**。

## 困难案例分析
以下是模型难以正确处理的典型案例（仅供分析，不要全部添加）：
{hard_cases_text}

## 优化要求

请按照以下**严格流程**完善提示词的 Few-Shot 场景示例部分：

### 第一步：识别并保留现有示例 (CRITICAL - 必须执行)
1. 仔细阅读原提示词，**完整识别**其中已有的所有 Few-Shot 示例
2. **必须100%保留**原有示例，不得删除或遗漏任何一个
3. 如原提示词没有示例部分，则跳过此步骤

### 第二步：精选添加困难案例示例
> **[核心约束]** 仅从困难案例中**精选 1-3 个最具代表性的案例**添加为 Few-Shot 示例
> **严禁**为每个困难案例都添加示例！选择最能覆盖核心错误模式的案例即可

选择标准：
- 优先选择难度评分最高（difficulty_score ≥ 7）的案例
- 优先选择能代表一类错误模式的案例（而非个例）
- 优先选择与现有示例互补的案例（避免重复覆盖同类场景）
- **直接使用原始 Query**，不做泛化

### 整合原则 (严禁重复)
- **严禁**删除原有的任何示例
- **严禁**新增独立的 "## Few-Shot 场景示例" 标题，必须**整合**到原提示词中已有的该部分
- **严禁**重复添加 "单意图示例"、"多意图示例" 等类型标签，如已有则在其下优化示例
- 如原提示词中没有该部分，则在正确位置**新增一个**（仅此一个）

### 格式一致性要求
- 新增的示例**必须**与原提示词中现有的示例或输出要求保持**完全一致**的格式

### 参考业务案例（严禁编造或改写）
> **[最高优先级约束]** 以下是**唯一可用**的业务案例来源：
{example_cases_text}

**强制规则：**
1. 你添加的每个示例的 `query` 字段**必须逐字复制**自上方参考案例
2. **严禁**编造、改写、省略或添加任何字符
3. **严禁**使用不在上方列表中的任何 query
4. 如果参考案例不足 3 个，则只添加已有的案例数量

### 示例结构要求
添加的示例**必须**采用 **JSON 格式**，且 `query` 字段必须**逐字复制**自上方参考案例：
```json
{{
  "examples": [
    {{
      "query": "必须逐字复制自上方参考案例的 query，严禁改写",
      "intent": "意图名称",
      "reason": "简要原因（为什么是这个意图）"
    }}
  ]
}}
```

> **[输出前自检 - 必须执行]**
> 对每个新增示例执行以下检查，任一检查不通过则删除该示例：
> 1. 该 query 是否**逐字**出现在「参考业务案例」中？ → 必须为 Yes
> 2. query 是否有任何字符被改写、省略或添加？ → 必须为 No
> 3. 如果该 query 不在参考案例中，**立即删除该示例**

"""
