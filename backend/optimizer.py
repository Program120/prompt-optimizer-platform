from openai import OpenAI
import storage
from prompts import DEFAULT_OPTIMIZATION_PROMPT


def _build_error_samples_table(errors: list) -> str:
    """
    构造错误样例 Markdown 表格
    :param errors: 错误样例列表
    :return: Markdown 格式的表格字符串
    """
    table: str = "| 用户输入 | 预期输出 | 模型实际输出 |\n| :--- | :--- | :--- |\n"
    # 取前10个错误样例
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
        context: str = final_prompt.format(
            old_prompt=old_prompt,
            error_samples=error_samples_str
        )
    except KeyError as e:
        # 如果模板格式不对，回退到默认模板
        context = DEFAULT_OPTIMIZATION_PROMPT.format(
            old_prompt=old_prompt,
            error_samples=error_samples_str
        )
        print(f"Warning: Prompt template error {e}, using default.")
    
    return context


def optimize_prompt(
    old_prompt: str, 
    errors: list, 
    model_config: dict = None, 
    system_prompt_template: str = None
) -> str:
    """
    调用 LLM 优化提示词
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
    
    # 初始化 OpenAI 客户端
    client: OpenAI = OpenAI(
        api_key=model_config.get("api_key", ""),
        base_url=model_config.get("base_url", "https://api.openai.com/v1")
    )
    
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
        timeout=int(model_config.get("timeout", 60))
    )
    
    return response.choices[0].message.content.strip()
