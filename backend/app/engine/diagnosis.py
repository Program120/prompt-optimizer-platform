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
            "clusters": deep_analysis["pattern_clusters"],
            "format_errors": detect_format_errors(errors),
            "terminology_errors": detect_terminology_errors(errors),
            "ambiguous_queries": detect_ambiguous_queries(errors),
            "boundary_violations": detect_boundary_violations(errors)
        },
        "prompt_analysis": {
            "instruction_clarity": analyze_instruction_clarity(prompt),
            "has_examples": detect_examples_in_prompt(prompt),
            "has_constraints": detect_constraints_in_prompt(prompt),
            "has_cot": detect_cot_in_prompt(prompt),
            "constraint_clarity": analyze_constraint_clarity(prompt),
            "format_issues": detect_format_issues(prompt),
            "output_consistency": analyze_output_consistency(prompt),
            "has_role_definition": detect_role_definition(prompt),
            "scene_coverage": analyze_scene_coverage(prompt)
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


def detect_cot_in_prompt(prompt: str) -> bool:
    """
    检测提示词中是否包含思维链（Chain of Thought）引导
    
    思维链是一种提示词技术，通过引导模型逐步推理来提高复杂任务的准确率。
    常见的思维链模式包括要求模型分步思考、展示推理过程等。
    
    Args:
        prompt: 待检测的提示词文本
        
    Returns:
        如果检测到思维链模式则返回 True，否则返回 False
    """
    # 思维链相关的关键词模式
    cot_patterns = [
        # 中文思维链模式
        r'让我们一步[一]?步',
        r'一步步思考',
        r'逐步分析',
        r'逐步思考',
        r'逐步推理',
        r'分步骤',
        r'思考过程',
        r'推理过程',
        r'推理步骤',
        r'分析步骤',
        r'先.*再.*最后',
        r'首先.*其次.*然后',
        r'请.*展示.*思考',
        r'请.*说明.*推理',
        r'解释.*原因',
        r'给出.*理由',
        r'说明.*依据',
        
        # 英文思维链模式
        r"let'?s\s+think\s+step\s+by\s+step",
        r'think\s+step\s+by\s+step',
        r'step[- ]by[- ]step',
        r'think\s+through',
        r'reason\s+through',
        r'reasoning\s+process',
        r'chain\s+of\s+thought',
        r'show\s+your\s+work',
        r'show\s+your\s+reasoning',
        r'explain\s+your\s+reasoning',
        r'work\s+through',
        r'break\s+(it\s+)?down',
        r'first.*then.*finally',
    ]
    
    return any(re.search(p, prompt, re.IGNORECASE) for p in cot_patterns)


def detect_format_errors(errors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    检测错误案例中的格式错误
    
    格式错误指输出格式不符合预期的情况，例如应该输出单个标签却输出了多个，
    或者输出中包含了多余的标点、空格等格式问题。
    
    Args:
        errors: 错误案例列表
        
    Returns:
        包含格式错误的案例列表
    """
    format_errors: List[Dict[str, Any]] = []
    
    for err in errors:
        output: str = str(err.get('output', '')).strip()
        target: str = str(err.get('target', '')).strip()
        
        is_format_error: bool = False
        error_type: str = ""
        
        # 检测输出中是否包含多余的标点符号
        if re.search(r'[，。！？、；：""''【】（）]', output) and not re.search(r'[，。！？、；：""''【】（）]', target):
            is_format_error = True
            error_type = "多余标点"
        
        # 检测输出中是否包含多个值（用逗号、分号、斜杠分隔）
        elif re.search(r'[,;/|，；]', output) and not re.search(r'[,;/|，；]', target):
            is_format_error = True
            error_type = "多值输出"
        
        # 检测输出长度是否异常（比目标长很多）
        elif len(output) > len(target) * 3 and len(target) > 0:
            is_format_error = True
            error_type = "输出过长"
        
        # 检测是否包含解释性文字
        elif re.search(r'(因为|所以|由于|因此|because|therefore|since)', output, re.IGNORECASE):
            is_format_error = True
            error_type = "包含解释"
            
        if is_format_error:
            format_errors.append({
                "query": err.get('query', ''),
                "target": target,
                "output": output,
                "error_type": error_type
            })
    
    return format_errors[:20]


def detect_terminology_errors(errors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    检测错误案例中的术语错误
    
    术语错误指模型使用了错误的专业术语或同义词替换导致的错误。
    
    Args:
        errors: 错误案例列表
        
    Returns:
        包含术语错误的案例列表
    """
    terminology_errors: List[Dict[str, Any]] = []
    
    for err in errors:
        output: str = str(err.get('output', '')).strip().lower()
        target: str = str(err.get('target', '')).strip().lower()
        
        # 计算字符串相似度（简单的编辑距离比较）
        # 如果输出和目标很相似但不完全相同，可能是术语错误
        if output != target and len(output) > 0 and len(target) > 0:
            # 检查是否有共同的子串（可能是同义词或近似术语）
            common_len: int = 0
            for i in range(min(len(output), len(target))):
                if output[i] == target[i]:
                    common_len += 1
                else:
                    break
            
            # 如果有超过50%的共同前缀，可能是术语混淆
            similarity_ratio: float = common_len / max(len(output), len(target))
            if similarity_ratio > 0.3 and similarity_ratio < 1.0:
                terminology_errors.append({
                    "query": err.get('query', ''),
                    "target": target,
                    "output": output,
                    "similarity": round(similarity_ratio, 2)
                })
    
    return terminology_errors[:20]


def detect_ambiguous_queries(errors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    检测错误案例中的模糊查询
    
    模糊查询指用户输入本身就存在歧义，难以明确判断意图的情况。
    
    Args:
        errors: 错误案例列表
        
    Returns:
        包含模糊查询的案例列表
    """
    ambiguous_queries: List[Dict[str, Any]] = []
    
    # 模糊性指标
    ambiguity_indicators: List[str] = [
        r'或者', r'还是', r'可能', r'大概', r'也许', r'好像',
        r'应该', r'似乎', r'or', r'maybe', r'perhaps', r'probably',
        r'不确定', r'不太清楚', r'不知道'
    ]
    
    for err in errors:
        query: str = str(err.get('query', ''))
        
        # 检查查询是否过短（难以判断意图）
        is_ambiguous: bool = False
        reason: str = ""
        
        if len(query.strip()) < 5:
            is_ambiguous = True
            reason = "查询过短"
        
        # 检查是否包含模糊词
        elif any(re.search(p, query, re.IGNORECASE) for p in ambiguity_indicators):
            is_ambiguous = True
            reason = "包含模糊词"
        
        # 检查是否是纯数字或纯符号
        elif re.match(r'^[\d\s\.\-\+\*\/\=]+$', query.strip()):
            is_ambiguous = True
            reason = "纯数字/符号"
            
        if is_ambiguous:
            ambiguous_queries.append({
                "query": query,
                "target": err.get('target', ''),
                "output": err.get('output', ''),
                "reason": reason
            })
    
    return ambiguous_queries[:20]


def detect_boundary_violations(errors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    检测错误案例中的边界违规
    
    边界违规指模型在相似类别之间做出了错误判断，通常发生在类别边界模糊的情况。
    
    Args:
        errors: 错误案例列表
        
    Returns:
        包含边界违规的案例列表，按违规频次排序
    """
    # 统计每对类别之间的错误次数
    boundary_counts: Dict[Tuple[str, str], int] = defaultdict(int)
    boundary_examples: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    
    for err in errors:
        target: str = str(err.get('target', '')).strip()
        output: str = str(err.get('output', '')).strip()
        
        if target and output and target != output:
            # 使用排序后的元组作为键，确保(A,B)和(B,A)被视为同一对
            pair: Tuple[str, str] = tuple(sorted([target, output]))
            boundary_counts[pair] += 1
            
            if len(boundary_examples[pair]) < 3:
                boundary_examples[pair].append({
                    "query": err.get('query', ''),
                    "target": target,
                    "output": output
                })
    
    # 转换为列表并按频次排序
    violations: List[Dict[str, Any]] = []
    for pair, count in sorted(boundary_counts.items(), key=lambda x: x[1], reverse=True):
        if count >= 2:
            violations.append({
                "class_pair": list(pair),
                "violation_count": count,
                "examples": boundary_examples[pair]
            })
    
    return violations[:10]


def analyze_constraint_clarity(prompt: str) -> float:
    """
    分析提示词中约束条件的清晰度
    
    评估提示词中的约束条件是否明确、具体、可执行。
    
    Args:
        prompt: 待分析的提示词文本
        
    Returns:
        约束清晰度得分 (0.0-1.0)
    """
    score: float = 0.5
    
    # 检查是否有明确的约束词
    constraint_patterns: List[str] = [
        r'禁止', r'不要', r'不能', r'必须', r'严禁',
        r'do not', r'don\'t', r'must', r'should not', r'never'
    ]
    if any(re.search(p, prompt, re.IGNORECASE) for p in constraint_patterns):
        score += 0.15
    
    # 检查是否有具体的数量限制
    quantity_patterns: List[str] = [
        r'最多\d+', r'至少\d+', r'不超过\d+', r'不少于\d+',
        r'at most \d+', r'at least \d+', r'no more than \d+'
    ]
    if any(re.search(p, prompt, re.IGNORECASE) for p in quantity_patterns):
        score += 0.1
    
    # 检查是否有条件语句
    conditional_patterns: List[str] = [
        r'如果.*则', r'当.*时', r'若.*就',
        r'if.*then', r'when.*should', r'in case'
    ]
    if any(re.search(p, prompt, re.IGNORECASE) for p in conditional_patterns):
        score += 0.1
    
    # 检查是否列举了例外情况
    exception_patterns: List[str] = [
        r'除非', r'除了', r'例外', r'特殊情况',
        r'except', r'unless', r'exception'
    ]
    if any(re.search(p, prompt, re.IGNORECASE) for p in exception_patterns):
        score += 0.1
    
    # 检查是否有优先级说明
    priority_patterns: List[str] = [
        r'优先', r'首先.*其次', r'最重要',
        r'priority', r'first.*then', r'most important'
    ]
    if any(re.search(p, prompt, re.IGNORECASE) for p in priority_patterns):
        score += 0.05
    
    return min(1.0, score)


def detect_format_issues(prompt: str) -> Dict[str, Any]:
    """
    检测提示词中的格式问题
    
    分析提示词是否存在格式定义不清、输出要求模糊等问题。
    
    Args:
        prompt: 待检测的提示词文本
        
    Returns:
        格式问题检测结果字典
    """
    issues: List[str] = []
    has_format_spec: bool = False
    
    # 检查是否有明确的输出格式要求
    format_patterns: List[str] = [
        r'输出格式', r'格式要求', r'返回格式', r'output format',
        r'只输出', r'仅输出', r'直接输出', r'只返回', r'仅返回'
    ]
    if any(re.search(p, prompt, re.IGNORECASE) for p in format_patterns):
        has_format_spec = True
    else:
        issues.append("缺少明确的输出格式要求")
    
    # 检查是否有示例输出
    example_output_patterns: List[str] = [
        r'输出[:：]', r'output[:：]', r'返回[:：]',
        r'示例输出', r'example output'
    ]
    if not any(re.search(p, prompt, re.IGNORECASE) for p in example_output_patterns):
        issues.append("缺少输出示例")
    
    # 检查是否有禁止解释性输出的要求
    no_explain_patterns: List[str] = [
        r'不要解释', r'无需解释', r'不需要解释', r'不用解释',
        r'do not explain', r'no explanation'
    ]
    if not any(re.search(p, prompt, re.IGNORECASE) for p in no_explain_patterns):
        issues.append("未明确禁止解释性输出")
    
    return {
        "has_format_spec": has_format_spec,
        "issues": issues,
        "issue_count": len(issues)
    }


def analyze_output_consistency(prompt: str) -> Dict[str, Any]:
    """
    分析提示词的输出一致性要求
    
    检查提示词是否定义了一致的输出规范，避免歧义。
    
    Args:
        prompt: 待分析的提示词文本
        
    Returns:
        输出一致性分析结果字典
    """
    consistency_score: float = 0.5
    findings: List[str] = []
    
    # 检查是否定义了输出选项/类别列表
    option_patterns: List[str] = [
        r'可选值[:：]', r'选项[:：]', r'类别[:：]', r'分类[:：]',
        r'options[:：]', r'categories[:：]', r'choices[:：]'
    ]
    if any(re.search(p, prompt, re.IGNORECASE) for p in option_patterns):
        consistency_score += 0.2
        findings.append("已定义输出选项列表")
    
    # 检查是否有一致性要求
    consistency_patterns: List[str] = [
        r'保持一致', r'统一格式', r'格式统一',
        r'consistent', r'uniform format'
    ]
    if any(re.search(p, prompt, re.IGNORECASE) for p in consistency_patterns):
        consistency_score += 0.15
        findings.append("有一致性要求")
    
    # 检查是否有标准化要求
    standardize_patterns: List[str] = [
        r'标准化', r'规范化', r'统一为',
        r'standardize', r'normalize'
    ]
    if any(re.search(p, prompt, re.IGNORECASE) for p in standardize_patterns):
        consistency_score += 0.15
        findings.append("有标准化要求")
    
    return {
        "score": min(1.0, consistency_score),
        "findings": findings
    }


def detect_role_definition(prompt: str) -> bool:
    """
    检测提示词中是否包含角色定义
    
    角色定义是一种提示词技术，通过给模型设定特定角色来引导其行为。
    
    Args:
        prompt: 待检测的提示词文本
        
    Returns:
        如果检测到角色定义则返回 True，否则返回 False
    """
    role_patterns: List[str] = [
        # 中文角色定义模式
        r'你是一个', r'你是一位', r'你是', r'作为一个', r'作为一位',
        r'你的角色是', r'你扮演', r'假设你是',
        r'你现在是', r'请以.*身份', r'以.*的角色',
        
        # 英文角色定义模式
        r'you are a', r'you are an', r'act as', r'acting as',
        r'your role is', r'pretend to be', r'imagine you are',
        r'as a', r'as an'
    ]
    
    return any(re.search(p, prompt, re.IGNORECASE) for p in role_patterns)


def analyze_scene_coverage(prompt: str) -> Dict[str, Any]:
    """
    分析提示词的场景覆盖度
    
    评估提示词是否覆盖了各种可能的输入场景和边界情况。
    
    Args:
        prompt: 待分析的提示词文本
        
    Returns:
        场景覆盖度分析结果字典
    """
    coverage_score: float = 0.5
    covered_aspects: List[str] = []
    missing_aspects: List[str] = []
    
    # 检查是否有边界情况说明
    edge_case_patterns: List[str] = [
        r'边界情况', r'特殊情况', r'极端情况', r'异常情况',
        r'edge case', r'corner case', r'special case'
    ]
    if any(re.search(p, prompt, re.IGNORECASE) for p in edge_case_patterns):
        coverage_score += 0.15
        covered_aspects.append("边界情况")
    else:
        missing_aspects.append("边界情况说明")
    
    # 检查是否有默认值/兜底策略
    fallback_patterns: List[str] = [
        r'默认', r'兜底', r'否则', r'其他情况',
        r'default', r'fallback', r'otherwise', r'else'
    ]
    if any(re.search(p, prompt, re.IGNORECASE) for p in fallback_patterns):
        coverage_score += 0.1
        covered_aspects.append("默认处理")
    else:
        missing_aspects.append("默认处理策略")
    
    # 检查是否有多场景示例
    if prompt.count('例') >= 2 or prompt.lower().count('example') >= 2:
        coverage_score += 0.1
        covered_aspects.append("多场景示例")
    else:
        missing_aspects.append("多场景示例")
    
    # 检查是否有输入类型说明
    input_type_patterns: List[str] = [
        r'输入类型', r'输入格式', r'用户输入',
        r'input type', r'input format'
    ]
    if any(re.search(p, prompt, re.IGNORECASE) for p in input_type_patterns):
        coverage_score += 0.1
        covered_aspects.append("输入类型说明")
    else:
        missing_aspects.append("输入类型说明")
    
    # 检查是否有错误处理说明
    error_handling_patterns: List[str] = [
        r'无法识别', r'无法判断', r'不确定时',
        r'cannot determine', r'unable to identify', r'uncertain'
    ]
    if any(re.search(p, prompt, re.IGNORECASE) for p in error_handling_patterns):
        coverage_score += 0.05
        covered_aspects.append("错误处理")
    else:
        missing_aspects.append("错误处理说明")
    
    return {
        "score": min(1.0, coverage_score),
        "covered_aspects": covered_aspects,
        "missing_aspects": missing_aspects
    }

