"""
诊断模块 - 指标分析组件
包含混淆矩阵构建、错误模式聚类、决策边界分析等数据分析逻辑
"""
from loguru import logger
import pandas as pd
import re
from typing import List, Dict, Any, Tuple
from collections import Counter, defaultdict

def build_confusion_matrix_data(errors: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    构建混淆矩阵数据
    
    :param errors: 错误样例列表
    :return: 混淆矩阵数据字典
    """
    if not errors:
        return {}
        
    y_true = [str(e.get('target', '')).strip() for e in errors]
    y_pred = [str(e.get('output', '')).strip() for e in errors]
    
    # 使用 pandas 创建混淆矩阵
    try:
        df = pd.DataFrame({'Actual': y_true, 'Predicted': y_pred})
        confusion_matrix = pd.crosstab(df['Actual'], df['Predicted'])
        
        # 转换为字典格式
        matrix_dict = confusion_matrix.to_dict(orient='index')
        
        # 计算最高混淆率
        total_errors = len(errors)
        top_confusion_rate = 0
        if total_errors > 0:
            max_val = 0
            for row in matrix_dict.values():
                for val in row.values():
                    if val > max_val:
                        max_val = val
            top_confusion_rate = max_val / total_errors
            
        return {
            "matrix": matrix_dict,
            "top_confusion_rate": top_confusion_rate,
            "labels": sorted(list(set(y_true) | set(y_pred)))
        }
    except Exception as e:
        logger.error(f"构建混淆矩阵失败: {e}")
        return {}


def cluster_error_patterns(errors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    聚类错误模式
    基于 (Target, Output) 对进行分组，并分析每组的特征
    """
    clusters = defaultdict(list)
    
    for err in errors:
        key = (str(err.get('target', '')).strip(), str(err.get('output', '')).strip())
        clusters[key].append(err)
        
    result = []
    for (target, output), items in clusters.items():
        if len(items) < 2:  # 忽略孤立错误
            continue
            
        # 提取共同特征 (简单实现)
        avg_len = sum(len(str(x.get('query', ''))) for x in items) / len(items)
        
        result.append({
            "pattern": f"{target} -> {output}",
            "count": len(items),
            "avg_length": avg_len,
            "sample_queries": [str(x.get('query', ''))[:50] for x in items[:3]]
        })
        
    # 按数量排序
    result.sort(key=lambda x: x['count'], reverse=True)
    return result


def analyze_decision_boundaries(errors: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    分析决策边界
    识别哪些类别之间边界最模糊
    """
    boundary_ambiguity = defaultdict(int)
    
    for err in errors:
        target = str(err.get('target', '')).strip()
        output = str(err.get('output', '')).strip()
        
        pair = tuple(sorted([target, output]))
        boundary_ambiguity[pair] += 1
        
    # 转换为列表
    boundaries = []
    for (c1, c2), count in boundary_ambiguity.items():
        boundaries.append({
            "class_a": c1,
            "class_b": c2,
            "ambiguity_score": count,  # 错误次数作为模糊度代理
        })
        
    boundaries.sort(key=lambda x: x['ambiguity_score'], reverse=True)
    return {"ambiguous_boundaries": boundaries[:5]}


def extract_text_features(errors: List[Dict[str, Any]]) -> Dict[str, Any]:
    """提取错误案例的文本特征"""
    if not errors:
        return {}
        
    lengths = [len(str(e.get('query', ''))) for e in errors]
    avg_len = sum(lengths) / len(lengths) if lengths else 0
    
    # 检查是否包含数字/英文
    has_digit = sum(1 for e in errors if re.search(r'\d', str(e.get('query', ''))))
    has_english = sum(1 for e in errors if re.search(r'[a-zA-Z]', str(e.get('query', ''))))
    
    return {
        "avg_query_length": avg_len,
        "ratio_containing_digits": has_digit / len(errors) if errors else 0,
        "ratio_containing_english": has_english / len(errors) if errors else 0
    }


def extract_confusion_pairs(
    errors: List[Dict[str, Any]], 
    threshold: float = 0.1
) -> List[Tuple[str, str, float]]:
    """
    提取混淆对 - 找出经常被混淆的类别对
    """
    pair_counts = defaultdict(int)
    
    for err in errors:
        target = str(err.get('target', '')).strip()
        output = str(err.get('output', '')).strip()
        
        if target and output and target != output:
            pair = tuple(sorted([target, output]))
            pair_counts[pair] += 1
    
    confusion_pairs = []
    total_errors = len(errors)
    
    for (intent_a, intent_b), count in pair_counts.items():
        # 计算归一化后的混淆率 (相对于总错误数)
        rate = count / total_errors if total_errors > 0 else 0
        if rate >= threshold / 2: # 稍微降低阈值以便捕获更多
            confusion_pairs.append((intent_a, intent_b, rate))
    
    confusion_pairs.sort(key=lambda x: x[2], reverse=True)
    return confusion_pairs[:20]


def identify_hard_cases(
    errors: List[Dict[str, Any]], 
    top_k: int = 50
) -> List[Dict[str, Any]]:
    """
    识别困难案例 - 选择最具代表性的错误样例
    """
    scored_errors = []
    
    for err in errors:
        query = str(err.get('query', ''))
        target = str(err.get('target', ''))
        output = str(err.get('output', ''))
        
        score = 0
        if len(query) < 50: score += 2
        elif len(query) < 100: score += 1
        
        if target.lower() != output.lower(): score += 1
        
        scored_errors.append((score, err))
    
    scored_errors.sort(key=lambda x: x[0], reverse=True)
    return [err for score, err in scored_errors[:top_k]]


def get_error_category_distribution(
    errors: List[Dict[str, Any]]
) -> Dict[str, int]:
    """获取错误在各类别上的分布"""
    target_counts = Counter()
    for err in errors:
        target = str(err.get('target', '')).strip()
        if target:
            target_counts[target] += 1
    return dict(target_counts.most_common(20))
