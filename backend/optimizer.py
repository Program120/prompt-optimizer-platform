from openai import OpenAI
import os
import json
import storage

def optimize_prompt(old_prompt: str, errors: list, model_config: dict = None, system_prompt_template: str = None) -> str:
    """
    优化提示词
    :param old_prompt: 当前提示词
    :param errors: 错误样例列表
    :param model_config: 模型配置（从storage获取）
    :param system_prompt_template: 优化提示词模板 (可选)
    :return: 优化后的提示词
    :raises Exception: 如果优化失败则抛出异常
    """
    if not errors:
        return old_prompt
    
    # 使用传入的配置或从storage获取
    if not model_config:
        model_config = storage.get_model_config()
    
    # 初始化客户端
    client = OpenAI(
        api_key=model_config.get("api_key", ""),
        base_url=model_config.get("base_url", "https://api.openai.com/v1")
    )
        
    
    # 构造错误样例展示 (Markdown表格)
    error_samples_str = "| 用户输入 | 预期输出 | 模型实际输出 |\n| :--- | :--- | :--- |\n"
    for err in errors[:10]: # 取前10个错误样例
        # 简单处理换行符和管道符，避免表格乱掉
        query = str(err['query']).replace('\n', ' ').replace('|', '\|')
        target = str(err['target']).replace('\n', ' ').replace('|', '\|')
        output = str(err['output']).replace('\n', ' ').replace('|', '\|')
        error_samples_str += f"| {query} | {target} | {output} |\n"
    
    # 使用传入的模板或默认模板 (这里逻辑稍作调整，因为prompts.py在调用层使用)
    # 但为了保持函数纯净，这里假设调用方已经传好了完整的template或者我们在函数内部import
    from prompts import DEFAULT_OPTIMIZATION_PROMPT
    
    final_prompt = system_prompt_template if system_prompt_template else DEFAULT_OPTIMIZATION_PROMPT
    
    # 替换变量
    # 注意：我们的DEFAULT_PROMPT里已经是f-string格式的占位符 {old_prompt} 和 {error_samples}
    # 但因为它是字符串，我们需要用format来填充
    
    try:
        user_content = final_prompt.format(
            old_prompt=old_prompt,
            error_samples=error_samples_str
        )
    except KeyError as e:
        # 如果模板格式不对，回退到默认
        user_content = DEFAULT_OPTIMIZATION_PROMPT.format(
            old_prompt=old_prompt,
            error_samples=error_samples_str
        )
        print(f"Warning: Prompt template error {e}, using default.")

    # 这里的prompt构造有点变化：
    # 原来的逻辑是 system + user
    # 现在的 configurable prompt 看起来是一个整体的 prompt (包含了 content 和 instructions)
    # 所以我们将它作为 user message 发送 (或者 system message，取决于模型偏好，通常作为 User 发送任务指令也是可以的，或者拆分)
    # 鉴于 configurable prompt 包含 "你是一个..." 的角色定义，它更像是一个 System Message。
    # 但 OpenAI Chat 格式通常需要 User 提供具体输入。
    # 让用户配置的 prompt 作为一个完整的指令发给模型。
    
    # 为了简单且灵活，我们将整个构建好的内容作为 System Message 或者 User Message。
    # 考虑到通常优化任务是 "System: 你是优化师" + "User: 这是旧prompt和错误"，
    # 如果用户配置的是整个大段文本，我们可以把它放在 User 消息里，或者 System 消息里。
    # 让我们把 format 后的内容作为 User Message，System Message 可以是一个简单的 "You are a helpful assistant" 或者留空，
    # 或者，我们规定 configurable prompt 就是 System Message，然后 User Message 是 "Go/Start"。
    # *根据用户需求描述*： "把old_prompt, error_samples等变量作为系统默认变量"
    # 这意味着整个大段文本是一个模板。
    
    messages = [
        {"role": "system", "content": "You are a prompt optimization expert."}, # 保持一个通用的 system
        {"role": "user", "content": user_content}
    ]

    # 调用LLM
    response = client.chat.completions.create(
        model=model_config.get("model_name", "gpt-3.5-turbo"),
        messages=messages,
        temperature=float(model_config.get("temperature", 0.7)),
        max_tokens=int(model_config.get("max_tokens", 2000)),
        timeout=int(model_config.get("timeout", 60))
    )
    return response.choices[0].message.content.strip()

