"use client";

import { useState, useEffect } from "react";
import { X, Save, Trash2, Clock, TrendingUp, Layers, FileText, AlertCircle, ChevronDown, ChevronUp } from "lucide-react";
import axios from "axios";



/**
 * 新增失败案例接口定义
 */
interface FailedCase {
    query: string;
    target: string;
    output?: string;
}

/**
 * 知识库记录接口定义
 * 使用动态类型以支持后端新增字段的自动展示
 */
interface KnowledgeRecord {
    version: number;
    timestamp: string;
    original_prompt: string;
    optimized_prompt: string;
    analysis_summary: string;
    intent_analysis: Record<string, unknown>;
    deep_analysis?: Record<string, unknown>;
    applied_strategies: string[];
    accuracy_before: number;
    accuracy_after?: number;
    updated_at?: string;
    newly_failed_cases?: FailedCase[];
    diff?: string;
    // 允许任意额外字段（动态扩展）
    [key: string]: unknown;
}

/**
 * 字段展示配置接口
 */
interface FieldConfig {
    // 字段显示名称
    label: string;
    // 图标颜色类名
    iconColor: string;
    // 是否跳过该字段（在自定义区域已处理）
    skip?: boolean;
}

/**
 * 已知字段的显示配置映射
 * 用于为常见字段提供友好的中文名称和样式
 */
const FIELD_CONFIG: Record<string, FieldConfig> = {
    // 基础字段（已在固定区域展示，跳过动态渲染）
    version: { label: "版本", iconColor: "text-slate-400", skip: true },
    timestamp: { label: "时间", iconColor: "text-slate-400", skip: true },
    original_prompt: { label: "原始提示词", iconColor: "text-slate-400", skip: true },
    optimized_prompt: { label: "优化后提示词", iconColor: "text-slate-400", skip: true },
    analysis_summary: { label: "优化总结", iconColor: "text-slate-400", skip: true },
    applied_strategies: { label: "应用策略", iconColor: "text-slate-400", skip: true },
    accuracy_before: { label: "优化前准确率", iconColor: "text-slate-400", skip: true },
    accuracy_after: { label: "优化后准确率", iconColor: "text-slate-400", skip: true },
    updated_at: { label: "更新时间", iconColor: "text-slate-400", skip: true },
    // 动态展示区域字段
    intent_analysis: { label: "意图分析", iconColor: "text-blue-400" },
    deep_analysis: { label: "深度分析", iconColor: "text-purple-400" },
    newly_failed_cases: { label: "新增失败案例", iconColor: "text-red-400" },
    diff: { label: "提示词变更", iconColor: "text-emerald-400" },
    // 可能的新增字段预配置
    advanced_diagnosis: { label: "高级诊断", iconColor: "text-amber-400" },
    optimization_history: { label: "优化历史", iconColor: "text-cyan-400" },
    error_patterns: { label: "错误模式分析", iconColor: "text-orange-400" },
    confusion_matrix: { label: "混淆矩阵", iconColor: "text-pink-400" },
};

/**
 * 模态框属性接口
 */
interface KnowledgeDetailModalProps {
    // 选中的知识库记录
    record: KnowledgeRecord | null;
    // 项目ID
    projectId: string;
    // 关闭回调
    onClose: () => void;
    // 数据更新回调
    onUpdate: () => void;
    // 提示消息回调
    showToast: (message: string, type: "success" | "error") => void;
}

const API_BASE = "/api";

/**
 * 知识库详情模态框组件
 * 
 * 用于展示和编辑知识库记录详情
 */
export default function KnowledgeDetailModal({
    record,
    projectId,
    onClose,
    onUpdate,
    showToast
}: KnowledgeDetailModalProps) {
    // 编辑模式状态
    const [isEditing, setIsEditing] = useState(false);
    // 编辑中的分析总结
    const [editedSummary, setEditedSummary] = useState("");
    // 保存中状态
    const [isSaving, setIsSaving] = useState(false);
    // 删除确认状态
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

    // 各模块折叠状态（默认全部折叠）
    const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({});

    /**
     * 切换模块折叠状态
     */
    const toggleSection = (section: string): void => {
        setExpandedSections(prev => ({
            ...prev,
            [section]: !prev[section]
        }));
    };

    // 当记录变化时，重置编辑状态
    useEffect(() => {
        if (record) {
            setEditedSummary(record.analysis_summary || "");
            setIsEditing(false);
            setShowDeleteConfirm(false);
        }
    }, [record]);

    // ESC 键关闭
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === "Escape" && record) {
                onClose();
            }
        };
        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [record, onClose]);

    if (!record) return null;

    /**
     * 保存编辑
     */
    const handleSave = async () => {
        setIsSaving(true);
        try {
            await axios.put(
                `${API_BASE}/projects/${projectId}/knowledge-base/${record.version}`,
                { analysis_summary: editedSummary }
            );
            showToast("保存成功", "success");
            setIsEditing(false);
            onUpdate();
        } catch (e: any) {
            console.error("保存失败:", e);
            showToast(`保存失败: ${e.response?.data?.detail || e.message}`, "error");
        } finally {
            setIsSaving(false);
        }
    };

    /**
     * 删除记录
     */
    const handleDelete = async () => {
        try {
            await axios.delete(
                `${API_BASE}/projects/${projectId}/knowledge-base/${record.version}`
            );
            showToast("删除成功", "success");
            onClose();
            onUpdate();
        } catch (e: any) {
            console.error("删除失败:", e);
            showToast(`删除失败: ${e.response?.data?.detail || e.message}`, "error");
        }
    };

    /**
     * 格式化时间戳
     */
    const formatTime = (timestamp: string): string => {
        if (!timestamp) return "未知";
        try {
            return new Date(timestamp).toLocaleString();
        } catch {
            return "未知";
        }
    };

    /**
     * 策略名称映射
     */
    const strategyNameMap: Record<string, string> = {
        "cot_reasoning": "思维链推理",
        "instruction_refinement": "指令优化",
        "format_alignment": "格式对齐",
        "example_enhancement": "示例增强",
        "persona_adjustment": "人设调整",
        "constraint_strengthening": "约束强化",
        "context_enrichment": "上下文增强"
    };

    /**
     * 检查值是否为空
     */
    const isEmptyValue = (value: unknown): boolean => {
        if (value === null || value === undefined) return true;
        if (typeof value === 'string' && value.trim() === '') return true;
        if (Array.isArray(value) && value.length === 0) return true;
        if (typeof value === 'object' && Object.keys(value as object).length === 0) return true;
        return false;
    };

    /**
     * 获取字段配置（支持未知字段的自动生成）
     */
    const getFieldConfig = (fieldKey: string): FieldConfig => {
        if (FIELD_CONFIG[fieldKey]) {
            return FIELD_CONFIG[fieldKey];
        }
        // 自动生成未知字段的配置
        // 将 snake_case 转换为中文友好名称
        const label = fieldKey
            .replace(/_/g, ' ')
            .replace(/\b\w/g, c => c.toUpperCase());
        return {
            label: label,
            iconColor: 'text-slate-400'
        };
    };

    /**
     * 处理全选快捷键 (Ctrl+A)
     */
    const handleSelectAll = (e: React.KeyboardEvent) => {
        if ((e.ctrlKey || e.metaKey) && (e.key === 'a' || e.key === 'A')) {
            e.preventDefault();
            const selection = window.getSelection();
            const range = document.createRange();
            range.selectNodeContents(e.currentTarget);
            selection?.removeAllRanges();
            selection?.addRange(range);
        }
    };

    /**
     * 渲染 Diff 内容（特殊处理 unified diff 格式）
     */
    const renderDiffContent = (diffText: string): React.ReactNode => {
        return (
            <div
                className="bg-black/30 rounded-lg p-3 font-mono text-xs space-y-0.5 focus:outline-none focus:ring-1 focus:ring-blue-500/30"
                tabIndex={0}
                onKeyDown={handleSelectAll}
            >
                {diffText.split('\n').map((line: string, idx: number) => {
                    const isAdded = line.startsWith('+');
                    const isRemoved = line.startsWith('-');
                    const isContext = line.startsWith('@@');

                    return (
                        <div
                            key={idx}
                            className={`whitespace-pre-wrap break-words px-1 rounded ${isAdded
                                ? 'text-green-400 bg-green-500/10'
                                : isRemoved
                                    ? 'text-red-400 bg-red-500/10'
                                    : isContext
                                        ? 'text-blue-400 bg-blue-500/10'
                                        : 'text-slate-400'
                                }`}
                        >
                            {line}
                        </div>
                    );
                })}
            </div>
        );
    };

    /**
     * 渲染失败案例列表（特殊处理 newly_failed_cases 格式）
     */
    const renderFailedCases = (cases: FailedCase[]): React.ReactNode => {
        return (
            <div
                className="space-y-2 focus:outline-none focus:ring-1 focus:ring-blue-500/30 p-1 rounded-lg"
                tabIndex={0}
                onKeyDown={handleSelectAll}
            >
                {cases.map((item: FailedCase, idx: number) => (
                    <div
                        key={idx}
                        className="bg-black/30 rounded-lg p-3 border border-red-500/20"
                    >
                        <div className="text-xs text-slate-500 mb-1">查询:</div>
                        <div className="text-sm text-slate-300 mb-2 break-words">
                            {item.query || "无"}
                        </div>
                        <div className="text-xs text-slate-500 mb-1">预期结果:</div>
                        <div className="text-sm text-red-400 break-words">
                            {item.target || "无"}
                        </div>
                    </div>
                ))}
            </div>
        );
    };

    /**
     * 通用字段内容渲染器
     * 根据值类型自动选择最佳展示方式
     */
    const renderFieldContent = (fieldKey: string, value: unknown): React.ReactNode => {
        // Diff 特殊处理
        if (fieldKey === 'diff' && typeof value === 'string') {
            return renderDiffContent(value);
        }

        // 失败案例特殊处理
        if (fieldKey === 'newly_failed_cases' && Array.isArray(value)) {
            return renderFailedCases(value as FailedCase[]);
        }

        // 字符串类型
        if (typeof value === 'string') {
            return (
                <pre
                    className="text-xs text-slate-400 bg-black/30 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap break-words pointer-events-auto select-text focus:outline-none focus:ring-1 focus:ring-blue-500/30"
                    tabIndex={0}
                    onKeyDown={handleSelectAll}
                >
                    {value}
                </pre>
            );
        }

        // 数组或对象类型 - JSON 格式化展示
        return (
            <pre
                className="text-xs text-slate-400 bg-black/30 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap break-words pointer-events-auto select-text focus:outline-none focus:ring-1 focus:ring-blue-500/30"
                tabIndex={0}
                onKeyDown={handleSelectAll}
            >
                {JSON.stringify(value, null, 2)}
            </pre>
        );
    };

    /**
     * 渲染动态字段区块
     * 支持折叠/展开，自动适配内容类型
     */
    const renderDynamicSection = (fieldKey: string, value: unknown): React.ReactNode => {
        const config = getFieldConfig(fieldKey);
        const isExpanded = !!expandedSections[fieldKey];

        // 计算显示的数量（如果是数组）
        const countDisplay = Array.isArray(value) ? ` (${value.length})` : '';

        return (
            <div key={fieldKey} className="bg-white/5 border border-white/10 rounded-xl overflow-hidden">
                <button
                    onClick={() => toggleSection(fieldKey)}
                    className="w-full p-4 flex items-center justify-between hover:bg-white/5 transition-colors"
                >
                    <div className="text-sm text-slate-300 font-medium flex items-center gap-2">
                        <Layers size={14} className={config.iconColor} />
                        {config.label}{countDisplay}
                    </div>
                    {isExpanded ? (
                        <ChevronUp size={16} className="text-slate-400" />
                    ) : (
                        <ChevronDown size={16} className="text-slate-400" />
                    )}
                </button>
                {isExpanded && (
                    <div className="px-4 pb-4">
                        <div className="max-h-96 overflow-y-auto custom-scrollbar">
                            {renderFieldContent(fieldKey, value)}
                        </div>
                    </div>
                )}
            </div>
        );
    };

    /**
     * 获取需要动态渲染的字段列表
     * 过滤掉已在固定区域展示的字段和空值
     */
    const getDynamicFields = (): Array<[string, unknown]> => {
        return Object.entries(record).filter(([key, value]) => {
            const config = FIELD_CONFIG[key];
            // 跳过已在固定区域展示的字段
            if (config?.skip) return false;
            // 跳过空值
            if (isEmptyValue(value)) return false;
            return true;
        });
    };

    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200"
            onClick={(e) => e.target === e.currentTarget && onClose()}
        >
            <div className="bg-slate-900 border border-white/10 rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden">
                {/* 头部 */}
                <div className="flex justify-between items-center p-4 border-b border-white/10 bg-gradient-to-r from-blue-600/10 to-purple-600/10">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-blue-600/20 flex items-center justify-center">
                            <Layers size={20} className="text-blue-400" />
                        </div>
                        <div>
                            <h3 className="text-lg font-bold text-white">优化分析 v{record.version}</h3>
                            <p className="text-xs text-slate-400 flex items-center gap-1">
                                <Clock size={12} />
                                {formatTime(record.timestamp)}
                            </p>
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        className="w-8 h-8 rounded-lg bg-white/5 hover:bg-white/10 flex items-center justify-center transition-colors"
                    >
                        <X size={18} className="text-slate-400" />
                    </button>
                </div>

                {/* 内容区域 - 增加右侧 padding 方便操作滑动条 */}
                <div className="flex-1 overflow-y-auto pl-4 pr-6 py-4 space-y-4 custom-scrollbar">
                    {/* 准确率卡片 */}
                    <div className="grid grid-cols-2 gap-4">
                        <div className="bg-gradient-to-br from-orange-600/10 to-red-600/10 border border-orange-500/20 rounded-xl p-4">
                            <div className="text-xs text-orange-400 mb-1">优化前准确率</div>
                            <div className="text-2xl font-bold text-orange-400">
                                {(record.accuracy_before * 100).toFixed(1)}%
                            </div>
                        </div>
                        <div className="bg-gradient-to-br from-emerald-600/10 to-green-600/10 border border-emerald-500/20 rounded-xl p-4">
                            <div className="text-xs text-emerald-400 mb-1 flex items-center gap-1">
                                <TrendingUp size={12} />
                                优化后准确率
                            </div>
                            <div className="text-2xl font-bold text-emerald-400">
                                {record.accuracy_after !== null && record.accuracy_after !== undefined
                                    ? `${(record.accuracy_after * 100).toFixed(1)}%`
                                    : "待验证"}
                            </div>
                        </div>
                    </div>

                    {/* 应用策略 */}
                    <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                        <div className="text-xs text-slate-400 mb-2 flex items-center gap-1">
                            <Layers size={12} />
                            应用的优化策略
                        </div>
                        <div className="flex flex-wrap gap-2">
                            {record.applied_strategies?.length ? (
                                record.applied_strategies.map((strategy, idx) => (
                                    <span
                                        key={idx}
                                        className="px-3 py-1 bg-blue-500/20 text-blue-400 text-xs rounded-full border border-blue-500/30"
                                    >
                                        {strategyNameMap[strategy] || strategy}
                                    </span>
                                ))
                            ) : (
                                <span className="text-slate-500 text-xs">无策略记录</span>
                            )}
                        </div>
                    </div>

                    {/* 优化总结 */}
                    <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                        <div className="flex justify-between items-center mb-2">
                            <div className="text-xs text-slate-400 flex items-center gap-1">
                                <FileText size={12} />
                                优化总结
                            </div>
                            {!isEditing && (
                                <button
                                    onClick={() => setIsEditing(true)}
                                    className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
                                >
                                    编辑
                                </button>
                            )}
                        </div>
                        {isEditing ? (
                            <textarea
                                value={editedSummary}
                                onChange={(e) => setEditedSummary(e.target.value)}
                                className="w-full h-40 bg-black/30 border border-white/10 rounded-lg p-3 text-sm text-slate-300 focus:outline-none focus:border-blue-500/50 resize-none custom-scrollbar"
                                placeholder="输入优化总结..."
                            />
                        ) : (
                            <p className="text-sm text-slate-300 whitespace-pre-wrap leading-relaxed">
                                {record.analysis_summary || "暂无优化总结"}
                            </p>
                        )}
                    </div>

                    {/* 动态渲染所有分析字段 */}
                    {getDynamicFields().map(([fieldKey, value]) =>
                        renderDynamicSection(fieldKey, value)
                    )}
                </div>

                {/* 底部操作栏 */}
                <div className="p-4 border-t border-white/10 bg-slate-900/80 flex justify-between items-center">
                    {/* 删除区域 */}
                    <div className="flex items-center gap-2">
                        {showDeleteConfirm ? (
                            <>
                                <span className="text-xs text-red-400 flex items-center gap-1">
                                    <AlertCircle size={12} />
                                    确认删除?
                                </span>
                                <button
                                    onClick={handleDelete}
                                    className="px-3 py-1.5 bg-red-600 hover:bg-red-500 text-white text-xs rounded-lg transition-colors"
                                >
                                    确认
                                </button>
                                <button
                                    onClick={() => setShowDeleteConfirm(false)}
                                    className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-white text-xs rounded-lg transition-colors"
                                >
                                    取消
                                </button>
                            </>
                        ) : (
                            <button
                                onClick={() => setShowDeleteConfirm(true)}
                                className="flex items-center gap-1 px-3 py-1.5 bg-red-600/20 hover:bg-red-600/30 text-red-400 text-xs rounded-lg transition-colors border border-red-500/30"
                            >
                                <Trash2 size={12} />
                                删除记录
                            </button>
                        )}
                    </div>

                    {/* 保存区域 */}
                    <div className="flex items-center gap-2">
                        {isEditing && (
                            <>
                                <button
                                    onClick={() => {
                                        setEditedSummary(record.analysis_summary || "");
                                        setIsEditing(false);
                                    }}
                                    className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white text-sm rounded-lg transition-colors"
                                >
                                    取消
                                </button>
                                <button
                                    onClick={handleSave}
                                    disabled={isSaving}
                                    className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg transition-colors disabled:opacity-50"
                                >
                                    <Save size={14} />
                                    {isSaving ? "保存中..." : "保存"}
                                </button>
                            </>
                        )}
                        {!isEditing && (
                            <button
                                onClick={onClose}
                                className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white text-sm rounded-lg transition-colors"
                            >
                                关闭
                            </button>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
