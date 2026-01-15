"""
诊断模块 - 检测器组件
包含各种针对提示词和错误案例的特定检测函数
"""
import re
from typing import List, Dict, Any, Tuple
from collections import defaultdict, Counter

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


def detect_role_definition(prompt: str) -> bool:
    """
    检测提示词中是否包含角色定义
    
    角色定义是一种提示词技术，通过给模型设定特定角色来引导其行为。
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


def detect_format_errors(errors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    检测错误案例中的格式错误
    
    格式错误指输出格式不符合预期的情况，例如应该输出单个标签却输出了多个，
    或者输出中包含了多余的标点、空格等格式问题。
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


def analyze_constraint_clarity(prompt: str) -> float:
    """
    分析提示词中约束条件的清晰度
    评估提示词中的约束条件是否明确、具体、可执行。
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

def analyze_scene_coverage(prompt: str) -> Dict[str, Any]:
    """
    分析提示词的场景覆盖度
    
    评估提示词是否覆盖了各种可能的输入场景和边界情况。
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
