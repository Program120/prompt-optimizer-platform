"""
取消令牌模块 - 提供跨协程传递停止信号的机制

用于在多策略优化器的各个阶段传递停止信号，实现立即响应停止请求
"""
import asyncio
import logging
from typing import Callable, Any, Optional, Coroutine

# 获取日志记录器
logger: logging.Logger = logging.getLogger(__name__)


class CancellationToken:
    """
    可取消令牌 - 用于跨协程传递停止信号
    
    封装停止检查逻辑，提供统一的取消检查接口
    """
    
    def __init__(self, should_stop_func: Callable[[], bool] = None):
        """
        初始化取消令牌
        
        :param should_stop_func: 外部停止检查回调函数
        """
        self._cancelled: bool = False
        self._should_stop: Callable[[], bool] = should_stop_func
        
    def is_cancelled(self) -> bool:
        """
        检查是否已取消
        
        优先检查内部标志，然后检查外部回调
        
        :return: 是否已取消
        """
        if self._cancelled:
            return True
        if self._should_stop and self._should_stop():
            self._cancelled = True
            return True
        return False
        
    def cancel(self) -> None:
        """
        主动设置取消标志
        """
        self._cancelled = True


async def run_with_cancellation(
    coro: Coroutine,
    should_stop: Callable[[], bool] = None,
    check_interval: float = 0.1,
    task_name: str = "未命名任务"
) -> Any:
    """
    包装协程使其支持取消
    
    使用 asyncio.wait + FIRST_COMPLETED 模式，同时等待目标协程和停止信号监控任务
    
    :param coro: 要执行的协程
    :param should_stop: 停止回调函数
    :param check_interval: 检查停止信号的间隔（秒）
    :param task_name: 任务名称（用于日志）
    :return: 协程返回值
    :raises asyncio.CancelledError: 如果收到停止信号
    """
    if should_stop is None:
        # 如果没有停止回调，直接执行
        return await coro
    
    # 创建目标任务
    target_task: asyncio.Task = asyncio.create_task(coro)
    
    # 创建停止监控任务
    async def monitor_stop() -> str:
        """
        监控停止信号的协程
        """
        while True:
            await asyncio.sleep(check_interval)
            if should_stop():
                return "CANCELLED"
    
    monitor_task: asyncio.Task = asyncio.create_task(monitor_stop())
    
    try:
        # 等待任意一个任务完成
        done, pending = await asyncio.wait(
            {target_task, monitor_task},
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # 取消所有未完成的任务
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        # 检查是哪个任务完成了
        for task in done:
            if task == target_task:
                # 目标任务完成，返回结果
                return task.result()
            elif task == monitor_task:
                # 监控任务完成，说明收到了停止信号
                logger.info(f"任务 '{task_name}' 因收到停止信号被取消")
                raise asyncio.CancelledError(f"任务 '{task_name}' 被用户停止")
                
    except Exception as e:
        # 确保清理所有任务
        if not target_task.done():
            target_task.cancel()
            try:
                await target_task
            except asyncio.CancelledError:
                pass
        if not monitor_task.done():
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass
        raise e
    
    return None


async def gather_with_cancellation(
    *coros: Coroutine,
    should_stop: Callable[[], bool] = None,
    check_interval: float = 0.1,
    return_exceptions: bool = True
) -> list:
    """
    可取消的 asyncio.gather 替代实现
    
    在等待多个协程的同时监控停止信号，收到信号后取消所有未完成任务
    
    :param coros: 要执行的协程列表
    :param should_stop: 停止回调函数
    :param check_interval: 检查停止信号的间隔（秒）
    :param return_exceptions: 是否将异常作为结果返回
    :return: 所有协程的结果列表
    """
    if should_stop is None:
        return await asyncio.gather(*coros, return_exceptions=return_exceptions)
    
    # 创建所有任务
    tasks: list[asyncio.Task] = [asyncio.create_task(c) for c in coros]
    
    # 创建停止监控任务
    async def monitor_stop() -> None:
        while True:
            await asyncio.sleep(check_interval)
            if should_stop():
                logger.info("gather_with_cancellation: 收到停止信号，取消所有任务...")
                for task in tasks:
                    if not task.done():
                        task.cancel()
                return
    
    monitor_task: asyncio.Task = asyncio.create_task(monitor_stop())
    
    try:
        # 等待所有目标任务完成
        results = await asyncio.gather(*tasks, return_exceptions=return_exceptions)
        
        # 取消监控任务
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
            
        return results
        
    except Exception as e:
        # 确保清理
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
        raise e
