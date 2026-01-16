import { Trash2, Download, TrendingUp, GitBranch, Sparkles } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { NoteSection } from "./NoteSection";

interface IterationHistoryTabProps {
    iterations?: any[];
    onSelectIteration: (iteration: any) => void;
    onDeleteIteration?: (iteration: any) => void;
    onSaveNote: (type: string, id: string, value: string) => Promise<boolean>;
}

export default function IterationHistoryTab({ iterations, onSelectIteration, onDeleteIteration, onSaveNote }: IterationHistoryTabProps) {
    const sortedIterations = [...(iterations || [])].sort((a: any, b: any) => (b.version || 0) - (a.version || 0));

    // Helper to format date safely
    const formatDate = (ts: string) => {
        try {
            if (!ts) return "未知时间";
            if (ts.includes("-") || ts.includes("T")) return new Date(ts).toLocaleString();
            const num = parseInt(ts);
            return new Date(num.toString().length === 10 ? num * 1000 : num).toLocaleString();
        } catch { return "未知时间"; }
    };

    return (
        <div className="flex-1 overflow-y-auto p-4 custom-scrollbar space-y-3">
            <AnimatePresence mode="popLayout">
                {sortedIterations.map((it: any, idx: number) => (
                    <motion.div
                        layout
                        initial={{ opacity: 0, y: 15 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.98 }}
                        transition={{ duration: 0.2, delay: idx * 0.03 }}
                        key={it.id}
                        onClick={() => onSelectIteration(it)}
                        className="relative p-3 rounded-xl border border-blue-500/20 bg-gradient-to-br from-blue-600/5 to-indigo-600/5 hover:from-blue-600/10 hover:to-indigo-600/10 cursor-pointer transition-all group"
                    >
                        {/* 头部: 版本号和时间 */}
                        <div className="flex justify-between items-center mb-2">
                            <div className="flex items-center gap-2">
                                <div className="w-6 h-6 rounded-lg bg-blue-500/20 flex items-center justify-center">
                                    <GitBranch size={12} className="text-blue-400" />
                                </div>
                                <span className="text-sm font-bold text-white">迭代 #{it.version}</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="text-[10px] text-slate-500">
                                    {formatDate(it.created_at)}
                                </span>
                                {onDeleteIteration && (
                                    <button
                                        onClick={(e) => { e.stopPropagation(); onDeleteIteration(it); }}
                                        className="opacity-0 group-hover:opacity-100 p-1 text-slate-500 hover:text-red-400 transition-all"
                                        title="删除记录"
                                    >
                                        <Trash2 size={12} />
                                    </button>
                                )}
                            </div>
                        </div>

                        {/* 准确率变化 */}
                        <div className="flex items-center gap-2 mb-2 text-xs">
                            <span className="text-orange-400">
                                {((it.accuracy_before || 0) * 100).toFixed(1)}%
                            </span>
                            <TrendingUp size={12} className="text-emerald-400" />
                            <span className="text-emerald-400 font-medium">
                                {it.accuracy_after !== null && it.accuracy_after !== undefined
                                    ? `${(it.accuracy_after * 100).toFixed(1)}%`
                                    : "待验证"}
                            </span>
                            {it.dataset_name && (
                                <span className="ml-auto text-[10px] text-slate-400 bg-slate-800/50 px-1.5 py-0.5 rounded border border-slate-700/30 truncate max-w-[100px] flex items-center gap-1" title={it.dataset_name}>
                                    <Sparkles size={8} className="text-indigo-400" />
                                    {it.dataset_name}
                                </span>
                            )}
                        </div>

                        {/* 优化后 Prompt 预览 */}
                        <p className="text-[11px] text-slate-400 line-clamp-2">
                            {it.optimized_prompt || it.previous_prompt || "无内容"}
                        </p>

                        {/* 下载按钮 */}
                        {it.task_id && (
                            <div className="flex justify-end pt-2 mt-2 border-t border-white/5">
                                <a
                                    href={`http://localhost:8000/api/tasks/${it.task_id}/export`}
                                    target="_blank"
                                    rel="noreferrer"
                                    onClick={(e) => e.stopPropagation()}
                                    className="flex items-center gap-1 text-[10px] text-blue-400 hover:text-blue-300 transition-colors"
                                >
                                    <Download size={12} />
                                    下载验证结果
                                </a>
                            </div>
                        )}

                        <NoteSection
                            type="iteration"
                            id={it.id}
                            initialNote={it.note}
                            onSave={onSaveNote}
                        />
                    </motion.div>
                ))}
            </AnimatePresence>

            {/* 空状态 */}
            {!sortedIterations.length && (
                <div className="flex flex-col items-center justify-center py-20">
                    <motion.div
                        initial={{ opacity: 0, scale: 0.8 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500/20 to-indigo-500/20 flex items-center justify-center mb-4 border border-blue-500/20"
                    >
                        <GitBranch className="w-8 h-8 text-blue-400" />
                    </motion.div>
                    <p className="text-slate-400 text-sm">暂无优化历史</p>
                    <p className="text-slate-600 text-xs mt-1">完成优化后将自动记录迭代历史</p>
                </div>
            )}
        </div>
    );
}
