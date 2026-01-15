"""动态示例选择算法 - 智能选择few-shot示例"""
import random
import math
from typing import List, Dict, Any
from collections import defaultdict

class FewShotSelector:
    """智能 Few-shot 示例选择器"""
    
    def select(self, dataset: List[Dict[str, Any]], strategy: str, n: int = 5) -> List[Dict[str, Any]]:
        """
        根据策略选择示例
        
        Args:
            dataset: 数据集列表
            strategy: 选择策略 (random, diversity, difficulty, boundary, prototype, auto)
            n: 需要选择的数量
        """
        if not dataset:
            return []
            
        if len(dataset) <= n:
            return dataset
            
        if strategy == "diversity":
            return self.select_by_diversity(dataset, n)
        elif strategy == "difficulty":
            return self.select_hard_cases(dataset, n)
        elif strategy == "boundary":
            return self.select_boundary_cases(dataset, n)
        elif strategy == "prototype":
            return self.select_prototype_examples(dataset, n)
        elif strategy == "auto":
            return self.auto_select(dataset, n)
        else:
            return random.sample(dataset, n)
            
    def select_by_diversity(self, dataset: List[Dict[str, Any]], n: int) -> List[Dict[str, Any]]:
        """多样性选择 - 简单实现：按长度分桶采样"""
        # 按长度排序
        sorted_data = sorted(dataset, key=lambda x: len(str(x.get('query', ''))))
        
        # 分桶采样
        bucket_size = len(dataset) // n
        selected = []
        for i in range(n):
            # 在每个桶中随机选一个
            start = i * bucket_size
            end = (i + 1) * bucket_size if i < n - 1 else len(dataset)
            selected.append(random.choice(sorted_data[start:end]))
            
        return selected
    
    def select_hard_cases(self, dataset: List[Dict[str, Any]], n: int) -> List[Dict[str, Any]]:
        """困难案例选择 - 基于复杂度启发式"""
        # 评分函数：长度 + 特殊字符数
        def complexity_score(item):
            text = str(item.get('query', ''))
            score = len(text) * 0.1  # 长度权重
            # 如果包含非字母数字字符，增加分数
            special_chars = sum(1 for c in text if not c.isalnum() and not c.isspace())
            score += special_chars * 2
            return score
            
        # 按复杂度降序排序
        sorted_data = sorted(dataset, key=complexity_score, reverse=True)
        return sorted_data[:n]
    
    def select_boundary_cases(self, dataset: List[Dict[str, Any]], n: int) -> List[Dict[str, Any]]:
        """边界案例选择 - 选择不同标签但文本相似的样本"""
        # 简单实现：按标签分组，然后找长度相近但标签不同的
        # 如果没有标签，回退到随机
        if not all('target' in x for x in dataset):
            return random.sample(dataset, n)
            
        # 这里的"边界"定义为：与其他类别样本非常相似的样本
        # 由于计算量限制，这里只做简单筛选：选择那些 query 长度与其他类别 query 长度非常接近的样本
        
        # 更好的简单策略：确保每个类别都有代表，且尽可能选择"非典型"（如长度偏短或偏长）的样本
        # 但为了符合"边界"定义，我们尝试寻找包含共有词汇的跨类别样本 (简化版)
        return self.select_by_diversity(dataset, n) # 暂时回退到多样性，因为计算真正的边界需要Embedding或严格匹配
    
    def select_prototype_examples(self, dataset: List[Dict[str, Any]], n: int) -> List[Dict[str, Any]]:
        """原型案例选择 - 选择最接近平均长度的样本"""
        avg_len = sum(len(str(x.get('query', ''))) for x in dataset) / len(dataset)
        
        # 按与平均长度的距离排序
        sorted_data = sorted(dataset, key=lambda x: abs(len(str(x.get('query', ''))) - avg_len))
        return sorted_data[:n]
    
    def auto_select(self, dataset: List[Dict[str, Any]], n: int = 5) -> List[Dict[str, Any]]:
        """自适应混合选择"""
        if len(dataset) < n * 2:
            return random.sample(dataset, n)
            
        # 混合策略：40% 原型，30% 多样性，30% 困难
        n_proto = max(1, int(n * 0.4))
        n_div = max(1, int(n * 0.3))
        n_hard = n - n_proto - n_div
        
        selected = []
        # 使用副本避免重复选择影响
        pool = list(dataset)
        
        # 原型
        protos = self.select_prototype_examples(pool, n_proto)
        selected.extend(protos)
        for p in protos:
            if p in pool: pool.remove(p)
            
        # 多样性
        divs = self.select_by_diversity(pool, n_div)
        selected.extend(divs)
        for d in divs:
            if d in pool: pool.remove(d)
            
        # 困难
        hards = self.select_hard_cases(pool, n_hard)
        selected.extend(hards)
        
        return selected
