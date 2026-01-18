"""Agent 路由边界优化策略 - 专门解决 Agent 路由混淆问题"""
import re
from loguru import logger
from typing import List, Dict, Any, Tuple
from .base import BaseStrategy


class AgentRoutingBoundaryStrategy(BaseStrategy):
    """
    Agent 路由边界优化策略

    专门针对多 Agent 路由场景中的边界混淆问题进行优化。
    通过分析错误案例中的路由混淆模式，生成精准的边界澄清规则。

    适用场景：
    1. Agent A 和 Agent B 之间存在高频混淆（如 pay_ai vs jcca）
    2. 某些关键词/场景被错误路由到相似 Agent
    3. 需要添加"优先级覆盖规则"或"排除规则"
    """

    name: str = "agent_routing_boundary"
    priority: int = 95  # 高优先级，边界问题是路由准确率的关键
    description: str = "Agent 路由边界优化策略：针对 Agent 间的路由混淆添加精准边界规则"

    # 已知的高频混淆对及其边界特征
    KNOWN_CONFUSION_PATTERNS: Dict[Tuple[str, str], Dict[str, Any]] = {
        # (期望Agent, 实际错误路由到的Agent): 边界特征
        ("pay_ai_master_agent", "jcca_agent"): {
            "keywords": ["还款提醒", "绑卡", "绑定", "主卡", "进口商品", "港澳卡", "数币还款"],
            "rule": "涉及「还款提醒设置」「银行卡绑定/解绑」「支付方式」的通用操作归 pay_ai_master_agent，仅「信用卡产品本身的业务」（年费、额度、分期、激活）归 jcca_agent",
            "examples": [
                ("农业银行还款提醒日", "pay_ai_master_agent", "设置还款提醒是支付功能"),
                ("帮别人还信用卡", "pay_ai_master_agent", "代还是支付操作"),
                ("港澳卡绑定", "pay_ai_master_agent", "绑卡是支付功能"),
            ]
        },
        ("pay_ai_master_agent", "cs_agent"): {
            "keywords": ["默认白条", "白条优先", "白条支付", "支付方式", "支付设置"],
            "rule": "「支付方式设置/默认支付修改」归 pay_ai_master_agent，仅「白条产品本身」（开通、额度、账单、还款）归 cs_agent",
            "examples": [
                ("我不想默认白条付款", "pay_ai_master_agent", "修改默认支付方式是支付设置"),
                ("怎么每次都是白条支付", "pay_ai_master_agent", "支付方式偏好设置"),
                ("白条怎么开通", "cs_agent", "白条产品本身的开通"),
            ]
        },
        ("cs_agent", "market"): {
            "keywords": ["六合彩", "澳门", "香港.*彩", "特码", "领奖", "领取.*奖"],
            "rule": "「六合彩」等境外/非法博彩一律归 cs_agent（需拒绝或引导）；「领奖/活动奖品」若无明确业务归属也归 cs_agent",
            "examples": [
                ("香港六合彩", "cs_agent", "非法博彩需客服处理"),
                ("六合彩特码", "cs_agent", "非法博彩"),
                ("我能领取最贵的奖品是哪个活动", "cs_agent", "通用活动咨询归客服"),
            ]
        },
        ("xj_master_agent", "cs_agent"): {
            "keywords": ["初筛", "授信", "借款.*失败", "欠款", "本金", "学生.*开通"],
            "rule": "「借款/贷款流程问题」（初筛失败、授信拒绝、欠款查询）归 xj_master_agent，仅「投诉/人工」归 cs_agent",
            "examples": [
                ("初筛失败怎么办", "xj_master_agent", "借款审核流程问题"),
                ("学生无法开通", "xj_master_agent", "借款资格问题"),
                ("查一下欠款总额", "xj_master_agent", "借款账单查询"),
            ]
        },
        ("jxb_agent", "pay_ai_master_agent"): {
            "keywords": ["零钱通", "随用随充", "零钱.*变多", "资产.*提现"],
            "rule": "「零钱通」「随用随充」等理财增值功能归 jxb_agent，仅「钱包余额/提现操作」归 pay_ai_master_agent",
            "examples": [
                ("零钱通是什么", "jxb_agent", "理财产品介绍"),
                ("随用随充怎么关闭", "jxb_agent", "理财功能设置"),
                ("我要提现", "pay_ai_master_agent", "提现是支付操作"),
            ]
        },
        ("jxb_agent", "market"): {
            "keywords": ["基金.*大佬", "基金.*牛人", "持仓.*榜", "北50"],
            "rule": "「基金大V/牛人」若强调「投资策略/持仓分析」归 jxb_agent，若强调「社区互动/关注」归 market",
            "examples": [
                ("基金牛人", "jxb_agent", "查看投资高手策略"),
                ("怎么关注基金博主", "market", "社区关注功能"),
            ]
        },
        ("market", "jxb_agent"): {
            "keywords": ["金生四海", "基金实盘", "大V持仓"],
            "rule": "「金生四海」等特定大V/栏目名称归 market",
            "examples": [
                ("金生四海", "market", "特定大V栏目"),
                ("金生四海对行情的看法", "market", "大V观点"),
            ]
        },
    }

    # 需要触发澄清的模糊场景
    CLARIFICATION_PATTERNS: List[Dict[str, Any]] = [
        {
            "keywords": ["额度", "材料", "资料"],
            "exclude": ["白条额度", "金条额度", "信用卡额度", "临时额度"],
            "reason": "未指明是哪个产品的额度",
        },
        {
            "keywords": ["激活", "激活失败"],
            "exclude": ["白条激活", "金条激活", "银行卡激活", "信用卡激活"],
            "reason": "未指明激活哪个产品",
        },
        {
            "keywords": ["限额", "调整限额"],
            "exclude": ["支付限额", "转账限额", "提现限额"],
            "reason": "未指明是哪种限额",
        },
        {
            "keywords": ["还款", "还款方式"],
            "exclude": ["白条还款", "金条还款", "信用卡还款", "花呗还款"],
            "reason": "未指明还哪个产品的款",
        },
    ]

    def is_applicable(self, diagnosis: Dict[str, Any]) -> bool:
        """
        判断策略是否适用

        当存在以下情况时适用：
        1. 存在 Agent 间的混淆对
        2. 错误案例中出现已知的混淆模式关键词
        """
        # 检查是否存在混淆对
        confusion_pairs = diagnosis.get("error_patterns", {}).get("confusion_pairs", [])
        if confusion_pairs:
            logger.info(f"[{self.name}] 检测到 {len(confusion_pairs)} 个混淆对，策略适用")
            return True

        # 检查错误样本中是否包含已知混淆模式的关键词
        error_samples = diagnosis.get("error_samples", [])
        for sample in error_samples[:20]:
            query = sample.get("query", "")
            target = sample.get("target", "")
            output = sample.get("output", "")

            # 检查是否匹配已知混淆模式
            pair_key = (target, output)
            if pair_key in self.KNOWN_CONFUSION_PATTERNS:
                pattern_info = self.KNOWN_CONFUSION_PATTERNS[pair_key]
                for keyword in pattern_info.get("keywords", []):
                    if re.search(keyword, query, re.IGNORECASE):
                        logger.info(f"[{self.name}] 检测到已知混淆模式: {pair_key}, 关键词: {keyword}")
                        return True

        return False

    def get_priority(self, diagnosis: Dict[str, Any]) -> int:
        """
        根据混淆严重程度动态调整优先级
        """
        confusion_pairs = diagnosis.get("error_patterns", {}).get("confusion_pairs", [])
        if confusion_pairs:
            # 混淆率越高，优先级越高
            max_rate = max(pair[2] for pair in confusion_pairs) if confusion_pairs else 0
            adjusted_priority = int(self.priority * (1 + max_rate * 0.5))
            logger.debug(f"[{self.name}] 动态优先级: {adjusted_priority} (基于最高混淆率 {max_rate:.2%})")
            return adjusted_priority
        return self.priority

    def apply(
        self,
        prompt: str,
        errors: List[Dict[str, Any]],
        diagnosis: Dict[str, Any]
    ) -> str:
        """
        应用 Agent 路由边界优化策略

        :param prompt: 当前提示词
        :param errors: 错误样例列表
        :param diagnosis: 诊断分析结果
        :return: 优化后的提示词
        """
        logger.info(f"[{self.name}] 开始执行 Agent 路由边界优化...")

        # 1. 分析错误案例，识别混淆模式
        confusion_analysis = self._analyze_routing_confusion(errors, diagnosis)

        # 2. 生成边界澄清规则
        boundary_rules = self._generate_boundary_rules(confusion_analysis, errors)

        # 3. 生成澄清触发规则
        clarification_rules = self._generate_clarification_rules(errors)

        # 4. 构建优化指令
        optimization_instruction = self._build_optimization_instruction(
            confusion_analysis, boundary_rules, clarification_rules
        )

        logger.info(f"[{self.name}] 生成优化指令完成，长度: {len(optimization_instruction)} 字符")

        # 5. 使用元优化方法应用修改
        return self._meta_optimize(
            prompt,
            errors,
            optimization_instruction,
            conservative=True,
            diagnosis=diagnosis
        )

    def _analyze_routing_confusion(
        self,
        errors: List[Dict[str, Any]],
        diagnosis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        分析路由混淆模式

        :return: 混淆分析结果
        """
        confusion_stats: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}

        for error in errors:
            target = error.get("target", "")
            output = error.get("output", "")
            query = error.get("query", "")

            if not target or not output or target == output:
                continue

            # 从 output 中提取实际路由的 agent_id
            actual_agent = self._extract_agent_from_output(output)
            if not actual_agent:
                continue

            pair_key = (target, actual_agent)
            if pair_key not in confusion_stats:
                confusion_stats[pair_key] = []
            confusion_stats[pair_key].append({
                "query": query,
                "target": target,
                "actual": actual_agent
            })

        # 按错误数量排序
        sorted_pairs = sorted(
            confusion_stats.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )

        logger.info(f"[{self.name}] 识别到 {len(sorted_pairs)} 个混淆对")
        for pair, samples in sorted_pairs[:5]:
            logger.info(f"[{self.name}]   {pair[0]} -> {pair[1]}: {len(samples)} 条错误")

        return {
            "confusion_pairs": sorted_pairs[:10],  # Top 10 混淆对
            "total_errors": len(errors)
        }

    def _extract_agent_from_output(self, output: str) -> str:
        """从模型输出中提取实际调用的 agent_id"""
        match = re.search(r'"agent_id":\s*"([^"]+)"', output)
        return match.group(1) if match else ""

    def _generate_boundary_rules(
        self,
        confusion_analysis: Dict[str, Any],
        errors: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        生成边界澄清规则
        """
        rules = []

        for pair_key, samples in confusion_analysis.get("confusion_pairs", []):
            target_agent, actual_agent = pair_key

            # 检查是否有预定义的规则
            if pair_key in self.KNOWN_CONFUSION_PATTERNS:
                pattern = self.KNOWN_CONFUSION_PATTERNS[pair_key]
                rules.append({
                    "pair": pair_key,
                    "error_count": len(samples),
                    "rule": pattern["rule"],
                    "examples": pattern["examples"],
                    "keywords": pattern["keywords"],
                    "sample_queries": [s["query"] for s in samples[:5]]
                })
            else:
                # 动态生成规则（基于错误样本）
                sample_queries = [s["query"] for s in samples[:5]]
                rules.append({
                    "pair": pair_key,
                    "error_count": len(samples),
                    "rule": f"需要明确区分 {target_agent} 和 {actual_agent} 的边界",
                    "examples": [],
                    "keywords": [],
                    "sample_queries": sample_queries
                })

        return rules

    def _generate_clarification_rules(
        self,
        errors: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        生成澄清触发规则
        """
        clarification_needed = []

        # 检查错误中是否有「期望澄清但直接路由」的情况
        for error in errors:
            target = error.get("target", "")
            query = error.get("query", "")

            if target == "需澄清":
                # 分析为什么应该澄清
                for pattern in self.CLARIFICATION_PATTERNS:
                    keywords = pattern["keywords"]
                    excludes = pattern["exclude"]

                    # 检查是否匹配关键词但不匹配排除词
                    matches_keyword = any(kw in query for kw in keywords)
                    matches_exclude = any(ex in query for ex in excludes)

                    if matches_keyword and not matches_exclude:
                        clarification_needed.append({
                            "query": query,
                            "reason": pattern["reason"],
                            "keywords": keywords
                        })
                        break

        logger.info(f"[{self.name}] 识别到 {len(clarification_needed)} 条需要澄清的案例")
        return clarification_needed[:10]

    def _build_optimization_instruction(
        self,
        confusion_analysis: Dict[str, Any],
        boundary_rules: List[Dict[str, Any]],
        clarification_rules: List[Dict[str, Any]]
    ) -> str:
        """
        构建优化指令
        """
        instruction_parts = []

        instruction_parts.append("## Agent 路由边界优化任务\n")
        instruction_parts.append("当前提示词在多 Agent 路由时存在边界混淆问题，需要添加精准的边界规则。\n")

        # 1. 混淆对分析
        if boundary_rules:
            instruction_parts.append("\n### 一、路由混淆问题（必须修复）\n")
            for rule in boundary_rules[:5]:
                target, actual = rule["pair"]
                count = rule["error_count"]
                instruction_parts.append(f"\n**问题**: 期望路由到 `{target}`，但被错误路由到 `{actual}` ({count} 条错误)\n")

                if rule.get("sample_queries"):
                    instruction_parts.append("典型错误案例:\n")
                    for q in rule["sample_queries"][:3]:
                        instruction_parts.append(f"  - \"{q}\"\n")

                if rule.get("rule"):
                    instruction_parts.append(f"\n**修复规则**: {rule['rule']}\n")

                if rule.get("examples"):
                    instruction_parts.append("**正确路由示例**:\n")
                    for query, agent, reason in rule["examples"][:3]:
                        instruction_parts.append(f"  - \"{query}\" → {agent}（{reason}）\n")

        # 2. 澄清规则
        if clarification_rules:
            instruction_parts.append("\n### 二、需要触发澄清的场景\n")
            instruction_parts.append("以下场景因信息不完整，应输出澄清问题而非直接路由:\n")
            for rule in clarification_rules[:5]:
                instruction_parts.append(f"  - \"{rule['query']}\" → 应澄清，原因: {rule['reason']}\n")

        # 3. 优化要点
        instruction_parts.append("\n### 三、优化要点\n")
        instruction_parts.append("""
1. 在「快速路由表」或「边界规则」部分添加明确的区分条件
2. 使用「如果...则归A，如果...则归B」的判断逻辑
3. 对于模糊场景，添加「需澄清」的触发条件
4. 保持原有提示词结构，仅添加/修改边界规则
5. 每次修改不超过 3 处，稳步迭代

**重要**:
- 修改应聚焦在「Agent 详细说明」或「边界规则」部分
- 优先使用「排除规则」(如: "xxx 归 A，但 yyy 除外")
- 添加的示例要与错误案例直接对应
""")

        return "".join(instruction_parts)
