"""
历史消息格式化工具
用于多轮验证时构建历史上下文
"""
import uuid
import pandas as pd
from typing import List, Dict, Any, Optional
from loguru import logger


class HistoryFormatter:
    """
    历史消息格式化器
    负责构建多轮对话的历史上下文
    """

    @staticmethod
    def generate_session_id() -> str:
        """
        生成唯一的会话 ID

        :return: UUID 格式的会话 ID
        """
        return str(uuid.uuid4())

    @staticmethod
    def build_history_from_responses(
        previous_rounds: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """
        从之前轮次的响应构建历史消息

        注意：在新设计中，历史消息是在任务执行过程中动态构建的，
        每轮完成后从 API 响应中提取 assistant 回复，添加到历史中。
        此方法用于将已收集的轮次数据转换为标准历史格式。

        :param previous_rounds: 之前轮次的数据列表
            格式: [{"query": "...", "response": "..."}, ...]
        :return: 历史消息列表
            格式: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
        """
        history: List[Dict[str, str]] = []

        for round_data in previous_rounds:
            query = round_data.get("query", "")
            response = round_data.get("response", "")

            if query:
                history.append({
                    "role": "user",
                    "content": query
                })

            if response:
                history.append({
                    "role": "assistant",
                    "content": response
                })

        return history

    @staticmethod
    def get_current_round_data(
        row_data: Dict[str, Any],
        round_config: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        获取当前轮次的 query 和 target

        :param row_data: 当前行数据
        :param round_config: 当前轮次配置
            格式: {"round": N, "query_col": "queryN", "target_col": "targetN"}
        :return: 包含 query 和 target 的字典
        """
        query_col = round_config.get("query_col", "")
        target_col = round_config.get("target_col", "")

        query = ""
        target = ""

        # 获取 query
        if query_col and query_col in row_data:
            val = row_data.get(query_col)
            if val is not None and not pd.isna(val):
                query = str(val).strip()

        # 获取 target
        if target_col and target_col in row_data:
            val = row_data.get(target_col)
            if val is not None and not pd.isna(val):
                target = str(val).strip()

        return {"query": query, "target": target}

    @staticmethod
    def validate_rounds_config(rounds_config: List[Dict[str, Any]]) -> bool:
        """
        验证轮次配置的有效性

        新设计：每轮都需要 query_col 和 target_col（每轮都验证意图）

        :param rounds_config: 轮次配置列表
            格式: [{"round": 1, "query_col": "query1", "target_col": "target1"}, ...]
        :return: 是否有效
        """
        if not rounds_config or not isinstance(rounds_config, list):
            logger.warning("轮次配置为空或格式错误")
            return False

        for idx, cfg in enumerate(rounds_config):
            if not isinstance(cfg, dict):
                logger.warning(f"轮次配置[{idx}]不是字典格式")
                return False

            # 检查必需字段：每轮都需要 round, query_col, target_col
            if "round" not in cfg or "query_col" not in cfg or "target_col" not in cfg:
                logger.warning(f"轮次配置[{idx}]缺少必需字段 (round, query_col, target_col)")
                return False

            # 检查字段值不为空
            if not cfg.get("query_col") or not cfg.get("target_col"):
                logger.warning(f"轮次配置[{idx}]的 query_col 或 target_col 为空")
                return False

        return True

    @staticmethod
    def parse_rounds_config_from_json(config_json: str) -> List[Dict[str, Any]]:
        """
        从 JSON 字符串解析轮次配置

        :param config_json: JSON 字符串
        :return: 轮次配置列表
        """
        import json

        try:
            rounds_config = json.loads(config_json)
            if not isinstance(rounds_config, list):
                logger.warning("轮次配置 JSON 不是列表格式")
                return []
            return rounds_config
        except json.JSONDecodeError as e:
            logger.error(f"解析轮次配置 JSON 失败: {e}")
            return []
