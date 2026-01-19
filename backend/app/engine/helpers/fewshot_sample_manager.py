"""
Few-Shot 样本管理器

基于 text2vec 向量化计算样本难区分程度，管理 Few-Shot 样本的注入、配额和替换策略。

核心功能：
1. 批量向量化所有样本：使用 SentenceModel
2. 矩阵运算计算难区分程度：(Max Similarity with Different Intent)
3. 按意图分组的数量限制：
   - 普通单意图: 不超过该意图在数据集中对应数量的 10%
   - 澄清意图: 不超过数据集总数的 10%
   - 多意图: 不超过数据集总数的 10%
4. 基于评分的低分样本替换策略
"""
import hashlib
import numpy as np
from loguru import logger
from typing import List, Dict, Any, Optional, Tuple, Set
from datetime import datetime


class FewShotSampleManager:
    """
    Few-Shot 样本管理器
    
    管理 Few-Shot 难例样本的评分、注入、配额检查和替换。
    使用 SentenceModel 进行批量向量化计算以提升性能。
    """
    
    # 难度评分阈值（只有 ≥ 该阈值的样本才会被考虑注入）
    DIFFICULTY_THRESHOLD: float = 7.0
    
    # 意图类型配额限制
    # 普通单意图: 不超过该意图在数据集中对应数量的 10%
    NORMAL_INTENT_QUOTA_RATIO: float = 0.10
    # 澄清意图: 不超过数据集总数的 10%
    CLARIFICATION_QUOTA_RATIO: float = 0.10
    # 多意图: 不超过数据集总数的 10%
    MULTI_INTENT_QUOTA_RATIO: float = 0.10
    
    # 全局模型单例
    _sentence_model: Optional[Any] = None
    
    def __init__(self, project_id: str, file_id: str = ""):
        self.project_id: str = project_id
        self.file_id: str = file_id
        logger.info(f"[FewShotSampleManager] 初始化，项目ID: {project_id}, 文件ID: {file_id}")
    
    @classmethod
    def _get_sentence_model(cls) -> Any:
        """获取 SentenceModel 单例"""
        if cls._sentence_model is None:
            try:
                from text2vec import SentenceModel
                # 使用中文模型，如果需要可以改为通过配置传入模型名称
                cls._sentence_model = SentenceModel()
                logger.info("[FewShotSampleManager] text2vec SentenceModel 加载成功")
            except Exception as e:
                logger.error(f"[FewShotSampleManager] 加载 text2vec 模型失败: {e}")
                cls._sentence_model = None
        return cls._sentence_model
    
    def batch_calculate_difficulty_scores(
        self, 
        target_samples: List[Dict[str, Any]], 
        reference_samples: List[Dict[str, Any]]
    ) -> List[float]:
        """
        批量计算样本的难区分程度评分 (高性能矩阵版)
        
        评分逻辑：
        1. 对目标样本和参考样本进行批量 Embedding
        2. 计算 Cosine Similarity 矩阵
        3. 对于每个目标样本，只关注那些【意图不同】的参考样本的相似度
        4. 难度分 = Max(跨意图相似度) * 10
        
        解释：如果一个 Query 与其他 Query 很像，但意图是相同的，这不算困难（一致性）。
        只有当 Query 与其他意图的 Query 很像时，才算困难（易混淆）。
        
        :param target_samples: 需要评分的样本列表
        :param reference_samples: 参考样本列表（通常是整个数据集，包含 target_samples）
        :return: 对应的分数列表
        """
        if not target_samples or not reference_samples:
            return [0.0] * len(target_samples)
            
        model = self._get_sentence_model()
        
        if model is None:
            # 降级到简单评分
            return [self._calculate_simple_difficulty(t, reference_samples) for t in target_samples]

        # 1. 准备数据
        target_queries = [str(s.get("query", "")).strip() for s in target_samples]
        ref_queries = [str(s.get("query", "")).strip() for s in reference_samples]
        
        target_intents = [str(s.get("target", "")).strip() for s in target_samples]
        ref_intents = [str(s.get("target", "")).strip() for s in reference_samples]
        
        try:
            # 2. 批量 Embedding (Normalize for Cosine Similarity)
            # 这里的 batch_size 可以根据显存/内存调整，默认 32
            target_embeddings = model.encode(target_queries, normalize_embeddings=True)
            ref_embeddings = model.encode(ref_queries, normalize_embeddings=True)
            
            # 3. 计算相似度矩阵 (Target x Ref)
            # shape: (num_targets, num_refs)
            similarity_matrix = np.matmul(target_embeddings, ref_embeddings.T)
            
            # 4. 计算难度分
            scores = []
            for i in range(len(target_samples)):
                current_intent = target_intents[i]
                current_query = target_queries[i]
                
                # 获取该目标样本与所有参考样本的相似度行
                sim_row = similarity_matrix[i]
                
                # 筛选出【意图不同】且【非自身】的索引
                # 注意：如果意图相同，mask 为 False；意图不同，mask 为 True
                # 我们只关心 mask 为 True 的相似度
                
                # 意图不同 mask
                diff_intent_mask = np.array([ri != current_intent for ri in ref_intents])
                
                # 排除完全相同的 query (避免自身对比或重复数据影响)
                # 虽然意图不同通常意味着 query 不同，但为了保险
                non_self_mask = np.array([rq != current_query for rq in ref_queries])
                
                # 最终有效 mask
                valid_mask = diff_intent_mask & non_self_mask
                
                if not np.any(valid_mask):
                    # 如果没有不同意图的样本，或者所有不同意图的样本 query 都一样(不可能)，则难度为 0
                    scores.append(0.0)
                    continue
                
                # 获取有效相似度
                valid_sims = sim_row[valid_mask]
                
                # 取最大相似度
                max_sim = np.max(valid_sims)
                
                # 映射到 0-10 分
                # 相似度范围 [-1, 1], 取 max(0, sim) * 10
                difficulty = max(0.0, float(max_sim)) * 10.0
                scores.append(round(difficulty, 2))
                
            logger.info(
                f"[FewShotSampleManager] 批量评分完成: {len(scores)} 个样本, "
                f"平均分={np.mean(scores):.2f}, 最高分={np.max(scores):.2f}"
            )
            return scores
            
        except Exception as e:
            logger.error(f"[FewShotSampleManager] 批量向量计算失败: {e}")
            # 出错降级
            return [0.0] * len(target_samples)

    def calculate_difficulty_score(
        self, 
        sample: Dict[str, Any], 
        all_samples: List[Dict[str, Any]]
    ) -> float:
        """
        单样本评分（包装批量方法）
        """
        scores = self.batch_calculate_difficulty_scores([sample], all_samples)
        return scores[0] if scores else 0.0
    
    def _calculate_simple_difficulty(
        self, 
        sample: Dict[str, Any], 
        all_samples: List[Dict[str, Any]]
    ) -> float:
        """简化版评分（字符串相似度）"""
        query = str(sample.get("query", "")).strip().lower()
        target = str(sample.get("target", "")).strip()
        if not query: return 0.0
        
        diff_intent_sims = []
        for s in all_samples:
            s_target = str(s.get("target", "")).strip()
            if s_target == target: continue # 意图相同，跳过
            
            s_query = str(s.get("query", "")).strip().lower()
            if s_query == query: continue
            
            # Jaccard 相似度
            q_set = set(query)
            sq_set = set(s_query)
            intersect = len(q_set & sq_set)
            union = len(q_set | sq_set)
            sim = intersect / union if union > 0 else 0.0
            diff_intent_sims.append(sim)
            
        if not diff_intent_sims:
            return 0.0
            
        return max(diff_intent_sims) * 10.0
    
    def check_quota(
        self, 
        intent: str, 
        intent_type: str,
        intent_sample_counts: Dict[str, int],
        total_sample_count: int,
        current_fewshot_counts: Dict[str, int]
    ) -> Tuple[bool, int, int]:
        """检查配额"""
        current = current_fewshot_counts.get(intent, 0)
        
        if intent_type == "clarification":
            limit = max(1, int(total_sample_count * self.CLARIFICATION_QUOTA_RATIO))
            total = sum(v for k, v in current_fewshot_counts.items() if self._is_clarification_intent(k))
            return total < limit, total, limit
        elif intent_type == "multi_intent":
            limit = max(1, int(total_sample_count * self.MULTI_INTENT_QUOTA_RATIO))
            total = sum(v for k, v in current_fewshot_counts.items() if self._is_multi_intent(k))
            return total < limit, total, limit
        else:
            total_in_data = intent_sample_counts.get(intent, 100)
            limit = max(1, int(total_in_data * self.NORMAL_INTENT_QUOTA_RATIO))
            return current < limit, current, limit

    def _is_clarification_intent(self, intent: str) -> bool:
        kws = ["澄清", "clarification", "clarify", "unclear", "需要更多信息", "需要澄清", "追问"]
        return any(k in intent.lower() for k in kws)
    
    def _is_multi_intent(self, intent: str) -> bool:
        inds = ["+", ",", "和", "且", "multi", "multiple"]
        return any(k in intent.lower() for k in inds)

    def classify_intent_type(self, intent: str) -> str:
        if self._is_clarification_intent(intent): return "clarification"
        elif self._is_multi_intent(intent): return "multi_intent"
        else: return "normal"

    def add_fewshot_sample(
        self,
        sample: Dict[str, Any],
        difficulty_score: float,
        intent_sample_counts: Dict[str, int],
        total_sample_count: int,
        current_fewshot_samples: List[Dict[str, Any]]
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        尝试添加样本，支持替换低分样本
        
        核心逻辑：
        1. 有配额时：只有高于阈值的样本才会添加
        2. 无配额时：将新样本与所有同意图/同类型已有样本放在一起比较，
           丢弃分数最低的那个（可能是新样本，也可能是已有样本）
        
        :param sample: 待添加的样本
        :param difficulty_score: 样本的难度评分
        :param intent_sample_counts: 各意图在数据集中的样本数量
        :param total_sample_count: 数据集总样本数
        :param current_fewshot_samples: 当前已有的 Few-Shot 样本列表
        :return: (是否添加成功, 被替换的样本或None)
        """
        intent: str = str(sample.get("target", "")).strip()
        intent_type: str = self.classify_intent_type(intent)
        
        # 统计当前各意图的 Few-Shot 数量
        current_counts: Dict[str, int] = {}
        for fs in current_fewshot_samples:
            t: str = str(fs.get("target", ""))
            current_counts[t] = current_counts.get(t, 0) + 1
            
        # 检查配额
        has_quota, current_used, limit = self.check_quota(
            intent, intent_type, intent_sample_counts, 
            total_sample_count, current_counts
        )
        
        # 场景1: 有剩余配额
        if has_quota:
            # 有配额时，只添加高于阈值的样本
            if difficulty_score >= self.DIFFICULTY_THRESHOLD:
                logger.debug(
                    f"[FewShot] 添加样本(有配额): intent={intent}, "
                    f"score={difficulty_score:.1f}, used={current_used}/{limit}"
                )
                return True, None
            else:
                logger.debug(
                    f"[FewShot] 跳过低分样本(有配额): intent={intent}, "
                    f"score={difficulty_score:.1f} < 阈值{self.DIFFICULTY_THRESHOLD}"
                )
                return False, None
        
        # 场景2: 配额已满，需要进行替换比较
        # 找出所有同意图/同类型的已有样本作为候选
        candidates: List[Dict[str, Any]] = []
        for fs in current_fewshot_samples:
            fs_intent: str = str(fs.get("target", ""))
            fs_type: str = self.classify_intent_type(fs_intent)
            
            # 判断是否应该纳入比较
            should_compare: bool = False
            if intent_type == "normal":
                # 普通意图：只与相同意图的样本比较
                if fs_intent == intent:
                    should_compare = True
            else:
                # 澄清/多意图：与同类型的所有样本比较
                if fs_type == intent_type:
                    should_compare = True
            
            if should_compare:
                candidates.append(fs)
        
        if not candidates:
            logger.debug(f"[FewShot] 无可替换候选(配额满): intent={intent}")
            return False, None
        
        # 将新样本也加入比较池
        # 创建一个包含所有候选样本（已有 + 新样本）的列表
        all_samples_for_comparison: List[Dict[str, Any]] = candidates.copy()
        new_sample_entry: Dict[str, Any] = {
            "query": sample.get("query", ""),
            "target": intent,
            "difficulty_score": difficulty_score,
            "_is_new": True  # 标记为新样本
        }
        all_samples_for_comparison.append(new_sample_entry)
        
        # 找出分数最低的样本
        min_sample: Dict[str, Any] = min(
            all_samples_for_comparison, 
            key=lambda x: float(x.get("difficulty_score", 0.0))
        )
        min_score: float = float(min_sample.get("difficulty_score", 0.0))
        
        # 判断最低分样本是新样本还是已有样本
        if min_sample.get("_is_new", False):
            # 新样本是最低分，不添加（丢弃新样本）
            logger.debug(
                f"[FewShot] 新样本分数最低被丢弃: intent={intent}, "
                f"new_score={difficulty_score:.1f}, 已有最低分="
                f"{min([float(c.get('difficulty_score', 0.0)) for c in candidates]):.1f}"
            )
            return False, None
        else:
            # 已有样本是最低分，用新样本替换
            logger.info(
                f"[FewShot] 触发替换: intent={intent}, "
                f"新分={difficulty_score:.1f} > 被替换样本分={min_score:.1f}"
            )
            return True, min_sample

    def get_fewshot_samples_for_injection(
        self, 
        fewshot_samples: List[Dict[str, Any]],
        max_per_intent: int = 3
    ) -> List[Dict[str, Any]]:
        """按意图分组取 Top N"""
        groups = {}
        for s in fewshot_samples:
            intent = str(s.get("target", "unknown"))
            groups.setdefault(intent, []).append(s)
            
        result = []
        for intent, samples in groups.items():
            sorted_s = sorted(samples, key=lambda x: float(x.get("difficulty_score", 0)), reverse=True)
            result.extend(sorted_s[:max_per_intent])
        return result
