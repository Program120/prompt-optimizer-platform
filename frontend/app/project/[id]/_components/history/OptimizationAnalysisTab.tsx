import { Layers, Trash2, TrendingUp } from "lucide-react";
import { NoteSection } from "./NoteSection";

interface OptimizationAnalysisTabProps {
    records?: any[];
    onSelectRecord?: (record: any) => void;
    onDeleteRecord?: (record: any) => void;
    onSaveNote: (type: string, id: string, value: string) => Promise<boolean>;
}

export default function OptimizationAnalysisTab({ records, onSelectRecord, onDeleteRecord, onSaveNote }: OptimizationAnalysisTabProps) {
    return (
        <div className="flex-1 overflow-y-auto p-4 custom-scrollbar space-y-3">
            {records?.map((record: any) => (
                <div
                    key={record.id}
                    onClick={() => onSelectRecord && onSelectRecord(record)}
                    className="relative p-3 rounded-xl border border-purple-500/20 bg-gradient-to-br from-purple-600/5 to-blue-600/5 hover:from-purple-600/10 hover:to-blue-600/10 cursor-pointer transition-all group"
                >
                    {/* 头部: 版本号和时间 */}
                    <div className="flex justify-between items-center mb-2">
                        <div className="flex items-center gap-2">
                            <div className="w-6 h-6 rounded-lg bg-purple-500/20 flex items-center justify-center">
                                <Layers size={12} className="text-purple-400" />
                            </div>
                            <span className="text-sm font-bold text-white">v{record.version}</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-[10px] text-slate-500">
                                {new Date(record.created_at || record.timestamp).toLocaleString()}
                            </span>
                            {onDeleteRecord && (
                                <button
                                    onClick={(e) => { e.stopPropagation(); onDeleteRecord(record); }}
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
                            {((record.accuracy_before || 0) * 100).toFixed(1)}%
                        </span>
                        <TrendingUp size={12} className="text-emerald-400" />
                        <span className="text-emerald-400 font-medium">
                            {record.accuracy_after !== null && record.accuracy_after !== undefined
                                ? `${(record.accuracy_after * 100).toFixed(1)}%`
                                : "待验证"}
                        </span>
                    </div>

                    {/* 应用策略 - 优先尝试 applied_strategies 数组，否则尝试 strategy 字符串 */}
                    {(record.applied_strategies?.length > 0 || record.strategy) && (
                        <div className="flex flex-wrap gap-1 mb-2">
                            {(record.applied_strategies || [record.strategy])
                                .filter((s: any) => s) // 过滤空值
                                .slice(0, 3)
                                .map((strategy: string, sIdx: number) => (
                                    <span
                                        key={sIdx}
                                        className="px-1.5 py-0.5 bg-blue-500/10 text-blue-400 text-[10px] rounded border border-blue-500/20"
                                    >
                                        {strategy}
                                    </span>
                                ))}
                            {(record.applied_strategies || [record.strategy]).length > 3 && (
                                <span className="text-[10px] text-slate-500">
                                    +{(record.applied_strategies || [record.strategy]).length - 3}
                                </span>
                            )}
                        </div>
                    )}

                    {/* 优化总结预览 */}
                    <p className="text-[11px] text-slate-400 line-clamp-2">
                        {record.analysis_summary || (typeof record.analysis === 'string' ? "暂无优化总结" : (record.analysis?.summary || "暂无优化总结"))}
                    </p>

                    <NoteSection
                        type="knowledge"
                        id={record.id}
                        initialNote={record.note}
                        onSave={onSaveNote}
                    />
                </div>
            ))}
            {!records?.length && (
                <div className="text-center mt-20">
                    <Layers size={32} className="mx-auto text-slate-600 mb-2" />
                    <p className="text-slate-600 text-sm">暂无优化分析记录</p>
                    <p className="text-slate-700 text-xs mt-1">完成优化后将自动记录分析历史</p>
                </div>
            )}
        </div>
    );
}
