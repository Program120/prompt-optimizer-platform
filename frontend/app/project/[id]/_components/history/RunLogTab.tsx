import { useState, useEffect } from "react";
import { CheckCircle2, AlertCircle, ArrowRight, Save, X, Search } from "lucide-react";

const API_BASE = "/api";

interface RunLogTabProps {
    taskId?: string;
    totalCount?: number; // From taskStatus
    reasons: Record<string, any>;
    saveReason: (query: string, reason: string, target: string) => Promise<void>;
    onSelectLog: (log: any) => void;
}

export default function RunLogTab({ taskId, totalCount, reasons, saveReason, onSelectLog }: RunLogTabProps) {
    // Local State for Pagination & Data
    const [results, setResults] = useState<any[]>([]);
    const [page, setPage] = useState(1);
    const [hasMore, setHasMore] = useState(true);
    const [isLoadingResults, setIsLoadingResults] = useState(false);
    const [totalResults, setTotalResults] = useState(0);
    const [searchQuery, setSearchQuery] = useState("");
    const [editingReason, setEditingReason] = useState<{ query: string, value: string, target: string } | null>(null);

    // Fetch Logic
    const fetchResults = async (pageNum: number, reset: boolean = false, search: string = "") => {
        if (!taskId) return;
        setIsLoadingResults(true);
        try {
            let url = `${API_BASE}/tasks/${taskId}/results?page=${pageNum}&page_size=20`;
            if (search) {
                url += `&search=${encodeURIComponent(search)}`;
            }
            const res = await fetch(url);
            if (res.ok) {
                const data = await res.json();
                setResults(prev => reset ? data.results : [...prev, ...data.results]);
                setTotalResults(data.total);
                setHasMore(data.page * data.size < data.total);
                setPage(pageNum);
            }
        } catch (e) {
            console.error("Failed to fetch results", e);
        } finally {
            setIsLoadingResults(false);
        }
    };

    // Reset when task changes
    useEffect(() => {
        if (taskId) {
            setResults([]);
            setPage(1);
            setHasMore(true);
            setTotalResults(0);
            fetchResults(1, true, searchQuery);
        }
    }, [taskId]);

    // Search Debounce
    useEffect(() => {
        if (taskId) {
            const timer = setTimeout(() => {
                setResults([]);
                setPage(1);
                fetchResults(1, true, searchQuery);
            }, 500);
            return () => clearTimeout(timer);
        }
    }, [searchQuery]);

    return (
        <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
            {taskId && (
                <div className="mb-3 flex justify-between items-center">
                    <span className="text-xs text-slate-500">
                        已加载 {results.length}/{totalResults || totalCount || '?'} 条
                    </span>
                </div>
            )}

            {/* 搜索框 */}
            <div className="mb-3 relative">
                <input
                    type="text"
                    placeholder="搜索 Query 或 原因..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full bg-black/20 border border-white/5 rounded-lg pl-9 pr-3 py-2 text-xs text-slate-300 focus:border-blue-500/50 outline-none"
                />
                <Search className="absolute left-3 top-2.5 text-slate-500" size={14} />
                {searchQuery && (
                    <button
                        onClick={() => setSearchQuery("")}
                        className="absolute right-3 top-2.5 text-slate-500 hover:text-white"
                    >
                        <X size={14} />
                    </button>
                )}
            </div>

            {results.map((r: any, idx: number) => {
                const reasonItem = reasons[r.query];
                const currentReason = reasonItem?.reason || r.reason;
                const currentTarget = reasonItem?.target || r.target;
                const isEditing = editingReason?.query === r.query;

                return (
                    <div
                        key={idx}
                        className={`p-3 rounded-xl border text-xs mb-2 group relative cursor-pointer ${r.is_correct ? "bg-emerald-500/5 border-emerald-500/20" : "bg-red-500/5 border-red-500/20"}`}
                        onClick={() => onSelectLog({ ...r, reason: currentReason, intervention: reasonItem })}
                    >
                        <div className="flex justify-between items-center mb-1">
                            <div className="flex items-center gap-2">
                                <span className="font-medium text-slate-500">Query {r.index + 1}</span>
                                {r.is_correct ? <CheckCircle2 size={14} className="text-emerald-500" /> : <AlertCircle size={14} className="text-red-500" />}
                            </div>
                        </div>
                        <p className="text-slate-300 mb-1 font-mono break-all" title={r.query}>{r.query}</p>
                        <div className="flex items-center gap-2 text-slate-500 mb-2">
                            <span className="truncate flex-1" title={currentTarget}>预期: {currentTarget}</span>
                            <ArrowRight size={10} />
                            <span className="truncate flex-1 text-slate-400" title={r.output}>输出: {r.output}</span>
                        </div>

                        {/* Reason Display/Edit */}
                        <div className="mt-2 pt-2 border-t border-white/5" onClick={e => e.stopPropagation()}>
                            {isEditing ? (
                                <div className="flex gap-2 items-start">
                                    <textarea
                                        className="flex-1 bg-black/20 border border-white/10 rounded p-1 text-xs text-slate-300 focus:border-blue-500/50 outline-none resize-none"
                                        rows={2}
                                        value={editingReason?.value || ""}
                                        onChange={(e) => setEditingReason(prev => prev ? { ...prev, value: e.target.value } : null)}
                                        placeholder="输入错误原因..."
                                        autoFocus
                                    />
                                    <div className="flex flex-col gap-1">
                                        <button
                                            onClick={() => editingReason && saveReason(r.query, editingReason.value, currentTarget).then(() => setEditingReason(null))}
                                            className="p-1 text-emerald-400 hover:bg-emerald-500/10 rounded"
                                        >
                                            <Save size={12} />
                                        </button>
                                        <button
                                            onClick={() => setEditingReason(null)}
                                            className="p-1 text-slate-400 hover:bg-slate-500/10 rounded"
                                        >
                                            <X size={12} />
                                        </button>
                                    </div>
                                </div>
                            ) : (
                                <div
                                    className={`flex justify-between items-start cursor-pointer hover:bg-white/5 rounded p-1 -mx-1 transition-colors ${!currentReason ? "text-slate-600" : ""}`}
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        setEditingReason({ query: r.query, value: currentReason || "", target: currentTarget });
                                    }}
                                >
                                    <div className="text-xs text-amber-500/80 w-full">
                                        <span className="font-medium mr-1">原因:</span>
                                        {currentReason || "点击添加原因..."}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                );
            })}

            {/* Infinite Scroll Trigger */}
            <div ref={(node) => {
                if (node && !isLoadingResults && hasMore && taskId) {
                    const observer = new IntersectionObserver(entries => {
                        if (entries[0].isIntersecting) {
                            fetchResults(page + 1, false, searchQuery);
                        }
                    }, { threshold: 1.0 });
                    observer.observe(node);
                    return () => observer.disconnect();
                }
            }} className="py-4 text-center">
                {isLoadingResults && (
                    <div className="flex justify-center items-center gap-2 text-slate-500 text-xs">
                        <div className="w-4 h-4 border-2 border-slate-500/30 border-t-slate-500 rounded-full animate-spin"></div>
                        加载更多...
                    </div>
                )}
                {!hasMore && results.length > 0 && (
                    <span className="text-slate-600 text-xs">没有更多日志了</span>
                )}
            </div>

            {!results.length && !isLoadingResults && <p className="text-center text-slate-600 mt-20">暂无运行日志</p>}
        </div>
    );
}
