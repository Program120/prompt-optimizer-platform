"""LLM 调用辅助模块 - 封装异步 LLM 调用和取消逻辑"""
import asyncio
import logging
import re
from typing import Dict, Any, Optional, Callable
from openai import AsyncOpenAI, OpenAI
from .cancellation import run_with_cancellation


class LLMHelper:
    """
    LLM 调用辅助类
    
    封装所有 LLM 调用相关逻辑，支持：
    - 异步调用（AsyncOpenAI / OpenAI）
    - 并发控制（信号量）
    - 可取消调用
    """
    
    def __init__(
        self, 
        llm_client=None, 
        model_config: Dict[str, Any] = None,
        semaphore: Optional[asyncio.Semaphore] = None,
        should_stop_callback: Optional[Callable[[], bool]] = None
    ):
        """
        初始化 LLM 辅助类
        
        :param llm_client: LLM 客户端实例（支持 AsyncOpenAI 或 OpenAI）
        :param model_config: 模型配置字典
        :param semaphore: 并发控制信号量
        :param should_stop_callback: 停止回调函数
        """
        self.llm_client = llm_client
        self.model_config: Dict[str, Any] = model_config or {}
        self.semaphore: asyncio.Semaphore = semaphore or asyncio.Semaphore(5)
        self._should_stop: Optional[Callable[[], bool]] = should_stop_callback
        self.logger: logging.Logger = logging.getLogger(__name__)
    
    def set_should_stop(self, callback: Optional[Callable[[], bool]]) -> None:
        """
        设置停止回调函数
        
        :param callback: 停止回调函数
        """
        self._should_stop = callback
    
    async def call_llm_async(
        self, 
        prompt: str,
        override_client: Any = None,
        override_config: Dict[str, Any] = None
    ) -> str:
        """
        异步调用 LLM（支持 AsyncOpenAI 和 OpenAI 客户端）
        自动处理并发控制和超时
        
        :param prompt: 输入提示词
        :param override_client: 覆盖使用的 LLM 客户端
        :param override_config: 覆盖使用的模型配置
        :return: LLM 响应内容
        """
        # 确定使用的 config 和 client
        config: Dict[str, Any] = override_config or self.model_config
        client = override_client or self.llm_client
        
        model_name: str = config.get("model_name", "gpt-3.5-turbo")
        temperature: float = float(config.get("temperature", 0.7))
        max_tokens: int = int(config.get("max_tokens", 4000))
        timeout: int = int(config.get("timeout", 60))
        extra_body: Dict = config.get("extra_body", {})
        
        # 记录 LLM 请求输入日志
        self.logger.info(
            f"[LLM请求] 输入提示词长度: {len(prompt)} 字符 "
            f"(Model: {model_name}, Timeout: {timeout}s)"
        )
        self.logger.debug(f"[LLM请求] 输入内容: {prompt[:500]}...")
        
        async with self.semaphore:
            try:
                # 情况 1: 异步客户端（推荐）
                if isinstance(client, AsyncOpenAI):
                    response = await client.chat.completions.create(
                        model=model_name,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=temperature,
                        max_tokens=max_tokens,
                        timeout=timeout,
                        extra_body=extra_body
                    )
                    result: str = response.choices[0].message.content.strip()
                    
                # 情况 2: 同步客户端（兼容旧代码）
                else:
                    loop = asyncio.get_running_loop()
                    
                    def run_sync() -> Any:
                        """在事件循环中运行同步 LLM 调用"""
                        return client.chat.completions.create(
                            model=model_name,
                            messages=[{"role": "user", "content": prompt}],
                            temperature=temperature,
                            max_tokens=max_tokens,
                            timeout=timeout,
                            extra_body=extra_body
                        )
                    
                    response = await loop.run_in_executor(None, run_sync)
                    result: str = response.choices[0].message.content.strip()

                # 处理推理模型的 <think> 标签
                result = re.sub(
                    r'<think>.*?</think>', 
                    '', 
                    result, 
                    flags=re.DOTALL
                ).strip()
                
                # 记录 LLM 响应输出日志
                self.logger.info(f"[LLM响应] 输出长度: {len(result)} 字符")
                self.logger.debug(f"[LLM响应] 输出内容: {result[:500]}...")
                
                return result

            except Exception as e:
                self.logger.error(f"[LLM请求] 调用失败: {e}")
                # 检查是否超时以提供更明确的警告
                if "timeout" in str(e).lower():
                    self.logger.error(
                        f"LLM 请求超时 ({timeout}s). "
                        f"请考虑在模型配置中增加 timeout 值或检查网络。"
                    )
                return ""

    async def call_llm_with_cancellation(
        self, 
        prompt: str,
        should_stop: Optional[Callable[[], bool]] = None,
        check_interval: float = 0.5,
        task_name: str = "LLM调用",
        override_client: Any = None,
        override_config: Dict[str, Any] = None
    ) -> str:
        """
        可取消的 LLM 调用
        
        使用 run_with_cancellation 包装 LLM 调用，使其能够在收到停止信号后立即响应
        
        :param prompt: 输入提示词
        :param should_stop: 停止回调函数
        :param check_interval: 检查停止信号的间隔（秒）
        :param task_name: 任务名称（用于日志）
        :param override_client: 覆盖使用的 LLM 客户端
        :param override_config: 覆盖使用的模型配置
        :return: LLM 响应内容
        """
        # 优先使用传入的回调，否则使用实例变量
        stop_func: Optional[Callable[[], bool]] = should_stop or self._should_stop
        
        if stop_func is None:
            # 没有停止回调，直接调用原始方法
            return await self.call_llm_async(prompt, override_client, override_config)
        
        try:
            result: str = await run_with_cancellation(
                self.call_llm_async(prompt, override_client, override_config),
                should_stop=stop_func,
                check_interval=check_interval,
                task_name=task_name
            )
            return result
        except asyncio.CancelledError:
            self.logger.info(f"[LLM调用] {task_name} 被用户取消")
            return ""
        except Exception as e:
            self.logger.error(f"[LLM调用] {task_name} 失败: {e}")
            return ""
