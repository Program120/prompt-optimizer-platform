"""
提示词优化模块

提供两种优化模式：
1. optimize_prompt() - 原有的单次LLM优化（向后兼容）
2. multi_strategy_optimize() - 新的多策略优化引擎
"""
import re
from typing import Any, Dict, List, Optional

from loguru import logger

from app.core.llm_factory import LLMFactory
from app.core.prompts import DEFAULT_OPTIMIZATION_PROMPT
from app.db import storage
# 导入多策略优化模块
from app.engine import MultiStrategyOptimizer


def _build_error_samples_table(errors: List[Dict[str, Any]]) -> str:
    """
    构造错误样例 Markdown 表格
    :param errors: 错误样例列表
    :return: Markdown 格式的表格字符串
    """
    table: str = "| 用户输入 | 预期输出 | 模型实际输出 |\n| :--- | :--- | :--- |\n"
    # 取前x个错误样例
    for err in errors[:]:
        # 处理换行符和管道符，避免表格格式错乱
        query: str = str(err.get('query', '')).replace('\n', ' ').replace('|', '\\|')
        target: str = str(err.get('target', '')).replace('\n', ' ').replace('|', '\\|')
        output: str = str(err.get('output', '')).replace('\n', ' ').replace('|', '\\|')
        table += f"| {query} | {target} | {output} |\n"
    return table


def generate_optimize_context(
    old_prompt: str, 
    errors: List[Dict[str, Any]], 
    system_prompt_template: Optional[str] = None
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
        logger.warning(f"Prompt template replace error {e}, using default.")
        context = DEFAULT_OPTIMIZATION_PROMPT.replace("{old_prompt}", old_prompt).replace("{error_samples}", error_samples_str)
    
    return context


def optimize_prompt(
    old_prompt: str, 
    errors: List[Dict[str, Any]], 
    model_config: Optional[Dict[str, Any]] = None, 
    system_prompt_template: Optional[str] = None
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
    logger.info("开始执行单次提示词优化 (optimize_prompt)")
    if not errors:
        logger.info("无错误样例，跳过优化")
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
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": "You are a prompt optimization expert."},
        {"role": "user", "content": user_content}
    ]

    # 调用 LLM
    logger.debug(f"Calling LLM for optimization with model: {model_config.get('model_name', 'gpt-3.5-turbo')}")
    try:
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
        
        logger.info("单次提示词优化完成")
        return response_content
    except Exception as e:
        logger.error(f"LLM call failed in optimize_prompt: {e}")
        raise


async def multi_strategy_optimize(
    old_prompt: str,
    errors: List[Dict[str, Any]],
    model_config: Optional[Dict[str, Any]] = None,
    dataset: Optional[List[Dict[str, Any]]] = None,
    total_count: Optional[int] = None,
    strategy_mode: str = "auto",
    max_strategies: int = 1,
    project_id: Optional[str] = None,
    should_stop: Any = None,
    newly_failed_cases: Optional[List[Dict[str, Any]]] = None,
    verification_config: Optional[Dict[str, Any]] = None,
    selected_modules: Optional[List[str]] = None,
    on_progress: Any = None
) -> Dict[str, Any]:
    """
    使用多策略优化引擎优化提示词
    
    :param old_prompt: 当前提示词
    :param errors: 错误样例列表
    :param model_config: 模型配置（用于优化生成）
    :param dataset: 完整数据集（可选，用于few-shot选择）
    :param total_count: 总样本数（用于计算准确率）
    :param strategy_mode: 策略模式 (auto, initial, precision_focus, recall_focus, advanced)
    :param max_strategies: 最多应用的策略数量
    :param project_id: 项目ID（用于知识库记录，可选）
    :param should_stop: 停止信号检查函数
    :param newly_failed_cases: 新增的失败案例（可选）
    :param verification_config: 验证模型配置（用于评估效果，可选）
    :param selected_modules: 用户选择的标准模块ID列表（可选）
    :param on_progress: 进度回调函数（可选）
    :return: 优化结果字典，包含 optimized_prompt, diagnosis, applied_strategies, message
    """
    logger.info(f"开始执行多策略优化: ProjectID={project_id}, Mode={strategy_mode}")
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
    
    # 创建主要 LLM 客户端 (优化用)
    client = LLMFactory.create_async_client(model_config)

    # 创建验证专用 LLM 客户端 (如有)
    verification_client = None
    if verification_config:
        verification_client = LLMFactory.create_async_client(verification_config)
    
    # 创建多策略优化器
    optimizer = MultiStrategyOptimizer(
        llm_client=client,
        model_config=model_config,
        verification_llm_client=verification_client,
        verification_model_config=verification_config
    )
    
    # 执行优化（传入 project_id 以启用知识库功能）
    try:
        result = await optimizer.optimize(
            prompt=old_prompt,
            errors=errors,
            dataset=dataset,
            total_count=total_count,
            strategy_mode=strategy_mode,
            max_strategies=max_strategies,
            project_id=project_id,
            should_stop=should_stop,
            newly_failed_cases=newly_failed_cases,
            selected_modules=selected_modules,
            on_progress=on_progress
        )
        logger.info("多策略优化执行完成")
        return result
    except Exception as e:
        logger.error(f"多策略优化执行失败: {e}")
        raise


def diagnose_and_get_recommendations(
    old_prompt: str,
    errors: List[Dict[str, Any]],
    total_count: Optional[int] = None,
    project_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    诊断提示词性能并获取优化建议
    
    :param old_prompt: 当前提示词
    :param errors: 错误样例列表
    :param total_count: 总样本数（用于计算准确率）
    :param project_id: 项目ID（可选）
    :return: 诊断结果和推荐策略
    """
    logger.info(f"开始诊断提示词: ProjectID={project_id}")
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
    
    try:
        diagnosis = optimizer.diagnose(old_prompt, errors, total_count, project_id=project_id)
        recommendations = optimizer.get_recommended_strategies(diagnosis)
        
        logger.info(f"诊断完成，推荐 {len(recommendations)} 个优化策略")
        return {
            "diagnosis": diagnosis,
            "recommendations": recommendations,
            "message": f"诊断完成，推荐 {len(recommendations)} 个优化策略"
        }
    except Exception as e:
        logger.error(f"提示词诊断失败: {e}")
        raise
