"use client";

import { useState, useEffect } from "react";
import { X, Save, Trash2, Clock, TrendingUp, Layers, FileText, AlertCircle } from "lucide-react";
import axios from "axios";

/**
 * 差异对象接口定义
 */
interface DiffItem {
    type: string;
    content: string;
}

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
    // 新增字段
    newly_failed_cases?: FailedCase[];
    diff?: DiffItem[];
}

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

                {/* 内容区域 */}
                <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
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

                    {/* 意图分析 (如果存在) - 固定高度 + 滚动条 */}
                    {record.intent_analysis && Object.keys(record.intent_analysis).length > 0 && (
                        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                            <div className="text-xs text-slate-400 mb-2">意图分析</div>
                            {/* 固定高度容器，防止内容过长 */}
                            <div className="max-h-60 overflow-y-auto custom-scrollbar">
                                <pre className="text-xs text-slate-400 bg-black/30 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap break-words pointer-events-auto select-text">
                                    {JSON.stringify(record.intent_analysis, null, 2)}
                                </pre>
                            </div>
                        </div>
                    )}

                    {/* 深度分析 (如果存在) */}
                    {record.deep_analysis && Object.keys(record.deep_analysis).length > 0 && (
                        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                            <div className="text-xs text-slate-400 mb-2 flex items-center gap-1">
                                <Layers size={12} />
                                深度分析
                            </div>
                            {/* 固定高度容器 */}
                            <div className="max-h-60 overflow-y-auto custom-scrollbar">
                                <pre className="text-xs text-slate-400 bg-black/30 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap break-words pointer-events-auto select-text">
                                    {JSON.stringify(record.deep_analysis, null, 2)}
                                </pre>
                            </div>
                        </div>
                    )}

                    {/* 新增失败案例 (如果存在) */}
                    {record.newly_failed_cases && record.newly_failed_cases.length > 0 && (
                        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                            <div className="text-xs text-slate-400 mb-2 flex items-center gap-1">
                                <AlertCircle size={12} />
                                新增失败案例 ({record.newly_failed_cases.length})
                            </div>
                            {/* 固定高度容器 */}
                            <div className="max-h-48 overflow-y-auto custom-scrollbar space-y-2">
                                {record.newly_failed_cases.map((item: FailedCase, idx: number) => (
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
                        </div>
                    )}

                    {/* Diff 变更 (如果存在) */}
                    {record.diff && record.diff.length > 0 && (
                        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                            <div className="text-xs text-slate-400 mb-2 flex items-center gap-1">
                                <FileText size={12} />
                                提示词变更
                            </div>
                            {/* 固定高度容器 */}
                            <div className="max-h-48 overflow-y-auto custom-scrollbar">
                                <div className="bg-black/30 rounded-lg p-3 font-mono text-xs space-y-1">
                                    {record.diff.map((line: DiffItem, idx: number) => (
                                        <div
                                            key={idx}
                                            className={`whitespace-pre-wrap break-words ${line.type === 'added'
                                                    ? 'text-green-400 bg-green-500/10'
                                                    : line.type === 'removed'
                                                        ? 'text-red-400 bg-red-500/10'
                                                        : 'text-slate-400'
                                                }`}
                                        >
                                            {line.type === 'added' && '+ '}
                                            {line.type === 'removed' && '- '}
                                            {line.content}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
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
