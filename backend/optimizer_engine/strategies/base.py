"""策略基类定义"""
import asyncio
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class BaseStrategy(ABC):
    """优化策略基类"""
    
    name: str = "base"
    priority: int = 0
    description: str = ""

    @property
    def strategy_name(self) -> str:
        return self.name
        
    def __init__(
        self, 
        llm_client=None, 
        model_config: Dict[str, Any] = None,
        semaphore: Optional[asyncio.Semaphore] = None
    ):
        """
        初始化策略基类
        
        :param llm_client: LLM 客户端实例
        :param model_config: 模型配置
        :param semaphore: 并发控制信号量（用于限制 LLM 调用并发数）
        """
        self.llm_client = llm_client
        self.model_config = model_config or {}
        self.semaphore = semaphore
    
    @abstractmethod
    def apply(
        self, 
        prompt: str, 
        errors: List[Dict[str, Any]], 
        diagnosis: Dict[str, Any]
    ) -> str:
        """
        应用策略优化提示词
        
        Args:
            prompt: 当前提示词
            errors: 错误样例列表
            diagnosis: 诊断分析结果
            
        Returns:
            优化后的提示词
        """
        pass
    
    def is_applicable(self, diagnosis: Dict[str, Any]) -> bool:
        """
        判断该策略是否适用于当前诊断结果
        
        Args:
            diagnosis: 诊断分析结果
            
        Returns:
            是否适用
        """
        return True
    
    def get_priority(self, diagnosis: Dict[str, Any]) -> int:
        """根据诊断结果动态计算优先级"""
        return self.priority

    def _meta_optimize(
        self,
        prompt: str,
        error_cases: List[Dict[str, Any]],
        instruction: str,
        conservative: bool = True,
        diagnosis: Optional[Dict[str, Any]] = None,
        module_name: Optional[str] = None
    ) -> str:
        """
        基于特定指令进行元优化的通用方法 (Git Diff Mode)
        
        :param prompt: 当前提示词
        :param error_cases: 错误案例列表
        :param instruction: 优化指令
        :param conservative: 是否使用保守模式（保留原有结构）
        :param diagnosis: 诊断结果（可选，包含历史优化经验和新增失败案例）
        :param module_name: 可修改的模块名称（用于模块边界约束）
        :return: 优化后的提示词
        """
        import logging
        
        logger: logging.Logger = logging.getLogger(__name__)
        
        logger.info(f"[元优化] 开始执行，策略: {self.name}, 模块: {module_name or '无限制'}")
        logger.info(f"[元优化] 原始提示词长度: {len(prompt)} 字符")
        logger.info(f"[元优化] 错误案例数量: {len(error_cases)}")
        logger.debug(f"[元优化] 优化指令: {instruction[:200]}...")
        
        error_text: str = self._build_error_samples(error_cases)
        
        # 构建模块边界约束（前置到角色声明中）
        module_constraint: str = ""
        if module_name:
            module_constraint = f"""
> **[核心约束 - 请务必遵守]**
> 你只能修改「{module_name}」模块的内容。
> 严禁修改其他任何模块或部分，违反此约束将导致优化失败。
"""
        
        # 构建保守模式约束
        constraint_text: str = ""
        if conservative:
            constraint_text = f"""
## 严格约束条件
1. **模块边界**: {"只能修改「" + module_name + "」模块" if module_name else "保留提示词原有结构"}
2. **渐进改进**: 目标是小幅迭代，而非重写
3. **最小改动**: 总改动字符不要超过100字符
4. **禁止越界**: 绝对禁止修改其他模块的内容
"""
        
        # 构建历史优化经验章节
        history_section: str = ""
        if diagnosis:
            history_text: str = diagnosis.get("optimization_history_text", "")
            if history_text and history_text != "暂无历史优化记录":
                history_section = f"""
## 历史优化经验
以下是之前各版本的优化总结，请参考避免重复无效的修改：

{history_text}
"""
                logger.info(f"[元优化] 已注入历史优化经验，长度: {len(history_text)} 字符")
        
        # 构建新增失败案例章节（去空格后原样输出）
        newly_failed_section: str = ""
        if diagnosis:
            newly_failed_cases: Optional[List[Dict[str, Any]]] = diagnosis.get(
                "newly_failed_cases"
            )
            if newly_failed_cases and len(newly_failed_cases) > 0:
                lines: List[str] = [
                    "## 新增失败案例",
                    "以下案例在上一轮优化后变得失败，需要特别关注，避免类似的优化方向：",
                    ""
                ]
                for case in newly_failed_cases:
                    # 去除空格后原样输出
                    query: str = str(case.get("query", "")).strip()
                    target: str = str(case.get("target", "")).strip()
                    output: str = str(case.get("output", "")).strip()
                    lines.append(f"- Query: {query}")
                    lines.append(f"  Expected: {target} | Actual: {output}")
                newly_failed_section = "\n".join(lines) + "\n"
                logger.info(
                    f"[元优化] 已注入新增失败案例，数量: {len(newly_failed_cases)}"
                )
        
        # 构建自检提示（仅当指定了模块名时）
        self_check_section: str = ""
        if module_name:
            self_check_section = f"""
## 输出前自检（必须执行）
在输出每个 SEARCH/REPLACE 块之前，请确认：
1. SEARCH 块中的内容是否属于「{module_name}」模块？ → 必须为 Yes
2. REPLACE 块是否仅修改了「{module_name}」模块的内容？ → 必须为 Yes
3. 是否触及了其他模块（如角色定义、全局约束、输出格式等）？ → 必须为 No

**如果任一检查不通过，请放弃该修改，重新选择仅属于「{module_name}」模块的内容进行优化。**
"""
        
        optimization_prompt: str = f"""你是一个提示词模块优化专家。
{module_constraint}
请根据提供的具体指令和错误案例优化以下提示词。

## 当前提示词
{prompt}

## 错误案例
{error_text}
{history_section}{newly_failed_section}
## 优化指令
{instruction}
{constraint_text}
{self_check_section}
## 输出格式
1. **分析**：首先，逐步分析当前提示词和错误模式。识别根本原因并规划具体的改进措施。
2. **优化**：然后，输出用于应用更改的 Git Diff 块。

你必须使用 Search/Replace 块格式来修改提示词。
**严禁输出完整提示词**。仅输出修改的部分。

请严格遵守以下格式：
<<<<<<< SEARCH
[要从原始提示词中替换的确切文本]
=======
[用于替换的新文本]
>>>>>>>

SEARCH/REPLACE 规则：
1. **严格限制**: SEARCH 块中的内容必须**逐字逐句**地存在于"当前提示词"中，包括所有的空格、换行符和特殊字符。如果 SEARCH 内容找不到，Diff 将无法应用。
2. 严禁修改 SEARCH 块中的内容去"匹配"你想修改的地方，你必须复制原文。
3. 如果要插入文本，请 SEARCH 邻近的现有行，并在 REPLACE 中包含该行以及你的新文本。
4. 要删除文本，请将 REPLACE 块留空。
"""
        
        logger.info(f"[元优化] 构造优化 Prompt 完成，总长度: {len(optimization_prompt)} 字符")
        
        response_content: str = self._call_llm(optimization_prompt)
        
        # 记录原始模型输出
        logger.info(f"[元优化] LLM 响应长度: {len(response_content)} 字符")
        logger.info(f"[元优化] LLM 原始输出:\n{response_content}")
        
        # 应用 Diff
        try:
            logger.info("[元优化] 开始应用 Diff...")
            new_prompt: str = self._apply_diff(prompt, response_content)
            
            # 比较结果
            if new_prompt == prompt:
                logger.warning("[元优化] Diff 应用后提示词无变化！")
                
                # 检查 LLM 是否可能回退到了全量输出
                if len(response_content) > len(prompt) * 0.8:
                    logger.info("[元优化] 检测到 LLM 可能输出了完整提示词，尝试使用原始输出")
                    return response_content
            else:
                length_change: int = len(new_prompt) - len(prompt)
                logger.info(f"[元优化] Diff 应用成功！长度变化: {length_change:+d} 字符")
                logger.info(f"[元优化] 新提示词长度: {len(new_prompt)} 字符")
                
            return new_prompt
        except Exception as e:
            logger.error(f"[元优化] Diff 应用失败: {e}。回退到原始提示词。")
            # 可以在这里做 retry logic，请求全量输出
            # 暂时返回原 Prompt (或者我们可以考虑抛出异常让上层处理)
            return prompt

    def _apply_diff(self, original_text: str, diff_text: str) -> str:
        """
        应用 SEARCH/REPLACE Diff（增强版 - 支持多级模糊匹配）
        
        匹配策略优先级:
        1. 精确匹配
        2. 去除首尾空白后匹配
        3. 规范化空白符后匹配（多个空白符合并为单个空格）
        4. 正则模糊匹配（忽略空白符差异）
        5. 行锚点匹配（使用第一行作为锚点插入）
        
        :param original_text: 原始文本
        :param diff_text: 包含 SEARCH/REPLACE 块的 diff 文本
        :return: 应用修改后的文本
        """
        import re
        import logging
        
        logger: logging.Logger = logging.getLogger(__name__)
        
        # 正则匹配 SEARCH/REPLACE 块
        pattern = re.compile(
            r'<<<<<<< SEARCH\n(.*?)\n=======\n(.*?)\n>>>>>>>',
            re.DOTALL
        )
        
        blocks = pattern.findall(diff_text)
        if not blocks:
            # 尝试宽松匹配 (允许 SEARCH 后没有换行等)
            pattern_loose = re.compile(
                r'<<<<<<< SEARCH\s*(.*?)\s*=======\s*(.*?)\s*>>>>>>>',
                re.DOTALL
            )
            blocks = pattern_loose.findall(diff_text)
            
        logger.info(f"[Diff应用] 检测到 {len(blocks)} 个 SEARCH/REPLACE 块")
        
        if not blocks:
            logger.warning("[Diff应用] 未检测到任何 SEARCH/REPLACE 块，返回原始文本")
            return original_text
            
        current_text: str = original_text
        applied_count: int = 0
        
        for idx, (search_block, replace_block) in enumerate(blocks):
            block_num: int = idx + 1
            s_stripped: str = search_block.strip()
            r_stripped: str = replace_block.strip()
            
            logger.debug(f"[Diff应用] 块 {block_num} - SEARCH 预览: {s_stripped[:80]}...")
            logger.debug(f"[Diff应用] 块 {block_num} - REPLACE 预览: {r_stripped[:80]}...")
            
            # ========== 策略 1: 精确匹配 ==========
            if search_block in current_text:
                current_text = current_text.replace(search_block, replace_block, 1)
                applied_count += 1
                logger.info(f"[Diff应用] 块 {block_num} - 策略1(精确匹配) 成功")
                continue
                
            # ========== 策略 2: 去除首尾空白匹配 ==========
            if s_stripped and s_stripped in current_text:
                current_text = current_text.replace(s_stripped, r_stripped, 1)
                applied_count += 1
                logger.info(f"[Diff应用] 块 {block_num} - 策略2(去空白匹配) 成功")
                continue
            
            # ========== 策略 3: 规范化空白符匹配 ==========
            # 将多个连续空白符（包括换行）合并为单个空格后比较
            normalized_search: str = re.sub(r'\s+', ' ', s_stripped)
            normalized_text: str = re.sub(r'\s+', ' ', current_text)
            
            if normalized_search and normalized_search in normalized_text:
                logger.debug(f"[Diff应用] 块 {block_num} - 规范化搜索文本: {normalized_search[:50]}...")
                # 在原文中使用正则查找对应位置
                # 将搜索文本转换为允许空白符变化的正则模式
                escaped_parts: list = [re.escape(part) for part in s_stripped.split()]
                search_pattern: str = r'\s*'.join(escaped_parts)
                
                match = re.search(search_pattern, current_text, re.DOTALL)
                if match:
                    before: str = current_text[:match.start()]
                    after: str = current_text[match.end():]
                    current_text = before + r_stripped + after
                    applied_count += 1
                    logger.info(f"[Diff应用] 块 {block_num} - 策略3(规范化匹配) 成功，位置: {match.start()}-{match.end()}")
                    continue
                    
            # ========== 策略 4: 正则模糊匹配 ==========
            # 更宽松的正则：允许每个词之间有任意空白
            try:
                words: list = s_stripped.split()
                if len(words) >= 2:
                    # 只使用前几个词作为锚点
                    anchor_words: list = words[:min(5, len(words))]
                    fuzzy_pattern: str = r'\s+'.join([re.escape(w) for w in anchor_words])
                    
                    match = re.search(fuzzy_pattern, current_text, re.DOTALL)
                    if match:
                        # 检测 REPLACE 块是否已包含锚点内容（避免重复）
                        anchor_text: str = match.group(0)
                        if anchor_text in r_stripped:
                            # REPLACE 块已包含锚点，直接替换锚点位置
                            before: str = current_text[:match.start()]
                            # 跳过 after 中的锚点行，因为 REPLACE 已包含
                            after_start: int = match.end()
                            after: str = current_text[after_start:]
                            current_text = before + r_stripped + after
                            logger.info(f"[Diff应用] 块 {block_num} - 策略4(模糊匹配-替换模式) 成功")
                        else:
                            # REPLACE 块不包含锚点，在锚点前插入新内容
                            before: str = current_text[:match.start()]
                            after: str = current_text[match.start():]
                            current_text = before + r_stripped + "\n\n" + after
                            logger.info(f"[Diff应用] 块 {block_num} - 策略4(模糊匹配-插入模式) 成功")
                        applied_count += 1
                        continue
            except Exception as e:
                logger.warning(f"[Diff应用] 块 {block_num} - 策略4(模糊匹配) 异常: {e}")
                    
            # ========== 策略 5: 行锚点匹配 ==========
            # 使用 SEARCH 块的第一行非空行作为锚点
            search_lines: list = [line.strip() for line in s_stripped.split('\n') if line.strip()]
            if search_lines:
                first_line: str = search_lines[0]
                logger.debug(f"[Diff应用] 块 {block_num} - 尝试行锚点: {first_line[:50]}...")
                
                if first_line and first_line in current_text:
                    idx_anchor: int = current_text.find(first_line)
                    
                    # 检测 REPLACE 块是否已包含锚点行（避免重复）
                    if first_line in r_stripped:
                        # REPLACE 块已包含锚点行，需要跳过原文中的锚点行
                        before: str = current_text[:idx_anchor]
                        # 找到锚点行的结束位置
                        line_end: int = current_text.find('\n', idx_anchor)
                        if line_end == -1:
                            line_end = len(current_text)
                        after: str = current_text[line_end:]
                        current_text = before + r_stripped + after
                        logger.info(f"[Diff应用] 块 {block_num} - 策略5(行锚点-替换模式) 成功")
                    else:
                        # 在锚点行之前插入新内容
                        before: str = current_text[:idx_anchor]
                        after: str = current_text[idx_anchor:]
                        current_text = before + r_stripped + "\n\n" + after
                        logger.info(f"[Diff应用] 块 {block_num} - 策略5(行锚点-插入模式) 成功")
                    applied_count += 1
                    continue
            
            # ========== 所有策略失败 ==========
            logger.warning(f"[Diff应用] 块 {block_num} - 所有匹配策略均失败！")
            logger.warning(f"[Diff应用] 块 {block_num} - SEARCH 内容预览: {s_stripped[:100]}...")
            
        logger.info(f"[Diff应用] 完成: 共 {len(blocks)} 个块，成功应用 {applied_count} 个")
        
        return current_text

    def _build_error_samples(self, errors: List[Dict[str, Any]]) -> str:
        """构建错误样例文本"""
        if not errors:
            return "暂无错误案例"
        
        lines = []
        for e in errors[:5]:
            query = str(e.get('query', ''))[:200]
            lines.append(f"- 输入: {query}")
            lines.append(f"  预期: {e.get('target', '')} | 实际: {e.get('output', '')}\n")
        return "\n".join(lines)

    def _call_llm(self, prompt: str) -> str:
        """
        调用 LLM (同步方法，支持 AsyncOpenAI 和 OpenAI 客户端)
        
        支持信号量并发控制（如果在初始化时传入了 semaphore）
        
        :param prompt: 输入提示词
        :return: LLM 响应内容
        """
        import re
        import logging
        import asyncio
        import threading
        from openai import AsyncOpenAI
        
        logger: logging.Logger = logging.getLogger(__name__)
        
        if not self.llm_client:
            # Fallback for testing or if client not provided
            logger.warning("[LLM请求-策略优化] 未配置 LLM 客户端，返回原始提示词")
            return prompt
        
        # 记录 LLM 请求输入日志
        logger.info(f"[LLM请求-策略优化] 策略: {self.name}, 输入提示词长度: {len(prompt)} 字符")
        logger.debug(f"[LLM请求-策略优化] 输入内容:\n{prompt[:1000]}...")
        
        # 如果有信号量，记录并发信息
        if self.semaphore:
            logger.info(f"[LLM请求-策略优化] 策略: {self.name}, 使用共享信号量控制并发")
        
        try:
            model_name: str = self.model_config.get("model_name", "gpt-3.5-turbo")
            temperature: float = float(self.model_config.get("temperature", 0.7))
            max_tokens: int = int(self.model_config.get("max_tokens", 4000))
            timeout: int = int(self.model_config.get("timeout", 180))
            
            logger.info(f"[LLM请求-策略优化] 使用模型: {model_name}, temperature: {temperature}, max_tokens: {max_tokens}")
            
            # 判断客户端类型并选择正确的调用方式
            if isinstance(self.llm_client, AsyncOpenAI):
                # AsyncOpenAI 客户端需要异步调用
                # 在同步上下文中运行异步代码
                
                # 如果有信号量，需要使用 async with 获取信号量
                if self.semaphore:
                    async def _async_call_with_semaphore():
                        """
                        带信号量控制的异步调用 LLM
                        
                        :return: LLM 响应对象
                        """
                        async with self.semaphore:
                            logger.debug(f"[LLM请求-策略优化] 策略: {self.name}, 获取到信号量许可")
                            return await self.llm_client.chat.completions.create(
                                model=model_name,
                                messages=[
                                    {"role": "user", "content": prompt}
                                ],
                                temperature=temperature,
                                max_tokens=max_tokens,
                                timeout=timeout,
                                extra_body=self.model_config.get("extra_body")
                            )
                    _async_call = _async_call_with_semaphore
                else:
                    async def _async_call_no_semaphore():
                        """
                        异步调用 LLM（无信号量控制）
                        
                        :return: LLM 响应对象
                        """
                        return await self.llm_client.chat.completions.create(
                            model=model_name,
                            messages=[
                                {"role": "user", "content": prompt}
                            ],
                            temperature=temperature,
                            max_tokens=max_tokens,
                            timeout=timeout,
                            extra_body=self.model_config.get("extra_body")
                        )
                    _async_call = _async_call_no_semaphore
                
                # 检查是否有正在运行的事件循环
                try:
                    loop = asyncio.get_running_loop()
                    # 有运行中的循环，使用 nest_asyncio 或创建新线程
                    import concurrent.futures
                    
                    # 如果有信号量，需要在同一个事件循环中运行
                    # 使用 run_coroutine_threadsafe 在当前循环中调度协程
                    if self.semaphore:
                        future = asyncio.run_coroutine_threadsafe(_async_call(), loop)
                        response = future.result(timeout=timeout + 10)
                    else:
                        def run_in_new_loop():
                            """
                            在新的事件循环中运行异步代码
                            
                            :return: LLM 响应对象
                            """
                            new_loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(new_loop)
                            try:
                                return new_loop.run_until_complete(_async_call())
                            finally:
                                new_loop.close()
                        
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(run_in_new_loop)
                            response = future.result(timeout=timeout + 10)
                        
                except RuntimeError:
                    # 没有运行中的循环，可以直接运行
                    response = asyncio.run(_async_call())
            else:
                # 同步 OpenAI 客户端，直接调用
                response = self.llm_client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout,
                    extra_body=self.model_config.get("extra_body")
                )

            content: str = response.choices[0].message.content.strip()
            
            # 记录 LLM 原始响应日志
            logger.info(f"[LLM响应-策略优化] 策略: {self.name}, 原始输出长度: {len(content)} 字符")
            logger.debug(f"[LLM响应-策略优化] 原始输出内容:\n{content[:1000]}...")
            
            # 清理可能的 <think> 标签 (DeepSeek R1 等)
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            
            # 清理可能的 markdown 代码块标记 (如果 LLM 包裹了代码块)
            if content.startswith("```") and content.endswith("```"):
                lines = content.split('\n')
                if len(lines) >= 2:
                    content = '\n'.join(lines[1:-1])
            
            # 记录处理后的输出
            logger.info(f"[LLM响应-策略优化] 策略: {self.name}, 处理后输出长度: {len(content.strip())} 字符")
            
            return content.strip()
        except Exception as e:
            # Log error separately if possible, here we just return original prompt or re-raise
            logger.error(f"[LLM请求-策略优化] 策略: {self.name}, 调用失败: {e}")
            raise e

