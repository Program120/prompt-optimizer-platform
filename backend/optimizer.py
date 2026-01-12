"""
提示词优化模块

提供两种优化模式：
1. optimize_prompt() - 原有的单次LLM优化（向后兼容）
2. multi_strategy_optimize() - 新的多策略优化引擎
"""
from llm_factory import LLMFactory
import re
import storage
from prompts import DEFAULT_OPTIMIZATION_PROMPT

# 导入多策略优化模块
from optimizer_engine import (
    MultiStrategyOptimizer,
    diagnose_prompt_performance
)


def _build_error_samples_table(errors: list) -> str:
    """
    构造错误样例 Markdown 表格
    :param errors: 错误样例列表
    :return: Markdown 格式的表格字符串
    """
    table: str = "| 用户输入 | 预期输出 | 模型实际输出 |\n| :--- | :--- | :--- |\n"
    # 取前300个错误样例
    for err in errors[:300]:
        # 处理换行符和管道符，避免表格格式错乱
        query: str = str(err.get('query', '')).replace('\n', ' ').replace('|', '\\|')
        target: str = str(err.get('target', '')).replace('\n', ' ').replace('|', '\\|')
        output: str = str(err.get('output', '')).replace('\n', ' ').replace('|', '\\|')
        table += f"| {query} | {target} | {output} |\n"
    return table


def generate_optimize_context(
    old_prompt: str, 
    errors: list, 
    system_prompt_template: str = None
) -> str:
    """
    生成优化上下文，用于外部优化功能和内部优化
    :param old_prompt: 当前提示词
    :param errors: 错误样例列表
    :param system_prompt_template: 优化提示词模板 (可选，为空则使用默认模板)
    :return: 格式化后的优化上下文
    """
    # 构造错误样例表格
    error_samples_str: str = _build_error_samples_table(errors)
    
    # 使用传入的模板或默认模板
    final_prompt: str = system_prompt_template if system_prompt_template else DEFAULT_OPTIMIZATION_PROMPT
    
    # 替换模板变量
    try:
        context = final_prompt.replace("{old_prompt}", old_prompt).replace("{error_samples}", error_samples_str)
    except Exception as e:
        context = DEFAULT_OPTIMIZATION_PROMPT.replace("{old_prompt}", old_prompt).replace("{error_samples}", error_samples_str)
        print(f"Warning: Prompt template replace error {e}, using default.")
    
    return context


def optimize_prompt(
    old_prompt: str, 
    errors: list, 
    model_config: dict = None, 
    system_prompt_template: str = None
) -> str:
    """
    调用 LLM 优化提示词（原有方法，向后兼容）
    :param old_prompt: 当前提示词
    :param errors: 错误样例列表
    :param model_config: 模型配置（可选，为空则从 storage 获取）
    :param system_prompt_template: 优化提示词模板 (可选)
    :return: 优化后的提示词
    :raises Exception: 如果优化失败则抛出异常
    """
    if not errors:
        return old_prompt
    
    # 使用传入的配置或从 storage 获取
    if not model_config:
        model_config = storage.get_model_config()
    
    # 使用 Factory 初始化 OpenAI 客户端
    client = LLMFactory.create_client(model_config)
    
    # 复用 generate_optimize_context 生成用户消息内容
    user_content: str = generate_optimize_context(
        old_prompt=old_prompt,
        errors=errors,
        system_prompt_template=system_prompt_template
    )
    
    # 构造消息列表
    messages: list = [
        {"role": "system", "content": "You are a prompt optimization expert."},
        {"role": "user", "content": user_content}
    ]

    # 调用 LLM
    response = client.chat.completions.create(
        model=model_config.get("model_name", "gpt-3.5-turbo"),
        messages=messages,
        temperature=float(model_config.get("temperature", 0.7)),
        max_tokens=int(model_config.get("max_tokens", 2000)),
        timeout=int(model_config.get("timeout", 60)),
        extra_body=model_config.get("extra_body")
    )
    
    response_content = response.choices[0].message.content.strip()
    
    # Process <think> tags for reasoning models
    response_content = re.sub(r'<think>.*?</think>', '', response_content, flags=re.DOTALL).strip()
    
    return response_content


async def multi_strategy_optimize(
    old_prompt: str,
    errors: list,
    model_config: dict = None,
    dataset: list = None,
    total_count: int = None,
    strategy_mode: str = "auto",
    max_strategies: int = 1
) -> dict:
    """
    使用多策略优化引擎优化提示词
    
    :param old_prompt: 当前提示词
    :param errors: 错误样例列表
    :param model_config: 模型配置（可选）
    :param dataset: 完整数据集（可选，用于few-shot选择）
    :param total_count: 总样本数（用于计算准确率）
    :param strategy_mode: 策略模式 (auto, initial, precision_focus, recall_focus, advanced)
    :param max_strategies: 最多应用的策略数量
    :return: 优化结果字典，包含 optimized_prompt, diagnosis, applied_strategies, message
    """
    if not errors:
        return {
            "optimized_prompt": old_prompt,
            "diagnosis": None,
            "applied_strategies": [],
            "message": "无错误样例，无需优化"
        }
    
    # 使用传入的配置或从 storage 获取
    if not model_config:
        model_config = storage.get_model_config()
    
    # 创建 LLM 客户端
    client = LLMFactory.create_client(model_config)
    
    # 创建多策略优化器
    optimizer = MultiStrategyOptimizer(
        llm_client=client,
        model_config=model_config
    )
    
    # 执行优化
    result = await optimizer.optimize(
        prompt=old_prompt,
        errors=errors,
        dataset=dataset,
        total_count=total_count,
        strategy_mode=strategy_mode,
        max_strategies=max_strategies
    )
    
    return result


def diagnose_and_get_recommendations(
    old_prompt: str,
    errors: list,
    total_count: int = None
) -> dict:
    """
    诊断提示词性能并获取优化建议
    
    :param old_prompt: 当前提示词
    :param errors: 错误样例列表
    :param total_count: 总样本数（用于计算准确率）
    :return: 诊断结果和推荐策略
    """
    if not errors:
        return {
            "diagnosis": None,
            "recommendations": [],
            "message": "无错误样例，无需诊断"
        }
    
    # 获取模型配置
    model_config = storage.get_model_config()
    client = LLMFactory.create_client(model_config)
    
    # 创建优化器并诊断
    optimizer = MultiStrategyOptimizer(
        llm_client=client,
        model_config=model_config
    )
    
    diagnosis = optimizer.diagnose(old_prompt, errors, total_count)
    recommendations = optimizer.get_recommended_strategies(diagnosis)
    
    return {
        "diagnosis": diagnosis,
        "recommendations": recommendations,
        "message": f"诊断完成，推荐 {len(recommendations)} 个优化策略"
    }
