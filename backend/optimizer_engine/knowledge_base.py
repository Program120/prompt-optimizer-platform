"""
优化知识库模块 - 记录每个版本的优化内容和分析

功能：
1. 记录每次优化的版本信息、分析结果和 LLM 总结
2. 提供历史优化记录查询
3. 为下一次优化提供历史参考
"""
import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import difflib


class OptimizationKnowledgeBase:
    """
    优化知识库 - 记录每个版本的优化内容和分析
    
    按项目存储优化历史，每次优化记录包含：
    - 版本号
    - 原始/优化后的提示词
    - LLM 生成的优化总结
    - 意图分析数据
    - 应用的策略
    - 优化前后准确率
    """
    
    # 知识库存储目录
    KNOWLEDGE_BASE_DIR: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
        "data", 
        "knowledge_base"
    )
    
    def __init__(self, project_id: str):
        """
        初始化知识库
        
        :param project_id: 项目ID，用于隔离不同项目的优化历史
        """
        self.project_id: str = project_id
        self.logger: logging.Logger = logging.getLogger(__name__)
        
        # 确保目录存在
        self._ensure_dir()
        
    def _ensure_dir(self) -> None:
        """确保知识库目录存在"""
        if not os.path.exists(self.KNOWLEDGE_BASE_DIR):
            os.makedirs(self.KNOWLEDGE_BASE_DIR)
            
    def _get_file_path(self) -> str:
        """
        获取当前项目的知识库文件路径
        
        :return: 知识库 JSON 文件的完整路径
        """
        return os.path.join(
            self.KNOWLEDGE_BASE_DIR, 
            f"kb_{self.project_id}.json"
        )
        
    def _load_history(self) -> List[Dict[str, Any]]:
        """
        加载项目的优化历史记录
        
        :return: 优化历史记录列表
        """
        file_path: str = self._get_file_path()
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"加载知识库失败: {e}")
                return []
        return []
        
    def _save_history(self, history: List[Dict[str, Any]]) -> None:
        """
        保存优化历史记录
        
        :param history: 优化历史记录列表
        """
        file_path: str = self._get_file_path()
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"保存知识库失败: {e}")
            
    def record_optimization(
        self,
        original_prompt: str,
        optimized_prompt: str,
        analysis_summary: str,
        intent_analysis: Dict[str, Any],
        applied_strategies: List[str],
        accuracy_before: float,
        accuracy_after: Optional[float] = None,
        deep_analysis: Optional[Dict[str, Any]] = None,
        newly_failed_cases: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        记录一次优化
        
        :param original_prompt: 优化前的提示词
        :param optimized_prompt: 优化后的提示词
        :param analysis_summary: LLM 生成的优化总结
        :param intent_analysis: 意图分析数据
        :param applied_strategies: 应用的策略列表
        :param accuracy_before: 优化前准确率
        :param accuracy_after: 优化后准确率（可选，可后续更新）
        :param deep_analysis: 深度分析数据（可选）
        :param newly_failed_cases: 新增的失败案例（上一轮成功，本轮失败）（可选）
        :return: 保存的优化记录
        """
        # 加载历史记录
        history: List[Dict[str, Any]] = self._load_history()
        
        # 生成版本号（递增）
        version: int = len(history) + 1
        
        # 构建优化记录
        record: Dict[str, Any] = {
            "version": version,
            "timestamp": datetime.now().isoformat(),
            "original_prompt": original_prompt,
            "optimized_prompt": optimized_prompt,
            "analysis_summary": analysis_summary,
            "intent_analysis": intent_analysis,
            "deep_analysis": deep_analysis,
            "applied_strategies": applied_strategies,
            "accuracy_before": accuracy_before,
            "accuracy_after": accuracy_after,
            "newly_failed_cases": newly_failed_cases,
            "diff": self._compute_diff(original_prompt, optimized_prompt)
        }
        
        # 添加到历史记录
        history.append(record)
        
        # 保存
        self._save_history(history)
        
        self.logger.info(
            f"记录优化版本 {version}，项目: {self.project_id}"
        )
        
        return record
        
    def _compute_diff(self, original: str, optimized: str) -> str:
        """
        计算简单的文本差异
        """
        try:
            diff_lines = list(difflib.unified_diff(
                original.splitlines(),
                optimized.splitlines(),
                lineterm=''
            ))
            
            # 过滤掉 unified diff 的头部信息 (---, +++, @@)
            clean_diff = []
            for line in diff_lines:
                if line.startswith('---') or line.startswith('+++'):
                    continue
                clean_diff.append(line)
                
            return "\n".join(clean_diff).strip()
        except Exception as e:
            self.logger.warning(f"Diff 计算失败: {e}")
            return ""

        
    def update_accuracy_after(
        self, 
        version: int, 
        accuracy_after: float
    ) -> bool:
        """
        更新某个版本的优化后准确率
        
        :param version: 版本号
        :param accuracy_after: 优化后准确率
        :return: 是否更新成功
        """
        history: List[Dict[str, Any]] = self._load_history()
        
        for record in history:
            if record.get("version") == version:
                record["accuracy_after"] = accuracy_after
                record["updated_at"] = datetime.now().isoformat()
                self._save_history(history)
                return True
                
        return False
    
    def update_latest_accuracy_after(
        self,
        accuracy_after: float
    ) -> bool:
        """
        更新最新一条 accuracy_after 为 null 的记录
        
        此方法用于在任务完成后回填准确率：
        当一次任务执行完成后，用当前准确率更新上一条优化分析记录的 accuracy_after
        
        :param accuracy_after: 优化后准确率
        :return: 是否更新成功（如果没有待更新的记录则返回 False）
        """
        history: List[Dict[str, Any]] = self._load_history()
        
        if not history:
            return False
        
        # 按版本倒序排列，找到最新一条 accuracy_after 为 null 的记录
        history.sort(key=lambda x: x.get("version", 0), reverse=True)
        
        for record in history:
            if record.get("accuracy_after") is None:
                record["accuracy_after"] = accuracy_after
                record["updated_at"] = datetime.now().isoformat()
                self._save_history(history)
                self.logger.info(
                    f"已回填知识库版本 {record.get('version')} 的优化后准确率: {accuracy_after:.1%}"
                )
                return True
        
        # 没有找到待更新的记录（所有记录都已有 accuracy_after）
        return False
        
    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取优化历史记录
        
        :param limit: 返回的最大记录数
        :return: 优化历史记录列表（按时间倒序）
        """
        history: List[Dict[str, Any]] = self._load_history()
        
        # 按版本倒序排列
        history.sort(key=lambda x: x.get("version", 0), reverse=True)
        
        return history[:limit]
        
    def get_latest_analysis(self) -> Optional[Dict[str, Any]]:
        """
        获取最近一次优化的分析结果
        
        :return: 最近一次优化的分析数据，如果没有则返回 None
        """
        history: List[Dict[str, Any]] = self.get_history(limit=1)
        
        if history:
            latest: Dict[str, Any] = history[0]
            return {
                "version": latest.get("version"),
                "analysis_summary": latest.get("analysis_summary"),
                "intent_analysis": latest.get("intent_analysis"),
                "deep_analysis": latest.get("deep_analysis"),
                "applied_strategies": latest.get("applied_strategies"),
                "accuracy_before": latest.get("accuracy_before"),
                "accuracy_after": latest.get("accuracy_after")
            }
            
        return None
        
    def get_optimization_trends(self) -> Dict[str, Any]:
        """
        获取优化趋势数据
        
        :return: 优化趋势统计
        """
        history: List[Dict[str, Any]] = self._load_history()
        
        if not history:
            return {"total_versions": 0, "accuracy_trend": []}
            
        # 按版本正序排列
        history.sort(key=lambda x: x.get("version", 0))
        
        # 提取准确率趋势
        accuracy_trend: List[Dict[str, Any]] = []
        for record in history:
            accuracy_trend.append({
                "version": record.get("version"),
                "accuracy_before": record.get("accuracy_before"),
                "accuracy_after": record.get("accuracy_after")
            })
            
        return {
            "total_versions": len(history),
            "accuracy_trend": accuracy_trend,
            "latest_accuracy": history[-1].get("accuracy_before") if history else None
        }
        
    def format_history_for_prompt(self, limit: int = 3) -> str:
        """
        格式化历史记录，用于注入优化提示词
        
        :param limit: 包含的历史版本数
        :return: 格式化的历史分析文本
        """
        history: List[Dict[str, Any]] = self.get_history(limit=limit)
        
        if not history:
            return "暂无历史优化记录"
            
        lines: List[str] = []
        for record in history:
            version: int = record.get("version", 0)
            summary: str = record.get("analysis_summary", "无总结")
            strategies: List[str] = record.get("applied_strategies", [])
            acc_before: float = record.get("accuracy_before", 0)
            acc_after: Optional[float] = record.get("accuracy_after")
            
            # 截断过长的总结
            if len(summary) > 200:
                summary = summary[:200] + "..."
                
            lines.append(f"### 版本 {version}")
            lines.append(f"- 优化前准确率: {acc_before:.1%}")
            if acc_after is not None:
                lines.append(f"- 优化后准确率: {acc_after:.1%}")
            lines.append(f"- 应用策略: {', '.join(strategies)}")
            lines.append(f"- 优化总结: {summary}")
            lines.append("")
            
        return "\n".join(lines)
    
    def get_all_history_for_prompt(self) -> str:
        """
        获取所有历史版本的格式化文本，用于注入到优化 Prompt 中
        
        与 format_history_for_prompt 不同，此方法：
        1. 返回所有历史版本（按版本正序，从 V1 到最新）
        2. 包含每轮的新增失败案例（去空格后原样输出）
        
        :return: 格式化的完整历史文本
        """
        # 加载所有历史记录
        history: List[Dict[str, Any]] = self._load_history()
        
        if not history:
            return "暂无历史优化记录"
        
        # 按版本正序排列（从 V1 到最新）
        history.sort(key=lambda x: x.get("version", 0))
        
        lines: List[str] = []
        
        for record in history:
            version: int = record.get("version", 0)
            summary: str = record.get("analysis_summary", "无总结")
            strategies: List[str] = record.get("applied_strategies", [])
            acc_before: float = record.get("accuracy_before", 0)
            acc_after: Optional[float] = record.get("accuracy_after")
            newly_failed: Optional[List[Dict[str, Any]]] = record.get(
                "newly_failed_cases"
            )
            
            lines.append(f"### 版本 {version}")
            lines.append(f"- 优化前准确率: {acc_before:.1%}")
            if acc_after is not None:
                lines.append(f"- 优化后准确率: {acc_after:.1%}")
            lines.append(f"- 应用策略: {', '.join(strategies)}")
            lines.append(f"- 优化总结: {summary}")
            
            # 添加 Diff 信息
            # diff_content = record.get("diff", "")
            # if diff_content:
            #     lines.append("- 修改 Diff:")
            #     # 简单缩进显示
            #     for d_line in diff_content.split('\n'):
            #         lines.append(f"  {d_line}")
            
            # 添加新增失败案例（去空格后原样输出）
            if newly_failed and len(newly_failed) > 0:
                lines.append("- 新增失败案例（本轮回退）:")
                for case in newly_failed:
                    # 去除空格后原样输出 query
                    query: str = str(case.get("query", "")).strip()
                    target: str = str(case.get("target", "")).strip()
                    output: str = str(case.get("output", "")).strip()
                    reason: str = str(case.get("reason", "")).strip()
                    
                    lines.append(f"  - Query: {query}")
                    reason_text = f" | 原因: {reason}" if reason else ""
                    lines.append(f"    期望: {target}{reason_text} | 实际: {output}")
            
            lines.append("")
        
        return "\n".join(lines)
