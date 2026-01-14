"""诊断分析模块 - 分析提示词性能和错误模式"""
from typing import List, Dict, Any, Tuple
from collections import Counter, defaultdict
import re
import pandas as pd
import math
from .hard_case_detection import HardCaseDetector

def diagnose_prompt_performance(
    prompt: str, 
    errors: List[Dict[str, Any]], 
    total_count: int = None,
    llm_client: Any = None,
    model_config: Dict[str, Any] = None,
    project_id: str = None,
    **kwargs
) -> Dict[str, Any]:
    """
    综合诊断提示词性能
    
    Args:
        prompt: 当前提示词
        errors: 错误样例列表
        total_count: 总样例数（用于计算准确率，可选）
        project_id: 项目ID（可选，用于查询历史错误）
        
    Returns:
        诊断结果字典
    """
    error_count = len(errors)
    total = total_count or max(error_count * 2, 100)  # 估算总数
    accuracy = 1 - (error_count / total) if total > 0 else 0
    
    # 基础分析
    confusion_pairs = extract_confusion_pairs(errors)
    
    # 困难案例探测
    detector = HardCaseDetector(llm_client, model_config)
    hard_cases = detector.detect_hard_cases(errors, top_k=50, project_id=project_id)
    if not hard_cases: # Fallback to old method if no hard cases found (e.g. empty lists)
         hard_cases = identify_hard_cases(errors)

    category_dist = get_error_category_distribution(errors)
    
    # 深度分析
    deep_analysis = {
        "confusion_matrix": build_confusion_matrix_data(errors),
        "pattern_clusters": cluster_error_patterns(errors),
        "decision_boundaries": analyze_decision_boundaries(errors),
        "text_features": extract_text_features(errors)
    }
    
    # 自动生成建议
    suggestions = generate_optimization_suggestions(
        accuracy, 
        confusion_pairs, 
        deep_analysis,
        prompt
    )
    
    return {
        "overall_metrics": {
            "accuracy": accuracy,
            "error_count": error_count,
            "total_count": total
        },
        "error_patterns": {
            "confusion_pairs": confusion_pairs,
            "hard_cases": hard_cases,
            "category_distribution": category_dist,
            "clusters": deep_analysis["pattern_clusters"]
        },
        "prompt_analysis": {
            "instruction_clarity": analyze_instruction_clarity(prompt),
            "has_examples": detect_examples_in_prompt(prompt),
            "has_constraints": detect_constraints_in_prompt(prompt)
        },
        "deep_analysis": deep_analysis,
        "suggestions": suggestions
    }


def build_confusion_matrix_data(errors: List[Dict[str, Any]]) -> Dict[str, Any]:
    """构建混淆矩阵数据"""
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
            # 找出非对角线上的最大值（如果是全错误数据，所有都是非对角线...或者可能是对角线如果errors包含正确?
            # 这里的 errors 参数只包含错误案例，所以所有条目理论上都是 mismatch (除非数据有问题)
            # 不过 crosstab 可能会包含某些偶然正确？不，输入是 errors 列表。
            # 所以整个矩阵都是错误分布。
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
        print(f"Error building confusion matrix: {e}")
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


def generate_optimization_suggestions(
    accuracy: float,
    confusion_pairs: List[Tuple],
    deep_analysis: Dict,
    prompt: str
) -> List[str]:
    """自动生成优化建议"""
    suggestions = []
    
    # 基于准确率的建议
    if accuracy < 0.6:
        suggestions.append("instruction_refinement")  # 准确率低，优先优化指令
        suggestions.append("meta_optimization")      # 尝试元优化
        
    # 基于混淆的建议
    matrix_info = deep_analysis.get("confusion_matrix", {})
    if matrix_info.get("top_confusion_rate", 0) > 0.2:
        suggestions.append("boundary_clarification")  # 混淆严重，添加边界澄清
        
    if confusion_pairs:
        suggestions.append("boundary_clarification")
        
    # 基于错误模式的建议
    clusters = deep_analysis.get("pattern_clusters", [])
    if clusters and clusters[0]['count'] > 5:
        # 存在明显的错误聚集，可能需要特定案例注入
        suggestions.append("difficult_example_injection")
        
    # 基于特征的建议
    features = deep_analysis.get("text_features", {})
    if features.get("avg_query_length", 0) < 10:
        suggestions.append("add_context_clarification") # 查询太短，可能需要补充上下文说明
        
    # 去重
    return list(set(suggestions))


def extract_confusion_pairs(
    errors: List[Dict[str, Any]], 
    threshold: float = 0.1
) -> List[Tuple[str, str, float]]:
    """
    提取混淆对 - 找出经常被混淆的类别对
    """
    pair_counts = defaultdict(int)
    target_counts = Counter()
    
    for err in errors:
        target = str(err.get('target', '')).strip()
        output = str(err.get('output', '')).strip()
        
        if target and output and target != output:
            pair = tuple(sorted([target, output]))
            pair_counts[pair] += 1
            target_counts[target] += 1
    
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


def analyze_instruction_clarity(prompt: str) -> float:
    """分析提示词指令的清晰度"""
    score = 0.5
    
    task_patterns = [
        r'你的任务是', r'请你', r'你需要', r'your task is', 
        r'please', r'classify', r'identify', r'分类', r'识别'
    ]
    if any(re.search(p, prompt, re.IGNORECASE) for p in task_patterns):
        score += 0.1
    
    step_patterns = [
        r'第[一二三四五1-5]步', r'step \d', r'首先.*然后',
        r'1\.|2\.|3\.', r'第一', r'接下来'
    ]
    if any(re.search(p, prompt, re.IGNORECASE) for p in step_patterns):
        score += 0.15
    
    format_patterns = [
        r'输出格式', r'格式要求', r'output format', r'返回格式',
        r'只输出', r'仅输出', r'直接输出'
    ]
    if any(re.search(p, prompt, re.IGNORECASE) for p in format_patterns):
        score += 0.1
    
    constraint_patterns = [
        r'禁止', r'不要', r'不能', r'必须', r'严禁',
        r'do not', r'don\'t', r'must', r'should not'
    ]
    if any(re.search(p, prompt, re.IGNORECASE) for p in constraint_patterns):
        score += 0.1
    
    if detect_examples_in_prompt(prompt):
        score += 0.05
    
    return min(1.0, score)


def detect_examples_in_prompt(prompt: str) -> bool:
    """检测提示词中是否包含示例"""
    example_patterns = [
        r'例如', r'示例', r'example', r'例:', r'如：',
        r'输入[:：].*输出[:：]', r'input[:：].*output[:：]'
    ]
    return any(re.search(p, prompt, re.IGNORECASE) for p in example_patterns)


def detect_constraints_in_prompt(prompt: str) -> bool:
    """检测提示词中是否包含约束条件"""
    constraint_patterns = [
        r'禁止', r'不要', r'不能', r'必须', r'严禁', r'注意',
        r'do not', r'don\'t', r'must', r'should not', r'never'
    ]
    return any(re.search(p, prompt, re.IGNORECASE) for p in constraint_patterns)
