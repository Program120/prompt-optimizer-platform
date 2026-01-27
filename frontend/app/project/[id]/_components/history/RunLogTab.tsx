import { useState, useEffect, useRef, useCallback } from "react";
import { CheckCircle2, AlertCircle, ArrowRight, Save, X, Search, FlaskConical } from "lucide-react";
import TestResultModal, { TestResultData } from "@/app/components/TestResultModal";

const API_BASE = "/api";

interface RunLogTabProps {
    taskId?: string;
    projectId?: string;
    totalCount?: number; // From taskStatus
    currentIndex?: number; // 当前处理进度，用于实时刷新
    reasons: Record<string, any>;
    saveReason: (query: string, reason: string, target: string) => Promise<boolean>;
    onSelectLog: (log: any) => void;
}

export default function RunLogTab({ taskId, projectId, totalCount, currentIndex, reasons, saveReason, onSelectLog }: RunLogTabProps) {
    // Local State for Pagination & Data
    const [results, setResults] = useState<any[]>([]);
    const [page, setPage] = useState(1);
    const [hasMore, setHasMore] = useState(true);
    // 分离两种加载状态：无限滚动加载 和 定时刷新
    const [isLoadingMore, setIsLoadingMore] = useState(false);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [totalResults, setTotalResults] = useState(0);
    const [searchQuery, setSearchQuery] = useState("");
    const [filterStatus, setFilterStatus] = useState<'all' | 'success' | 'failed'>('all');
    const [editingReason, setEditingReason] = useState<{ query: string, value: string, target: string } | null>(null);
    // 保存反馈状态
    const [saveFeedback, setSaveFeedback] = useState<{ query: string, success: boolean } | null>(null);

    // Test State
    const [testingQuery, setTestingQuery] = useState<string | null>(null);
    const [testResult, setTestResult] = useState<TestResultData | null>(null);

    // Ref for scroll container (用于 IntersectionObserver 的 root)
    const scrollContainerRef = useRef<HTMLDivElement>(null);
    // Ref for infinite scroll trigger element
    const loadMoreRef = useRef<HTMLDivElement>(null);
    // 使用 ref 记录当前已加载的页数，避免闭包问题
    const loadedPagesRef = useRef<number>(1);

    /**
     * 执行单条测试
     */
    const handleTest = async (query: string, target: string, reason: string) => {
        if (!projectId) return;
        setTestingQuery(query);
        try {
            const res = await fetch(`${API_BASE}/projects/${projectId}/interventions/test`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ query, target, reason })
            });
            if (res.ok) {
                const data = await res.json();
                setTestResult({
                    query,
                    is_correct: data.is_correct,
                    output: data.output,
                    reason: data.reason,
                    target: target,
                    latency_ms: data.latency_ms,
                    request_id: data.request_id
                });
            } else {
                const err = await res.json();
                alert(`测试失败: ${err.detail || "未知错误"}`);
            }
        } catch (e) {
            console.error(e);
            alert("测试请求出错");
        } finally {
            setTestingQuery(null);
        }
    };



    /**
     * 加载更多数据 (用于无限滚动)
     */
    /**
     * 加载更多数据 (用于无限滚动)
     */
    const loadMoreResults = useCallback(async (pageNum: number, search: string = "", status: 'all' | 'success' | 'failed' = 'all') => {
        if (!taskId) return;
        setIsLoadingMore(true);
        try {
            let url: string = `${API_BASE}/tasks/${taskId}/results?page=${pageNum}&page_size=20`;
            if (search) {
                url += `&search=${encodeURIComponent(search)}`;
            }
            if (status !== 'all') {
                url += `&type=${status === 'success' ? 'success' : 'error'}`;
            }
            const res: Response = await fetch(url);
            if (res.ok) {
                const data = await res.json();
                // 正序排列：按 index 从小到大
                const sortedResults: any[] = [...data.results].sort((a: any, b: any) => (a.index || 0) - (b.index || 0));
                setResults(prev => [...prev, ...sortedResults]);
                setTotalResults(data.total);
                setHasMore(data.page * (data.page_size || data.size || 20) < data.total);
                setPage(pageNum);
                loadedPagesRef.current = pageNum;
            }
        } catch (e) {
            console.error("加载更多数据失败", e);
        } finally {
            setIsLoadingMore(false);
        }
    }, [taskId]);

    /**
     * 刷新数据 (用于初始加载和定时刷新)
     * @param pageSize 要获取的数据量
     * @param search 搜索关键词
     */
    /**
     * 刷新数据 (用于初始加载和定时刷新)
     * @param pageSize 要获取的数据量
     * @param search 搜索关键词
     * @param status 过滤状态
     */
    const refreshResults = useCallback(async (pageSize: number, search: string = "", status: 'all' | 'success' | 'failed' = 'all') => {
        if (!taskId) return;
        setIsRefreshing(true);
        try {
            let url: string = `${API_BASE}/tasks/${taskId}/results?page=1&page_size=${pageSize}`;
            if (search) {
                url += `&search=${encodeURIComponent(search)}`;
            }
            if (status !== 'all') {
                url += `&type=${status === 'success' ? 'success' : 'error'}`;
            }
            const res: Response = await fetch(url);
            if (res.ok) {
                const data = await res.json();
                // 正序排列：按 index 从小到大
                const sortedResults: any[] = [...data.results].sort((a: any, b: any) => (a.index || 0) - (b.index || 0));
                setResults(prev => {
                    // 如果本地已有更多数据（可能是刷新期间触发了加载更多），则保留尾部数据
                    if (prev.length > sortedResults.length) {
                        return [...sortedResults, ...prev.slice(sortedResults.length)];
                    }
                    return sortedResults;
                });
                setTotalResults(data.total);
                // 根据实际获取的数据量更新分页状态
                const pagesLoaded: number = Math.ceil(sortedResults.length / 20);
                setPage(pagesLoaded || 1);
                loadedPagesRef.current = pagesLoaded || 1;
                setHasMore(sortedResults.length < data.total);
            }
        } catch (e) {
            console.error("刷新数据失败", e);
        } finally {
            setIsRefreshing(false);
        }
    }, [taskId]);

    // Reset when task changes
    useEffect(() => {
        if (taskId) {
            setResults([]);
            setPage(1);
            setHasMore(true);
            setTotalResults(0);
            loadedPagesRef.current = 1;
            setFilterStatus('all'); // Reset filter
            refreshResults(20, searchQuery, 'all');
        }
    }, [taskId]);

    /**
     * 实时更新：任务运行时每隔2秒刷新一次数据
     * 刷新时保持当前已加载的数据量，而不是只刷新第一页
     */
    useEffect(() => {
        if (!taskId) return;

        // 启动定时刷新
        const interval = setInterval(() => {
            // 使用 ref 获取当前已加载的页数，避免闭包问题
            const currentPages: number = loadedPagesRef.current;
            const dataToFetch: number = currentPages * 20;
            refreshResults(dataToFetch, searchQuery, filterStatus);
        }, 2000);

        return () => clearInterval(interval);
    }, [taskId, searchQuery, filterStatus, refreshResults, isLoadingMore]);

    // Search Debounce
    useEffect(() => {
        if (taskId) {
            const timer = setTimeout(() => {
                setResults([]);
                setPage(1);
                loadedPagesRef.current = 1;
                refreshResults(20, searchQuery, filterStatus);
            }, 500);
            return () => clearTimeout(timer);
        }
    }, [searchQuery]);

    /**
     * 无限滚动 Observer
     * 注意：只在 isLoadingMore 为 false 时设置 observer，isRefreshing 不影响
     */
    useEffect(() => {
        const node = loadMoreRef.current;
        const root = scrollContainerRef.current;
        if (!node || isLoadingMore || !hasMore || !taskId) return;

        const observer = new IntersectionObserver(entries => {
            if (entries[0].isIntersecting && hasMore && !isLoadingMore) {
                loadMoreResults(page + 1, searchQuery, filterStatus);
            }
        }, {
            threshold: 0.1,
            root: root,
            rootMargin: "100px"
        });

        observer.observe(node);
        return () => observer.disconnect();
    }, [hasMore, isLoadingMore, page, taskId, loadMoreResults, searchQuery, filterStatus]);

    // Filter Change Effect
    useEffect(() => {
        if (taskId) {
            setResults([]);
            setPage(1);
            loadedPagesRef.current = 1;
            refreshResults(20, searchQuery, filterStatus);
        }
    }, [filterStatus]);

    return (
        <div ref={scrollContainerRef} className="flex-1 overflow-y-auto p-4 custom-scrollbar">
            {taskId && (
                <div className="mb-3 flex flex-col gap-2">
                    {/* 过滤器 */}
                    <div className="flex gap-2">
                        <button
                            onClick={() => setFilterStatus('all')}
                            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${filterStatus === 'all'
                                ? "bg-blue-500/20 text-blue-400 border border-blue-500/30"
                                : "bg-white/5 text-slate-400 border border-white/5 hover:bg-white/10"
                                }`}
                        >
                            全部
                        </button>
                        <button
                            onClick={() => setFilterStatus('success')}
                            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${filterStatus === 'success'
                                ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                                : "bg-white/5 text-slate-400 border border-white/5 hover:bg-white/10"
                                }`}
                        >
                            成功
                        </button>
                        <button
                            onClick={() => setFilterStatus('failed')}
                            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${filterStatus === 'failed'
                                ? "bg-red-500/20 text-red-400 border border-red-500/30"
                                : "bg-white/5 text-slate-400 border border-white/5 hover:bg-white/10"
                                }`}
                        >
                            失败
                        </button>
                    </div>

                    <div className="flex justify-between items-center">
                        <span className="text-xs text-slate-500">
                            已加载 {results.length}/{totalResults || totalCount || '?'} 条
                        </span>
                    </div>
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


            {/* 使用 Map 进行数据去重，以 query 为 key，避免调整期望意图后数据重复 */}
            {Array.from(
                new Map(results.map((r: any) => [r.query, r])).values()
            ).map((r: any, idx: number) => {
                const reasonItem = reasons[r.query];
                // 使用 ?? 而非 ||，确保空字符串 "" 也能正确显示（|| 会将空字符串视为 falsy）
                const currentReason = reasonItem?.reason ?? r.reason;
                const currentTarget = reasonItem?.target ?? r.target;
                const isEditing = editingReason?.query === r.query;

                // 直接使用后端返回的 is_correct（后端已使用最新的意图修正计算）
                const isCorrect = r.is_correct;

                return (
                    <div
                        key={`${r.query}-${idx}`}
                        className={`p-3 rounded-xl border text-xs mb-2 group relative cursor-pointer ${isCorrect ? "bg-emerald-500/5 border-emerald-500/20" : "bg-red-500/5 border-red-500/20"}`}
                        onClick={() => onSelectLog({ ...r, reason: currentReason, intervention: reasonItem, is_correct: isCorrect })}
                    >
                        <div className="flex justify-between items-center mb-1">
                            <div className="flex items-center gap-2">
                                <span className="font-medium text-slate-500">Query {(r.index ?? idx) + 1}</span>
                                {isCorrect ? <CheckCircle2 size={14} className="text-emerald-500" /> : <AlertCircle size={14} className="text-red-500" />}
                            </div>
                        </div>
                        <div className="text-slate-300 mb-2 line-clamp-1">{r.query}</div>
                        <div className="flex items-center gap-2 text-slate-400">
                            <span className="text-slate-500">预期:</span>
                            <span className="text-blue-400 line-clamp-1 max-w-[40%]">{currentTarget}</span>
                            <ArrowRight size={12} className="text-slate-600" />
                            <span className="text-slate-500">输出:</span>
                            <span className={`line-clamp-1 max-w-[40%] ${isCorrect ? "text-emerald-400" : "text-red-400"}`}>
                                {r.output?.substring(0, 60)}...
                            </span>
                        </div>

                        {/* 操作栏 */}
                        <div className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity flex gap-1">
                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    handleTest(r.query, currentTarget || "", currentReason || "");
                                }}
                                disabled={!!testingQuery}
                                className={`p-1.5 rounded transition-colors ${testingQuery === r.query
                                    ? "text-cyan-400 bg-cyan-500/10 animate-pulse"
                                    : "text-slate-400 hover:text-indigo-400 hover:bg-slate-700/50"
                                    }`}
                                title="执行单测"
                            >
                                {testingQuery === r.query ? (
                                    <div className="w-3 h-3 border-2 border-cyan-500/30 border-t-cyan-500 rounded-full animate-spin" />
                                ) : (
                                    <FlaskConical size={14} />
                                )}
                            </button>
                        </div>

                        {/* 原因编辑 */}
                        <div className="mt-2 border-t border-white/5 pt-2">
                            {isEditing && editingReason ? (
                                <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
                                    <input
                                        type="text"
                                        value={editingReason.value}
                                        onChange={(e) => setEditingReason({ ...editingReason, value: e.target.value })}
                                        className="flex-1 bg-black/30 border border-white/10 rounded px-2 py-1 text-xs focus:border-blue-500 outline-none"
                                        placeholder="输入原因..."
                                        autoFocus
                                    />
                                    <button
                                        onClick={async () => {
                                            const success = await saveReason(r.query, editingReason.value, editingReason.target);
                                            setEditingReason(null);
                                            // 显示保存反馈
                                            setSaveFeedback({ query: r.query, success });
                                            // 2秒后清除反馈
                                            setTimeout(() => setSaveFeedback(null), 2000);
                                        }}
                                        className="bg-emerald-600 hover:bg-emerald-500 px-2 py-1 rounded text-xs"
                                    >
                                        <Save size={12} />
                                    </button>
                                    <button
                                        onClick={() => setEditingReason(null)}
                                        className="bg-slate-600 hover:bg-slate-500 px-2 py-1 rounded text-xs"
                                    >
                                        <X size={12} />
                                    </button>
                                </div>
                            ) : (
                                <div
                                    className={`flex justify-between items-start cursor-pointer hover:bg-white/5 rounded p-1 -mx-1 transition-colors ${!currentReason ? "text-slate-600" : ""}`}
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        setEditingReason({ query: r.query, value: currentReason || "", target: currentTarget });
                                    }}
                                >
                                    <div className="text-xs text-amber-500/80 w-full flex items-center gap-2">
                                        <span className="font-medium mr-1">原因:</span>
                                        {currentReason || "点击添加原因..."}
                                        {/* 保存反馈提示 */}
                                        {saveFeedback && saveFeedback.query === r.query && (
                                            <span className={`text-[10px] px-1.5 py-0.5 rounded ${saveFeedback.success ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"}`}>
                                                {saveFeedback.success ? "✓ 已保存" : "✗ 保存失败"}
                                            </span>
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                );
            })}

            {/* Infinite Scroll Trigger */}
            <div ref={loadMoreRef} className="py-4 text-center">
                {isLoadingMore && (
                    <div className="flex justify-center items-center gap-2 text-slate-500 text-xs">
                        <div className="w-4 h-4 border-2 border-slate-500/30 border-t-slate-500 rounded-full animate-spin"></div>
                        加载更多...
                    </div>
                )}
                {!hasMore && results.length > 0 && (
                    <span className="text-slate-600 text-xs">没有更多日志了</span>
                )}
            </div>

            {!results.length && !isLoadingMore && !isRefreshing && <p className="text-center text-slate-600 mt-20">暂无运行日志</p>}

            {/* 测试结果 Modal */}
            {testResult && (
                <TestResultModal
                    testResult={testResult}
                    onClose={() => setTestResult(null)}
                />
            )}
        </div>
    );
}
