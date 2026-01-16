import { useState, useEffect } from "react";
import { CheckCircle2, AlertCircle, ArrowRight, Download, Clock, FileText, Database, X, Copy, Layers, TrendingUp, Trash2, Edit3, Save, Search, RotateCcw } from "lucide-react";

const API_BASE = "/api";

interface HistoryPanelProps {
    taskStatus: any;
    project: any;
    runHistory: any[];  // 运行历史列表 (List of past execution tasks)
    onSelectLog: (log: any) => void;
    onSelectIteration: (iteration: any) => void;
    // 知识库相关
    knowledgeRecords?: any[];
    onSelectKnowledge?: (record: any) => void;

    // Delete handlers
    onDeleteTask?: (task: any) => void;
    onDeleteIteration?: (iteration: any) => void;
    onDeleteKnowledge?: (record: any) => void;

    // Refresh handler
    onRefresh?: () => void;
    reasonsUpdateCount?: number;
    fileId?: string;
}

export default function HistoryPanel({
    taskStatus,
    project,
    runHistory,
    fileId,
    onSelectLog,
    onSelectIteration,
    knowledgeRecords,
    onSelectKnowledge,
    onDeleteTask,
    onDeleteIteration,
    onDeleteKnowledge,
    onRefresh,
    reasonsUpdateCount = 0
}: HistoryPanelProps) {
    const [activeTab, setActiveTab] = useState("run"); // run, history, runHistory
    const [showPromptModal, setShowPromptModal] = useState(false);
    const [currentPrompt, setCurrentPrompt] = useState("");

    // Results pagination state
    const [results, setResults] = useState<any[]>([]);
    const [page, setPage] = useState(1);
    const [hasMore, setHasMore] = useState(true);
    const [isLoadingResults, setIsLoadingResults] = useState(false);
    const [totalResults, setTotalResults] = useState(0);

    // Reset results when task changes
    useEffect(() => {
        if (taskStatus?.id) {
            setResults([]);
            setPage(1);
            setHasMore(true);
            setTotalResults(0);
            fetchResults(taskStatus.id, 1, true);
        }
    }, [taskStatus?.id]);

    // Search state
    const [searchQuery, setSearchQuery] = useState("");

    // Intent Intervention State
    const [intentItems, setIntentItems] = useState<any[]>([]);
    const [intentPage, setIntentPage] = useState(1);
    const [intentTotal, setIntentTotal] = useState(0);
    const [intentLoading, setIntentLoading] = useState(false);
    const [intentSearch, setIntentSearch] = useState("");
    const [intentFilter, setIntentFilter] = useState("all"); // all, modified, reason_added

    // Fetch Intent Data
    const fetchIntentData = async (pageNum: number = 1, search: string = "") => {
        if (!project?.id) return;
        setIntentLoading(true);
        try {
            let url = `${API_BASE}/projects/${project.id}/interventions?page=${pageNum}&page_size=20`;
            if (search) url += `&search=${encodeURIComponent(search)}`;
            if (intentFilter !== "all") url += `&filter_type=${intentFilter}`;
            if (fileId) url += `&file_id=${fileId}`;

            const res = await fetch(url);
            if (res.ok) {
                const data = await res.json();
                setIntentItems(data.items || []);
                setIntentTotal(data.total || 0);
                setIntentPage(data.page || 1);
            }
        } catch (e) { console.error("Failed to fetch intent data", e); }
        finally { setIntentLoading(false); }
    };

    useEffect(() => {
        if (activeTab === "intent") {
            fetchIntentData(intentPage, intentSearch);
        }
    }, [activeTab, intentPage, intentSearch, intentFilter, project?.id, fileId, reasonsUpdateCount]);

    // Intent CRUD
    const handleAddIntentRow = async () => {
        // Placeholder for adding new row - maybe open modal or just insert empty row?
        // For simple UX, let's insert a temp row at top or ask user.
        // Or implement inline 'New Row' form.
        // Prompt user for Query?
        const q = prompt("请输入 Query:");
        if (q && q.trim()) {
            await saveReason(q, "", ""); // Create empty
            fetchIntentData(1, intentSearch); // Refresh
        }
    };

    const handleExportIntent = () => {
        window.open(`${API_BASE}/projects/${project?.id}/interventions/export`, '_blank');
    };

    const handleResetIntervention = async (query: string) => {
        if (!window.confirm("确定要重置这条记录吗？\n这将恢复原始 Target 并清空失败原因。")) return;
        try {
            const res = await fetch(`${API_BASE}/projects/${project.id}/interventions/reset`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ query })
            });
            if (res.ok) {
                fetchIntentData(intentPage, intentSearch);
            } else {
                alert("重置失败");
            }
        } catch (e) { console.error(e); alert("重置出错"); }
    };

    // Debounce search

    // Debounce search
    useEffect(() => {
        if (taskStatus?.id) {
            const timer = setTimeout(() => {
                setResults([]);
                setPage(1);
                setHasMore(true);
                setTotalResults(0);
                fetchResults(taskStatus.id, 1, true, searchQuery);
            }, 500);
            return () => clearTimeout(timer);
        }
    }, [searchQuery, taskStatus?.id]);

    // Fetch results function
    const fetchResults = async (taskId: string, pageNum: number, reset: boolean = false, search: string = "") => {
        if (!taskId) return;
        setIsLoadingResults(true);
        try {
            let url = `${API_BASE}/tasks/${taskId}/results?page=${pageNum}&page_size=50`;
            if (search) {
                url += `&search=${encodeURIComponent(search)}`;
            }
            const res = await fetch(url);
            if (res.ok) {
                const data = await res.json();
                setResults(prev => reset ? data.results : [...prev, ...data.results]);
                setTotalResults(data.total);
                setHasMore(data.results.length === 50); // If less than page_size, no more
            }
        } catch (e) {
            console.error("Failed to fetch results", e);
        } finally {
            setIsLoadingResults(false);
        }
    };

    const loadMoreResults = () => {
        if (!hasMore || isLoadingResults || !taskStatus?.id) return;
        const nextPage = page + 1;
        setPage(nextPage);
        fetchResults(taskStatus.id, nextPage, false, searchQuery);
    };

    // Note editing state
    const [editingNote, setEditingNote] = useState<{ type: 'task' | 'iteration' | 'knowledge', id: string, value: string } | null>(null);

    // Optimistic UI state for notes: stores { [key]: noteValue }
    // Key format: `${type}_${id}`
    // This allows immediate feedback while background refresh happens
    const [localNotes, setLocalNotes] = useState<Record<string, string>>({});

    // Reasons state
    const [reasons, setReasons] = useState<Record<string, any>>({});
    // Reason editing state
    const [editingReason, setEditingReason] = useState<{ query: string, value: string, target: string } | null>(null);
    const [selectedReasons, setSelectedReasons] = useState<Set<string>>(new Set());
    const [reasonSearch, setReasonSearch] = useState("");
    const [confirmDeleteQuery, setConfirmDeleteQuery] = useState<string | null>(null);

    const toggleReasonSelection = (query: string) => {
        const newSet = new Set(selectedReasons);
        if (newSet.has(query)) newSet.delete(query);
        else newSet.add(query);
        setSelectedReasons(newSet);
    };

    const getFilteredReasons = () => {
        if (!reasonSearch) return Object.values(reasons);
        return Object.values(reasons).filter((r: any) =>
            r.query.toLowerCase().includes(reasonSearch.toLowerCase())
        );
    };

    const toggleSelectAllReasons = () => {
        const visibleReasons = getFilteredReasons();
        const visibleQueries = visibleReasons.map((r: any) => r.query);
        const allSelected = visibleQueries.every(q => selectedReasons.has(q));

        const newSet = new Set(selectedReasons);
        if (allSelected) {
            visibleQueries.forEach(q => newSet.delete(q));
        } else {
            visibleQueries.forEach(q => newSet.add(q));
        }
        setSelectedReasons(newSet);
    };

    const deleteReason = async (query: string) => {
        try {
            const res = await fetch(`${API_BASE}/projects/${project.id}/interventions?query=${encodeURIComponent(query)}`, {
                method: "DELETE"
            });
            if (res.ok) {
                fetchReasons();
                const newSet = new Set(selectedReasons);
                newSet.delete(query);
                setSelectedReasons(newSet);
                setConfirmDeleteQuery(null);
            } else {
                alert("删除失败");
            }
        } catch (e) { console.error(e); alert("删除出错"); }
    };


    const handleBatchDeleteReasons = async () => {
        if (selectedReasons.size === 0) return;
        if (!window.confirm(`确定要删除选中的 ${selectedReasons.size} 条记录吗？`)) return;
        try {
            const res = await fetch(`${API_BASE}/projects/${project.id}/reasons/batch`, {
                method: "DELETE",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(Array.from(selectedReasons))
            });
            if (res.ok) {
                fetchReasons();
                setSelectedReasons(new Set());
            } else {
                alert("批量删除失败");
            }
        } catch (e) { console.error(e); alert("批量删除出错"); }
    };

    const handleDeleteAllReasons = async () => {
        const allQueries = Object.keys(reasons);
        if (allQueries.length === 0) return;
        if (!window.confirm(`确定要清空所有 ${allQueries.length} 条标注记录吗？此操作不可恢复！`)) return;
        try {
            const res = await fetch(`${API_BASE}/projects/${project.id}/reasons/batch`, {
                method: "DELETE",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(allQueries)
            });
            if (res.ok) {
                fetchReasons();
                setSelectedReasons(new Set());
            } else {
                alert("清空失败");
            }
        } catch (e) { console.error(e); alert("清空出错"); }
    };

    const fetchReasons = async () => {
        if (!project?.id) return;
        try {
            const res = await fetch(`${API_BASE}/projects/${project.id}/interventions`);
            if (res.ok) {
                const data = await res.json();
                const map: Record<string, any> = {};
                data.items.forEach((r: any) => map[r.query] = r); // Note: Update assuming paginated API returns {items: []}
                setReasons(map);
            }
        } catch (e) { console.error("Failed to fetch reasons", e); }
    };

    useEffect(() => {
        fetchReasons();
    }, [project?.id, reasonsUpdateCount]);

    const saveReason = async (query: string, reason: string, target: string) => {
        try {
            const res = await fetch(`${API_BASE}/projects/${project.id}/interventions`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ query, reason, target })
            });
            if (res.ok) {
                await fetchReasons();
                setEditingReason(null);
            } else {
                alert("保存原因失败");
            }
        } catch (e) {
            console.error(e);
            alert("保存原因出错");
        }
    };


    // 格式化时间戳
    const formatTime = (timestamp: string) => {
        if (!timestamp) return "未知";
        try {
            const ts = parseInt(timestamp) * 1000;
            return new Date(ts).toLocaleString();
        } catch {
            return "未知";
        }
    };

    // 获取状态标签样式
    const getStatusStyle = (status: string) => {
        switch (status) {
            case "running":
                return "bg-blue-500/20 text-blue-400";
            case "completed":
                return "bg-emerald-500/20 text-emerald-400";
            case "stopped":
                return "bg-orange-500/20 text-orange-400";
            default:
                return "bg-slate-500/20 text-slate-400";
        }
    };

    const getStatusText = (status: string) => {
        switch (status) {
            case "running": return "运行中";
            case "completed": return "已完成";
            case "stopped": return "已停止";
            case "paused": return "已暂停";
            default: return status;
        }
    };

    const handleViewPrompt = (prompt: string, e: React.MouseEvent) => {
        e.stopPropagation();
        setCurrentPrompt(prompt);
        setShowPromptModal(true);
    };

    const copyPrompt = () => {
        navigator.clipboard.writeText(currentPrompt);
    };

    // 监听 ESC 键关闭
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === "Escape" && showPromptModal) {
                setShowPromptModal(false);
            }
        };
        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [showPromptModal]);

    const handleDelete = (e: React.MouseEvent, type: 'task' | 'iteration' | 'knowledge', item: any) => {
        e.stopPropagation();
        if (!window.confirm("确定要删除这条记录吗？删除后不可恢复。")) {
            return;
        }

        if (type === 'task' && onDeleteTask) onDeleteTask(item);
        if (type === 'iteration' && onDeleteIteration) onDeleteIteration(item);
        if (type === 'knowledge' && onDeleteKnowledge) onDeleteKnowledge(item);
    };

    const startEditingNote = (e: React.MouseEvent, type: 'task' | 'iteration' | 'knowledge', id: string, currentNote: string) => {
        e.stopPropagation();
        // Use local note if available for most up-to-date value
        const key = `${type}_${id}`;
        const noteValue = localNotes[key] !== undefined ? localNotes[key] : (currentNote || "");
        setEditingNote({ type, id, value: noteValue });
    };

    const saveNote = async (e?: React.MouseEvent) => {
        if (e) e.stopPropagation();
        if (!editingNote) return;

        const { type, id, value } = editingNote;
        const key = `${type}_${id}`;
        const previousValue = localNotes[key];

        // Optimistic update
        setLocalNotes(prev => ({ ...prev, [key]: value }));
        setEditingNote(null);

        try {
            let url = "";
            let method = "PUT";
            let body = {};

            if (type === 'task') {
                url = `${API_BASE}/projects/${project.id}/tasks/${id}/note`;
                body = { note: value };
            } else if (type === 'iteration') {
                url = `${API_BASE}/projects/${project.id}/iterations/${id}/note`;
                body = { note: value };
            } else if (type === 'knowledge') {
                url = `${API_BASE}/projects/${project.id}/knowledge-base/${id}`;
                body = { note: value };
            }

            const response = await fetch(url, {
                method,
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body)
            });

            if (response.ok) {
                if (onRefresh) onRefresh();
            } else {
                // Revert on failure
                setLocalNotes(prev => {
                    const newState = { ...prev };
                    if (previousValue !== undefined) {
                        newState[key] = previousValue;
                    } else {
                        delete newState[key];
                    }
                    return newState;
                });
                alert("保存备注失败");
            }
        } catch (err) {
            console.error(err);
            // Revert on error
            setLocalNotes(prev => {
                const newState = { ...prev };
                if (previousValue !== undefined) {
                    newState[key] = previousValue;
                } else {
                    delete newState[key];
                }
                return newState;
            });
            alert("保存备注出错");
        }
    };

    const renderNoteSection = (item: any, type: 'task' | 'iteration' | 'knowledge', id: string) => {
        const isEditing = editingNote?.type === type && editingNote?.id === id;
        const key = `${type}_${id}`;
        const note = localNotes[key] !== undefined ? localNotes[key] : (item.note || "");

        return (
            <div className="mt-2 pt-2 border-t border-white/5" onClick={e => e.stopPropagation()}>
                {isEditing ? (
                    <div className="flex gap-2 items-start">
                        <textarea
                            className="flex-1 bg-black/20 border border-white/10 rounded p-1 text-xs text-slate-300 focus:border-blue-500/50 outline-none resize-none"
                            rows={2}
                            value={editingNote.value}
                            onChange={(e) => setEditingNote({ ...editingNote, value: e.target.value })}
                            placeholder="添加备注..."
                            autoFocus
                        />
                        <div className="flex flex-col gap-1">
                            <button
                                onClick={(e) => saveNote(e)}
                                className="p-1 text-emerald-400 hover:bg-emerald-500/10 rounded"
                            >
                                <Save size={12} />
                            </button>
                            <button
                                onClick={() => setEditingNote(null)}
                                className="p-1 text-slate-400 hover:bg-slate-500/10 rounded"
                            >
                                <X size={12} />
                            </button>
                        </div>
                    </div>
                ) : (
                    <div
                        className="flex justify-between items-start group/note cursor-pointer hover:bg-white/5 rounded p-1 -m-1 transition-colors"
                        onClick={(e) => startEditingNote(e, type, id, note)}
                    >
                        <div className="flex-1 text-xs">
                            <span className="text-slate-500 mr-2 font-medium">备注:</span>
                            {note ? (
                                <span className="text-slate-300">{note}</span>
                            ) : (
                                <span className="text-slate-600 italic">无</span>
                            )}
                        </div>
                        <button
                            onClick={(e) => startEditingNote(e, type, id, note)}
                            className={`p-1 text-slate-500 hover:text-blue-400 transition-colors ${!note ? 'opacity-0 group-hover/note:opacity-100' : ''}`}
                            title="编辑备注"
                        >
                            <Edit3 size={12} />
                        </button>
                    </div>
                )}
            </div>
        );
    };

    return (
        <section className="glass rounded-2xl overflow-hidden h-[600px] flex flex-col relative">
            <div className="flex border-b border-white/10">
                <button
                    onClick={() => setActiveTab("run")}
                    className={`flex-1 py-4 text-sm font-medium transition-colors ${activeTab === "run" ? "bg-white/5 text-blue-400 border-b-2 border-blue-500" : "text-slate-500 hover:text-slate-300"}`}
                >
                    运行日志
                </button>
                <button
                    onClick={() => setActiveTab("runHistory")}
                    className={`flex-1 py-4 text-sm font-medium transition-colors ${activeTab === "runHistory" ? "bg-white/5 text-blue-400 border-b-2 border-blue-500" : "text-slate-500 hover:text-slate-300"}`}
                >
                    运行历史
                </button>
                <button
                    onClick={() => setActiveTab("history")}
                    className={`flex-1 py-4 text-sm font-medium transition-colors ${activeTab === "history" ? "bg-white/5 text-blue-400 border-b-2 border-blue-500" : "text-slate-500 hover:text-slate-300"}`}
                >
                    迭代历史
                </button>
                <button
                    onClick={() => setActiveTab("intent")}
                    className={`flex-1 py-4 text-sm font-medium transition-colors ${activeTab === "intent" ? "bg-white/5 text-indigo-400 border-b-2 border-indigo-500" : "text-slate-500 hover:text-slate-300"}`}
                >
                    意图干预
                </button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
                {activeTab === "run" ? (
                    <>
                        {/* 进度信息 (移除了下载按钮) */}
                        {taskStatus?.id && (
                            <div className="mb-3 flex justify-between items-center">
                                <span className="text-xs text-slate-500">
                                    已加载 {results.length}/{totalResults || taskStatus.total_count || '?'} 条
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
                            const isEditing = editingReason?.query === r.query;

                            return (
                                <div
                                    key={idx}
                                    className={`p-3 rounded-xl border text-xs mb-2 group relative cursor-pointer ${r.is_correct ? "bg-emerald-500/5 border-emerald-500/20" : "bg-red-500/5 border-red-500/20"}`}
                                    onClick={() => onSelectLog({ ...r, reason: currentReason })}
                                >
                                    <div className="flex justify-between items-center mb-1">
                                        <div className="flex items-center gap-2">
                                            <span className="font-medium text-slate-500">Query {r.index + 1}</span>
                                            {r.is_correct ? <CheckCircle2 size={14} className="text-emerald-500" /> : <AlertCircle size={14} className="text-red-500" />}
                                        </div>
                                    </div>
                                    <p className="text-slate-300 mb-1 font-mono break-all" title={r.query}>{r.query}</p>
                                    <div className="flex items-center gap-2 text-slate-500 mb-2">
                                        <span className="truncate flex-1" title={r.target}>预期: {r.target}</span>
                                        <ArrowRight size={10} />
                                        <span className="truncate flex-1 text-slate-400" title={r.output}>输出: {r.output}</span>
                                    </div>

                                    {/* Reason Display/Edit */}
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
                                                        onClick={() => editingReason && saveReason(r.query, editingReason.value, r.target)}
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
                                                    setEditingReason({ query: r.query, value: currentReason || "", target: r.target });
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

                        {/* Load More Button */}
                        {hasMore && (
                            <div className="py-2 text-center">
                                <button
                                    onClick={loadMoreResults}
                                    disabled={isLoadingResults}
                                    className="text-xs text-blue-400 hover:text-blue-300 disabled:opacity-50"
                                >
                                    {isLoadingResults ? "加载中..." : "加载更多"}
                                </button>
                            </div>
                        )}

                        {!results.length && !isLoadingResults && <p className="text-center text-slate-600 mt-20">暂无运行日志</p>}
                    </>

                ) : activeTab === "runHistory" ? (
                    // 运行历史 Tab
                    <div className="space-y-3">
                        {runHistory?.map((task: any, idx: number) => (
                            <div
                                key={task.id}
                                className="relative p-3 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 transition-colors group"
                            >
                                {/* 头部: 时间和状态 */}
                                <div className="flex justify-between items-center mb-2">
                                    <div className="flex items-center gap-2 text-xs text-slate-400">
                                        <Clock size={12} />
                                        <span>{formatTime(task.created_at)}</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${getStatusStyle(task.status)}`}>
                                            {getStatusText(task.status)}
                                        </span>
                                        {onDeleteTask && (
                                            <button
                                                onClick={(e) => handleDelete(e, 'task', task)}
                                                className="opacity-0 group-hover:opacity-100 p-1 text-slate-500 hover:text-red-400 transition-all"
                                                title="删除记录"
                                            >
                                                <Trash2 size={12} />
                                            </button>
                                        )}
                                    </div>
                                </div>

                                {/* 数据集信息 & 下载 */}
                                <div className="flex items-center justify-between mb-2">
                                    <div className="flex items-center gap-2 text-xs text-slate-500 overflow-hidden">
                                        <Database size={12} />
                                        <span className="truncate" title={task.dataset_name}>{task.dataset_name}</span>
                                    </div>
                                    <a
                                        href={`${API_BASE}/tasks/${task.id}/download_dataset`}
                                        target="_blank"
                                        rel="noreferrer"
                                        onClick={(e) => e.stopPropagation()}
                                        className="text-[10px] text-blue-400 hover:text-blue-300 flex items-center gap-1 flex-shrink-0"
                                    >
                                        <Download size={10} /> 下载数据集
                                    </a>
                                </div>

                                {/* 提示词预览 & 查看 */}
                                <div className="flex items-start justify-between gap-2 mb-2">
                                    <div className="flex items-start gap-2 text-xs text-slate-500 overflow-hidden">
                                        <FileText size={12} className="mt-0.5 flex-shrink-0" />
                                        <p className="line-clamp-2 italic text-slate-400" title={task.prompt}>
                                            "{task.prompt}"
                                        </p>
                                    </div>
                                    <button
                                        onClick={(e) => handleViewPrompt(task.prompt, e)}
                                        className="text-[10px] text-blue-400 hover:text-blue-300 whitespace-nowrap flex-shrink-0"
                                    >
                                        查看提示词
                                    </button>
                                </div>

                                {/* 底部: 进度和准确率 & 结果下载 */}
                                <div className="flex justify-between items-center pt-2 border-t border-white/5">
                                    <div className="flex items-center gap-4 text-xs">
                                        <span className="text-slate-500">
                                            进度: <span className="text-slate-300">{task.results_count}/{task.total_count}</span>
                                        </span>
                                        <span className="text-slate-500">
                                            准确率: <span className="text-emerald-400 font-medium">{(task.accuracy * 100).toFixed(1)}%</span>
                                        </span>
                                    </div>
                                    <a
                                        href={`/api/tasks/${task.id}/export`}
                                        target="_blank"
                                        rel="noreferrer"
                                        onClick={(e) => e.stopPropagation()}
                                        className="flex items-center gap-1 text-[10px] text-blue-400 hover:text-blue-300 transition-colors"
                                    >
                                        <Download size={12} />
                                        下载结果
                                    </a>
                                </div>

                                {/* 备注区域 */}
                                {renderNoteSection(task, 'task', task.id)}
                            </div>
                        ))}
                        {!runHistory?.length && <p className="text-center text-slate-600 mt-20">暂无运行历史</p>}
                    </div>
                ) : activeTab === "history" ? (
                    // 迭代历史 Tab
                    <div className="space-y-4">
                        {project.iterations?.slice().reverse().map((it: any, idx: number) => (
                            <div
                                key={idx}
                                onClick={() => onSelectIteration(it)}
                                className="relative pl-6 before:absolute before:left-0 before:top-2 before:bottom-0 before:w-[2px] before:bg-blue-500/30 cursor-pointer hover:opacity-80 transition-opacity group"
                            >
                                <div className="absolute left-[-4px] top-2 w-2 h-2 rounded-full bg-blue-500" />
                                <div className="flex justify-between items-center mb-2">
                                    <div className="flex items-center gap-2">
                                        <span className="text-sm font-bold">迭代 #{project.iterations.length - idx}</span>
                                        {/* 未应用提示词标识 */}
                                        {(it.not_applied || it.is_failed) && (
                                            <span className="px-1.5 py-0.5 bg-orange-500/20 text-orange-400 text-[10px] rounded border border-orange-500/30">
                                                未应用
                                            </span>
                                        )}
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <span className="text-[10px] text-slate-600">{new Date(it.created_at).toLocaleString()}</span>
                                        {onDeleteIteration && (
                                            <button
                                                onClick={(e) => handleDelete(e, 'iteration', it)}
                                                className="opacity-0 group-hover:opacity-100 p-1 text-slate-500 hover:text-red-400 transition-all"
                                                title="删除记录"
                                            >
                                                <Trash2 size={12} />
                                            </button>
                                        )}
                                    </div>
                                </div>
                                <div className={`text-xs rounded-lg p-3 border transition-colors ${it.not_applied || it.is_failed ? "bg-orange-500/5 border-orange-500/20 hover:bg-orange-500/10" : "bg-white/5 border-white/5 hover:bg-white/10"}`}>
                                    <div className="flex justify-between items-start mb-1">
                                        <div className={it.not_applied || it.is_failed ? "text-orange-400 font-bold" : "text-emerald-400 font-bold"}>准确率: {(it.accuracy_before * 100).toFixed(1)}%</div>
                                        {it.dataset_name && (
                                            <span className="text-[10px] text-slate-500 bg-white/5 px-2 py-0.5 rounded-full truncate max-w-[120px]" title={it.dataset_name}>
                                                {it.dataset_name}
                                            </span>
                                        )}
                                    </div>
                                    <p className="text-slate-500 line-clamp-3 italic mb-2">"{it.optimized_prompt}"</p>

                                    <div className="flex justify-end pt-2 border-t border-white/5">
                                        <a
                                            href={`/api/tasks/${it.task_id}/export`}
                                            target="_blank"
                                            rel="noreferrer"
                                            onClick={(e) => e.stopPropagation()}
                                            className="flex items-center gap-1 text-[10px] text-blue-400 hover:text-blue-300 transition-colors"
                                        >
                                            <Download size={12} /> 下载验证结果
                                        </a>
                                    </div>

                                    {/* 备注区域 */}
                                    {renderNoteSection(it, 'iteration', it.created_at)}
                                </div>
                            </div>
                        ))}
                        {!project.iterations?.length && <p className="text-center text-slate-600 mt-20">暂无优化历史</p>}
                    </div>
                ) : activeTab === "knowledge" ? (
                    // 优化分析 Tab (知识库)
                    <div className="space-y-3">
                        {knowledgeRecords?.map((record: any, idx: number) => (
                            <div
                                key={record.version}
                                onClick={() => onSelectKnowledge?.(record)}
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
                                            {new Date(record.timestamp).toLocaleString()}
                                        </span>
                                        {onDeleteKnowledge && (
                                            <button
                                                onClick={(e) => handleDelete(e, 'knowledge', record)}
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
                                        {(record.accuracy_before * 100).toFixed(1)}%
                                    </span>
                                    <TrendingUp size={12} className="text-emerald-400" />
                                    <span className="text-emerald-400 font-medium">
                                        {record.accuracy_after !== null && record.accuracy_after !== undefined
                                            ? `${(record.accuracy_after * 100).toFixed(1)}%`
                                            : "待验证"}
                                    </span>
                                </div>

                                {/* 应用策略 */}
                                {record.applied_strategies?.length > 0 && (
                                    <div className="flex flex-wrap gap-1 mb-2">
                                        {record.applied_strategies.slice(0, 3).map((strategy: string, sIdx: number) => (
                                            <span
                                                key={sIdx}
                                                className="px-1.5 py-0.5 bg-blue-500/10 text-blue-400 text-[10px] rounded border border-blue-500/20"
                                            >
                                                {strategy}
                                            </span>
                                        ))}
                                        {record.applied_strategies.length > 3 && (
                                            <span className="text-[10px] text-slate-500">
                                                +{record.applied_strategies.length - 3}
                                            </span>
                                        )}
                                    </div>
                                )}

                                {/* 优化总结预览 */}
                                <p className="text-[11px] text-slate-400 line-clamp-2">
                                    {record.analysis_summary || "暂无优化总结"}
                                </p>

                                {/* 备注区域 */}
                                {renderNoteSection(record, 'knowledge', record.version)}
                            </div>
                        ))}
                        {!knowledgeRecords?.length && (
                            <div className="text-center mt-20">
                                <Layers size={32} className="mx-auto text-slate-600 mb-2" />
                                <p className="text-slate-600 text-sm">暂无优化分析记录</p>
                                <p className="text-slate-700 text-xs mt-1">完成优化后将自动记录分析历史</p>
                            </div>
                        )}
                    </div>
                ) : activeTab === "intent" ? (
                    // 意图干预 Tab
                    !fileId ? (
                        <div className="flex flex-col items-center justify-center h-64 text-slate-500">
                            <Database className="w-12 h-12 mb-4 opacity-20" />
                            <p>请先上传或选择一个数据文件</p>
                            <p className="text-sm opacity-60 mt-2">意图干预数据与文件版本绑定</p>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            {/* Toolbar */}
                            <div className="bg-slate-800/40 p-3 rounded-xl border border-white/5 mb-4 space-y-3">
                                {/* Filter & Actions Row */}
                                <div className="flex justify-between items-center gap-4">
                                    <div className="flex items-center gap-2">
                                        <span className="text-xs text-slate-400">筛选:</span>
                                        <select
                                            value={intentFilter}
                                            onChange={(e) => {
                                                setIntentFilter(e.target.value);
                                                setIntentPage(1);
                                            }}
                                            className="bg-black/20 border border-white/10 rounded px-2 py-1.5 text-xs text-slate-300 outline-none focus:border-blue-500/50"
                                        >
                                            <option value="all" className="bg-slate-900">全部数据</option>
                                            <option value="modified" className="bg-slate-900">意图干预 (Target 修改)</option>
                                            <option value="reason_added" className="bg-slate-900">原因干预 (Reason 标注)</option>
                                        </select>
                                    </div>
                                    <div className="flex gap-2">
                                        <button
                                            onClick={() => handleAddIntentRow()}
                                            className="px-3 py-1.5 bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 rounded text-xs border border-blue-500/20 flex items-center gap-1"
                                        >
                                            <Edit3 size={12} /> 新增
                                        </button>
                                        <button
                                            onClick={handleExportIntent}
                                            className="px-3 py-1.5 bg-white/5 text-slate-400 hover:text-slate-300 rounded text-xs flex items-center gap-1 border border-white/10"
                                        >
                                            <Download size={12} /> 导出
                                        </button>
                                    </div>
                                </div>

                                {/* Search */}
                                <div className="flex items-center gap-2 bg-black/20 px-3 py-1.5 rounded-lg border border-white/5">
                                    <Search size={14} className="text-slate-500" />
                                    <input
                                        type="text"
                                        value={intentSearch}
                                        onChange={(e) => setIntentSearch(e.target.value)}
                                        className="bg-transparent border-none text-xs text-slate-300 placeholder:text-slate-600 focus:outline-none focus:ring-0 w-full"
                                        placeholder="搜索 Query, 预期结果 或 原因..."
                                    />
                                    {intentSearch && (
                                        <button onClick={() => setIntentSearch("")} className="text-slate-600 hover:text-slate-400">
                                            <X size={12} />
                                        </button>
                                    )}
                                </div>
                            </div>

                            {/* List */}
                            {intentLoading ? (
                                <p className="text-center text-slate-600 mt-20">加载中...</p>
                            ) : intentItems.length > 0 ? (
                                <div className="space-y-3">
                                    {intentItems.map((item: any, idx: number) => {
                                        const isEditing = editingReason?.query === item.query;
                                        return (
                                            <div key={item.id || idx} className="p-4 rounded-xl border border-white/5 bg-white/5 gap-3 flex flex-col group relative">
                                                {/* Header: Query & Badges */}
                                                <div className="mb-2">
                                                    <div className="flex items-center gap-2 mb-2">
                                                        <span className="text-indigo-400 font-medium text-xs">Query</span>
                                                        {item.is_target_modified && (
                                                            <span className="px-1.5 py-0.5 bg-indigo-500/20 text-indigo-300 text-[10px] rounded border border-indigo-500/30">
                                                                意图干预
                                                            </span>
                                                        )}
                                                        {item.reason && (
                                                            <span className="px-1.5 py-0.5 bg-amber-500/20 text-amber-300 text-[10px] rounded border border-amber-500/30">
                                                                原因干预
                                                            </span>
                                                        )}
                                                    </div>
                                                    <div className="bg-black/20 p-2 rounded border border-white/5 text-slate-300 min-h-[36px] break-all text-xs font-mono">
                                                        {item.query}
                                                    </div>
                                                </div>

                                                {/* Body: Target & Reason (Editable) */}
                                                {isEditing ? (
                                                    <div className="space-y-2 bg-black/20 p-3 rounded-lg border border-white/5">
                                                        <div className="space-y-1">
                                                            <label className="text-[10px] text-slate-500">预期结果 (Target)</label>
                                                            <textarea
                                                                className="w-full bg-black/40 border border-white/10 rounded p-1.5 text-xs text-slate-300 focus:border-blue-500/50 outline-none resize-none"
                                                                rows={2}
                                                                value={editingReason?.target || ""}
                                                                onChange={(e) => setEditingReason(prev => prev ? { ...prev, target: e.target.value } : null)}
                                                            />
                                                        </div>
                                                        <div className="space-y-1">
                                                            <label className="text-[10px] text-slate-500">原因 (Reason)</label>
                                                            <textarea
                                                                className="w-full bg-black/40 border border-white/10 rounded p-1.5 text-xs text-slate-300 focus:border-amber-500/50 outline-none resize-none"
                                                                rows={2}
                                                                value={editingReason?.value || ""}
                                                                onChange={(e) => setEditingReason(prev => prev ? { ...prev, value: e.target.value } : null)}
                                                            />
                                                        </div>
                                                        <div className="flex justify-end gap-2 pt-2">
                                                            <button
                                                                onClick={async () => {
                                                                    if (editingReason) {
                                                                        await saveReason(item.query, editingReason.value, editingReason.target);
                                                                        fetchIntentData(intentPage, intentSearch);
                                                                    }
                                                                }}
                                                                className="px-3 py-1 text-xs bg-emerald-500/10 text-emerald-400 rounded hover:bg-emerald-500/20 border border-emerald-500/20"
                                                            >
                                                                保存
                                                            </button>
                                                            <button
                                                                onClick={() => setEditingReason(null)}
                                                                className="px-3 py-1 text-xs bg-slate-500/10 text-slate-400 rounded hover:bg-slate-500/20 border border-white/10"
                                                            >
                                                                取消
                                                            </button>
                                                        </div>
                                                    </div>
                                                ) : (
                                                    <div
                                                        className="space-y-3 cursor-pointer hover:bg-white/5 rounded transition-colors -m-2 p-2 relative group/item"
                                                        onClick={() => setEditingReason({ query: item.query, target: item.target, value: item.reason })}
                                                    >
                                                        <div className="grid grid-cols-1 gap-2">
                                                            <div>
                                                                <span className="text-[10px] text-slate-500 block mb-0.5">预期结果:</span>
                                                                <div className="text-xs text-slate-400 break-words">{item.target || <span className="text-slate-600 italic">未设置</span>}</div>
                                                            </div>
                                                            <div>
                                                                <span className="text-[10px] text-amber-500/70 block mb-0.5">标注原因:</span>
                                                                <div className="text-xs text-amber-500/90 break-words">{item.reason || <span className="text-slate-600 italic">未设置</span>}</div>
                                                            </div>
                                                        </div>
                                                        <div className="absolute right-2 top-2 text-[10px] text-blue-400/50 opacity-0 group-hover/item:opacity-100 transition-opacity flex items-center gap-1 bg-black/40 px-2 py-0.5 rounded-full">
                                                            <Edit3 size={10} /> 点击编辑
                                                        </div>
                                                    </div>
                                                )}

                                                {/* Footer: Date & Actions */}
                                                <div className="flex justify-between items-center mt-2 pt-2 border-t border-white/5">
                                                    <span className="text-[10px] text-slate-600">
                                                        更新于: {new Date(item.updated_at).toLocaleString()}
                                                    </span>
                                                    <div className="flex gap-1">
                                                        {/* Reset Button */}
                                                        {(item.is_target_modified || item.reason) && (
                                                            <button
                                                                onClick={() => handleResetIntervention(item.query)}
                                                                className="p-1.5 text-slate-400 hover:text-blue-400 hover:bg-blue-500/10 rounded transition-colors"
                                                                title="重置为原始值 (清除干预)"
                                                            >
                                                                <RotateCcw size={14} />
                                                            </button>
                                                        )}
                                                        {/* Delete Button */}
                                                        <button
                                                            onClick={() => {
                                                                if (window.confirm("确定删除此条数据吗?")) {
                                                                    deleteReason(item.query).then(() => fetchIntentData(intentPage, intentSearch));
                                                                }
                                                            }}
                                                            className="p-1.5 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded transition-colors"
                                                            title="删除"
                                                        >
                                                            <Trash2 size={14} />
                                                        </button>
                                                    </div>
                                                </div>
                                            </div>
                                        );
                                    })}

                                    {/* Pagination */}
                                    <div className="flex justify-between items-center text-xs text-slate-500 pt-2">
                                        <span>共 {intentTotal} 条</span>
                                        <div className="flex gap-2">
                                            <button
                                                disabled={intentPage === 1}
                                                onClick={() => setIntentPage(p => p - 1)}
                                                className="hover:text-white disabled:opacity-30"
                                            >
                                                上一页
                                            </button>
                                            <span>Page {intentPage}</span>
                                            <button
                                                disabled={intentItems.length < 20}
                                                onClick={() => setIntentPage(p => p + 1)}
                                                className="hover:text-white disabled:opacity-30"
                                            >
                                                下一页
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            ) : (
                                <div className="text-center mt-20">
                                    <Database size={32} className="mx-auto text-slate-600 mb-2" />
                                    <p className="text-slate-600 text-sm">暂无干预数据</p>
                                    <p className="text-slate-700 text-xs mt-1">上传文件开始任务后自动导入，或点击新增</p>
                                </div>
                            )}
                        </div>
                    )
                ) : null}
            </div>

            {/* Prompt Modal */}
            {
                showPromptModal && (
                    <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 animate-in fade-in duration-200">
                        <div className="bg-slate-900 border border-white/10 rounded-xl shadow-2xl w-full max-w-2xl flex flex-col h-[500px]">
                            <div className="flex justify-between items-center p-3 border-b border-white/10">
                                <h3 className="text-sm font-medium text-white">完整提示词</h3>
                                <button onClick={() => setShowPromptModal(false)} className="text-slate-400 hover:text-white transition-colors">
                                    <X size={16} />
                                </button>
                            </div>
                            <div className="flex-1 p-3 overflow-hidden">
                                <textarea
                                    readOnly
                                    className="w-full h-full bg-black/20 border border-white/5 rounded-lg p-2 text-xs text-slate-300 font-mono resize-none focus:outline-none focus:border-blue-500/50 custom-scrollbar"
                                    value={currentPrompt}
                                />
                            </div>
                            <div className="p-3 border-t border-white/10 flex justify-end">
                                <button
                                    onClick={copyPrompt}
                                    className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded-lg transition-colors"
                                >
                                    <Copy size={12} /> 复制
                                </button>
                            </div>
                        </div>
                    </div>
                )
            }
        </section >
    );
}
