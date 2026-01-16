import { useState, useEffect, useRef, useCallback } from "react";

import { Database, Edit3, FileText, CheckCircle2, AlertCircle, RotateCcw, Search, Filter, MessageSquare, Sparkles, X, Save, LogOut, Trash2, FlaskConical, XCircle, Download } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

const API_BASE = "/api";

/**
 * 意图干预Tab组件的Props接口
 */
interface IntentInterventionTabProps {
    project: any;
    fileId?: string;
    saveReason: (query: string, reason: string, target: string) => Promise<void>;
}

/**
 * 编辑状态接口
 */
interface EditingState {
    query: string;
    value: string;
    target: string;
    originalValue: string;
    originalTarget: string;
}

/**
 * 意图干预Tab组件
 * 用于展示和编辑意图干预数据
 * 重构：采用 RunLogTab 的稳定无限滚动模式
 */
export default function IntentInterventionTab({ project, fileId, saveReason }: IntentInterventionTabProps) {
    // Local State for Pagination & Data
    const [intentItems, setIntentItems] = useState<any[]>([]);
    const [page, setPage] = useState(1);
    const [hasMore, setHasMore] = useState(true);
    // 分离两种加载状态：无限滚动加载 和 定时刷新
    const [isLoadingMore, setIsLoadingMore] = useState(false);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [totalResults, setTotalResults] = useState(0);

    // Filters & Search
    const [searchQuery, setSearchQuery] = useState("");
    const [filterStatus, setFilterStatus] = useState("all");

    // Editing State
    const [editingReason, setEditingReason] = useState<EditingState | null>(null);
    const [showExitConfirm, setShowExitConfirm] = useState(false);
    const [resetConfirmQuery, setResetConfirmQuery] = useState<string | null>(null);
    const [testingQuery, setTestingQuery] = useState<string | null>(null);
    const [testResult, setTestResult] = useState<{ query: string, is_correct: boolean, output: string, reason: string, target: string } | null>(null);

    // Selection State
    const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());

    // Create Modal State
    const [showCreateModal, setShowCreateModal] = useState(false);

    const [createForm, setCreateForm] = useState({ query: "", target: "", reason: "" });
    const [showCreateExitConfirm, setShowCreateExitConfirm] = useState(false);

    // Refs
    const scrollContainerRef = useRef<HTMLDivElement>(null);
    const loadMoreRef = useRef<HTMLDivElement>(null);
    const loadedPagesRef = useRef<number>(1);
    const editPanelRef = useRef<HTMLDivElement | null>(null);

    /**
     * 检查是否有未保存的更改
     */
    const hasUnsavedChanges = useCallback((): boolean => {
        if (!editingReason) return false;
        return editingReason.value !== editingReason.originalValue ||
            editingReason.target !== editingReason.originalTarget;
    }, [editingReason]);

    /**
     * 尝试关闭编辑面板
     */
    const tryCloseEditor = useCallback(() => {
        if (hasUnsavedChanges()) {
            setShowExitConfirm(true);
        } else {
            setEditingReason(null);
        }
    }, [hasUnsavedChanges]);

    /**
     * 确认退出不保存
     */
    const confirmExit = useCallback(() => {
        setShowExitConfirm(false);
        setEditingReason(null);
    }, []);

    /**
     * 取消退出
     */
    const cancelExit = useCallback(() => {
        setShowExitConfirm(false);
    }, []);

    /**
     * 加载更多数据 (用于无限滚动)
     */
    const loadMoreResults = useCallback(async (pageNum: number, search: string = "", filter: string = "all") => {
        if (!project?.id || !fileId) return;
        setIsLoadingMore(true);
        try {
            let url = `${API_BASE}/projects/${project.id}/interventions?page=${pageNum}&page_size=20&file_id=${fileId}`;
            if (search) url += `&search=${encodeURIComponent(search)}`;
            if (filter !== "all") url += `&filter_type=${filter}`;

            const res = await fetch(url);
            if (res.ok) {
                const data = await res.json();
                // 追加数据
                setIntentItems(prev => [...prev, ...(data.items || [])]);
                setTotalResults(data.total || 0);

                // 计算是否还有更多
                const currentCount = pageNum * 20;
                setHasMore(currentCount < (data.total || 0));

                setPage(pageNum);
                loadedPagesRef.current = pageNum;
            }
        } catch (e) {
            console.error("Failed to load more intent data", e);
        } finally {
            setIsLoadingMore(false);
        }
    }, [project?.id, fileId]);

    /**
     * 刷新数据 (用于初始加载、筛选、搜索变换)
     */
    const refreshResults = useCallback(async (pageSize: number, search: string = "", filter: string = "all") => {
        if (!project?.id || !fileId) return;
        setIsRefreshing(true);
        setSelectedItems(new Set()); // Clear selection on refresh
        try {
            // 注意：这里我们请求 page=1 但 page_size 可以是累积的大小，或者简单点只请求第一页
            // RunLogTab 的逻辑是 refreshResults(pageSize)
            // 这里我们简化：每次刷新重置为第一页 20 条，因为通常是条件变了
            // 如果是自动刷新（这里似乎不需要自动刷新），可能需要保持条数

            let url = `${API_BASE}/projects/${project.id}/interventions?page=1&page_size=${pageSize}&file_id=${fileId}`;
            if (search) url += `&search=${encodeURIComponent(search)}`;
            if (filter !== "all") url += `&filter_type=${filter}`;

            const res = await fetch(url);
            if (res.ok) {
                const data = await res.json();
                setIntentItems(data.items || []);
                setTotalResults(data.total || 0);

                const pagesLoaded = Math.ceil((data.items?.length || 0) / 20);
                setPage(pagesLoaded || 1);
                loadedPagesRef.current = pagesLoaded || 1;

                setHasMore((data.items?.length || 0) < (data.total || 0));
            }
        } catch (e) {
            console.error("Failed to refresh intent data", e);
        } finally {
            setIsRefreshing(false);
        }
    }, [project?.id, fileId]);

    // Reset when dependencies change (project / fileId / filter)
    useEffect(() => {
        if (project?.id && fileId) {
            setIntentItems([]);
            setPage(1);
            setHasMore(true);
            setTotalResults(0);
            loadedPagesRef.current = 1;
            refreshResults(20, searchQuery, filterStatus);
        }
    }, [project?.id, fileId, filterStatus]); // searchQuery has its own debounce effect

    // Search Debounce
    useEffect(() => {
        if (project?.id && fileId) {
            const timer = setTimeout(() => {
                setIntentItems([]);
                setPage(1);
                loadedPagesRef.current = 1;
                refreshResults(20, searchQuery, filterStatus);
            }, 500);
            return () => clearTimeout(timer);
        }
    }, [searchQuery]);

    /**
     * 无限滚动 Observer
     */
    useEffect(() => {
        const node = loadMoreRef.current;
        const root = scrollContainerRef.current;
        // 关键：只有在非加载状态、有更多数据、且有必要ID时才监听
        if (!node || isLoadingMore || !hasMore || !project?.id || !fileId) return;

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
    }, [hasMore, isLoadingMore, page, project?.id, fileId, loadMoreResults, searchQuery, filterStatus]);

    // ESC键监听
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape' && editingReason) {
                e.preventDefault();
                tryCloseEditor();
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [editingReason, tryCloseEditor]);

    // 点击外部检测
    useEffect(() => {
        const handleClickOutside = (e: MouseEvent) => {
            if (editingReason && editPanelRef.current && !editPanelRef.current.contains(e.target as Node)) {
                tryCloseEditor();
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [editingReason, tryCloseEditor]);

    /**
     * 新增Modal的退出检查逻辑
     */
    const checkCreateFormDirty = useCallback(() => {
        if (createForm.query.trim() || createForm.target.trim() || createForm.reason.trim()) {
            return true;
        }
        return false;
    }, [createForm]);

    const tryCloseCreateModal = useCallback(() => {
        if (checkCreateFormDirty()) {
            setShowCreateExitConfirm(true);
        } else {
            setShowCreateModal(false);
            setCreateForm({ query: "", target: "", reason: "" });
        }
    }, [checkCreateFormDirty]);

    const confirmExitCreate = () => {
        setShowCreateExitConfirm(false);
        setShowCreateModal(false);
        setCreateForm({ query: "", target: "", reason: "" });
    };

    const cancelExitCreate = () => {
        setShowCreateExitConfirm(false);
    };

    // 新增Modal的 ESC 键监听
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape' && showCreateModal) {
                // 如果确认弹窗已显示，Esc取消确认（即留在当前界面）
                if (showCreateExitConfirm) {
                    cancelExitCreate();
                } else {
                    tryCloseCreateModal();
                }
            }
        };
        // 仅在Modal显示时添加
        if (showCreateModal) {
            window.addEventListener('keydown', handleKeyDown);
        }
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [showCreateModal, showCreateExitConfirm, tryCloseCreateModal]);

    /**
     * 重置单条意图干预记录
     */
    /**
     * 重置单条意图干预记录
     */
    const executeReset = async (query: string) => {
        if (!project?.id) return;

        try {
            const res = await fetch(`${API_BASE}/projects/${project.id}/interventions/reset`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ query })
            });

            if (res.ok) {
                // 刷新当前列表
                const currentPages = loadedPagesRef.current;
                refreshResults(currentPages * 20, searchQuery, filterStatus);
                setResetConfirmQuery(null);
            } else {
                alert("重置失败");
            }
        } catch (e) {
            console.error(e);
            alert("重置出错");
        }
    };

    /**
     * 创建新干预项
     */
    const handleCreate = async () => {
        if (!project?.id || !createForm.query.trim()) return;
        try {
            const res = await fetch(`${API_BASE}/projects/${project.id}/interventions`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    query: createForm.query,
                    target: createForm.target,
                    reason: createForm.reason,
                    file_id: fileId
                })
            });
            if (res.ok) {
                setShowCreateModal(false);
                setCreateForm({ query: "", target: "", reason: "" });
                refreshResults(loadedPagesRef.current * 20, searchQuery, filterStatus);
            } else {
                alert("创建失败");
            }
        } catch (e) {
            console.error(e);
            alert("创建出错");
        }
    };

    /**
     * 删除单条干预项
     */
    const handleDelete = async (query: string) => {
        if (!project?.id || !confirm("确定要删除此条记录吗？")) return;
        try {
            const res = await fetch(`${API_BASE}/projects/${project.id}/interventions?query=${encodeURIComponent(query)}`, {
                method: "DELETE"
            });
            if (res.ok) {
                refreshResults(loadedPagesRef.current * 20, searchQuery, filterStatus);
            } else {
                alert("删除失败");
            }
        } catch (e) {
            console.error(e);
            alert("删除出错");
        }
    };

    /**
     * 批量删除
     */
    const handleBatchDelete = async () => {
        if (!project?.id || selectedItems.size === 0 || !confirm(`确定要删除选中的 ${selectedItems.size} 条记录吗？`)) return;
        try {
            const res = await fetch(`${API_BASE}/projects/${project.id}/interventions/batch`, {
                method: "DELETE",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(Array.from(selectedItems))
            });
            if (res.ok) {
                setSelectedItems(new Set());
                refreshResults(loadedPagesRef.current * 20, searchQuery, filterStatus);
            } else {
                alert("批量删除失败");
            }
        } catch (e) {
            console.error(e);
            alert("批量删除出错");
        }
    };

    /**
     * 清空所有
     */
    const handleClearAll = async () => {
        if (!project?.id || !confirm("确定要清空所有意图干预数据吗？此操作不可恢复！")) return;
        try {
            const res = await fetch(`${API_BASE}/projects/${project.id}/interventions/clear?file_id=${fileId || ''}`, {
                method: "DELETE"
            });
            if (res.ok) {
                refreshResults(20, searchQuery, filterStatus);
            } else {
                alert("清空失败");
            }
        } catch (e) {
            console.error(e);
            alert("清空出错");
        }
    };

    /**
     * 导出干预数据
     */
    const handleExport = async () => {
        if (!project?.id) return;
        try {
            const url = `${API_BASE}/projects/${project.id}/interventions/export?file_id=${fileId || ''}`;
            const res = await fetch(url);
            if (!res.ok) throw new Error("导出失败");

            const blob = await res.blob();
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = downloadUrl;
            a.download = `intent_interventions_${project.id}${fileId ? `_${fileId}` : ''}.xlsx`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(downloadUrl);
            document.body.removeChild(a);
        } catch (e) {
            console.error(e);
            alert("导出数据失败");
        }
    };

    /**
     * 选择/取消选择
     */
    const toggleSelection = (query: string) => {
        const newSet = new Set(selectedItems);
        if (newSet.has(query)) {
            newSet.delete(query);
        } else {
            newSet.add(query);
        }
        setSelectedItems(newSet);
    };

    /**
     * 执行单条测试
     */
    const handleTest = async (query: string, target: string, reason: string) => {
        if (!project?.id) return;
        setTestingQuery(query);
        try {
            const res = await fetch(`${API_BASE}/projects/${project.id}/interventions/test`, {
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
                    target: target
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

    // 无文件提示
    if (!fileId) {
        return (
            <div className="flex flex-col items-center justify-center h-64">
                <motion.div
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className="w-16 h-16 rounded-2xl bg-gradient-to-br from-cyan-500/20 to-blue-500/20 flex items-center justify-center mb-4 border border-cyan-500/20"
                >
                    <Database className="w-8 h-8 text-cyan-400" />
                </motion.div>
                <p className="text-slate-400 text-sm">请先上传或选择一个数据文件</p>
                <p className="text-slate-600 text-xs mt-1">意图干预数据与文件版本绑定</p>
            </div>
        );
    }

    return (
        <div
            ref={scrollContainerRef}
            className="flex-1 overflow-y-auto p-4 custom-scrollbar space-y-3"
        >
            {/* 搜索与筛选工具栏 */}
            <div className="flex flex-col gap-2">
                <div className="flex gap-2 flex-1">
                    {/* 搜索框 */}
                    <div className="relative flex-1">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={12} />
                        <input
                            type="text"
                            className="w-full bg-slate-800/50 border border-slate-700/50 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-200 outline-none focus:border-cyan-500/50 transition-all placeholder:text-slate-600"
                            placeholder="搜索 Query, 预期结果 或 原因..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                        />
                        {searchQuery && (
                            <button
                                onClick={() => setSearchQuery("")}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white"
                            >
                                <X size={12} />
                            </button>
                        )}
                    </div>
                    {/* 筛选下拉 */}
                    <div className="flex items-center gap-2 bg-slate-800/50 border border-slate-700/50 rounded-lg px-3 py-1.5 min-w-fit">
                        <Filter size={12} className="text-slate-400" />
                        <select
                            value={filterStatus}
                            onChange={(e) => setFilterStatus(e.target.value)}
                            className="bg-transparent text-xs text-slate-300 outline-none cursor-pointer"
                        >
                            <option value="all" className="bg-slate-900">全部</option>
                            <option value="modified" className="bg-slate-900">已修正</option>
                            <option value="reason_added" className="bg-slate-900">已标注</option>
                        </select>
                    </div>
                </div>

                {/* 操作按钮 */}
                <div className="flex gap-2 justify-end">
                    {selectedItems.size > 0 ? (
                        <div className="flex gap-2">
                            <motion.button
                                initial={{ opacity: 0, scale: 0.9 }}
                                animate={{ opacity: 1, scale: 1 }}
                                onClick={() => setSelectedItems(new Set())}
                                className="px-3 py-1.5 rounded-lg bg-slate-700/50 text-slate-300 text-xs border border-slate-600/50 hover:bg-slate-700 hover:text-white transition-colors flex items-center gap-1.5"
                            >
                                <X size={12} />
                                取消选择
                            </motion.button>
                            <motion.button
                                initial={{ opacity: 0, scale: 0.9 }}
                                animate={{ opacity: 1, scale: 1 }}
                                onClick={handleBatchDelete}
                                className="px-3 py-1.5 rounded-lg bg-red-500/10 text-red-400 text-xs border border-red-500/20 hover:bg-red-500/20 transition-colors flex items-center gap-1.5"
                            >
                                <Trash2 size={12} />
                                <span className="w-4 h-4 rounded-full bg-red-500/20 flex items-center justify-center text-[10px]">{selectedItems.size}</span>
                                删除选中
                            </motion.button>
                        </div>
                    ) : (
                        <div className="flex gap-2">
                            <button
                                onClick={handleClearAll}
                                className="px-3 py-1.5 rounded-lg bg-slate-800/50 text-slate-400 text-xs border border-slate-700/50 hover:text-red-400 hover:border-red-500/30 transition-colors"
                            >
                                清空
                            </button>
                            <button
                                onClick={handleExport}
                                className="px-3 py-1.5 rounded-lg bg-slate-800/50 text-slate-400 text-xs border border-slate-700/50 hover:text-cyan-400 hover:border-cyan-500/30 transition-colors flex items-center gap-1"
                            >
                                <Download size={12} /> 导出
                            </button>
                            <button
                                onClick={() => setShowCreateModal(true)}
                                className="px-3 py-1.5 rounded-lg bg-cyan-600/20 text-cyan-400 text-xs border border-cyan-500/30 hover:bg-cyan-600/30 transition-colors flex items-center gap-1"
                            >
                                <Edit3 size={12} /> 新增
                            </button>
                        </div>
                    )}
                </div>
            </div>

            {/* 数据列表 */}
            <div className="space-y-3">
                {isRefreshing ? (
                    <div className="flex flex-col items-center justify-center py-20 gap-3">
                        <div className="w-6 h-6 border-2 border-cyan-500/30 border-t-cyan-500 rounded-full animate-spin" />
                        <span className="text-xs text-slate-500">加载中...</span>
                    </div>
                ) : (
                    <>
                        {intentItems.map((item, index) => {
                            const isEditing = editingReason?.query === item.query;
                            const hasModification = item.is_target_modified;
                            const hasReason = !!item.reason;
                            // 使用唯一 key：优先 id，其次 query，最后使用索引
                            const itemKey = item.id || item.query || `intent-item-${index}`;

                            const isSelected = selectedItems.has(item.query);

                            return (
                                <div
                                    key={itemKey}
                                    className={`relative p-3 rounded-xl border transition-all group ${isSelected
                                        ? 'border-cyan-500/40 bg-cyan-900/10'
                                        : 'border-cyan-500/20 bg-gradient-to-br from-cyan-600/5 to-blue-600/5 hover:from-cyan-600/10 hover:to-blue-600/10'
                                        }`}
                                >
                                    {/* 头部：Query 标签和状态 */}
                                    <div className="flex justify-between items-center mb-2">
                                        <div className="flex items-center gap-2 flex-1 overflow-hidden">
                                            {/* 复选框 */}
                                            <div
                                                className={`w-5 h-5 rounded border flex items-center justify-center cursor-pointer transition-colors ${isSelected ? 'bg-cyan-500 border-cyan-500' : 'border-slate-600 hover:border-cyan-500'
                                                    }`}
                                                onClick={() => toggleSelection(item.query)}
                                            >
                                                {isSelected && <CheckCircle2 size={12} className="text-white" />}
                                            </div>

                                            <div className="w-6 h-6 rounded-lg bg-cyan-500/20 flex items-center justify-center">
                                                <MessageSquare size={12} className="text-cyan-400" />
                                            </div>
                                            <span className="text-sm font-bold text-white truncate max-w-[200px]" title={item.query}>{item.query}</span>
                                            {hasModification && (
                                                <span className="px-1.5 py-0.5 bg-indigo-500/20 text-indigo-300 text-[10px] rounded border border-indigo-500/30 flex items-center gap-0.5 shrink-0">
                                                    <Edit3 size={8} /> 已修正
                                                </span>
                                            )}
                                            {hasReason && (
                                                <span className="px-1.5 py-0.5 bg-amber-500/20 text-amber-300 text-[10px] rounded border border-amber-500/30 flex items-center gap-0.5 shrink-0">
                                                    <FileText size={8} /> 已标注
                                                </span>
                                            )}
                                        </div>

                                        {/* 操作按钮 */}
                                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleDelete(item.query);
                                                }}
                                                className="p-1.5 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded transition-colors"
                                                title="删除"
                                            >
                                                <X size={12} />
                                            </button>

                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleTest(item.query, item.target || "", item.reason || "");
                                                }}
                                                disabled={!!testingQuery}
                                                className={`p-1.5 rounded transition-colors ${testingQuery === item.query
                                                    ? "text-cyan-400 bg-cyan-500/10 animate-pulse"
                                                    : "text-slate-400 hover:text-indigo-400 hover:bg-indigo-500/10"
                                                    }`}
                                                title="执行单测"
                                            >
                                                {testingQuery === item.query ? (
                                                    <div className="w-3 h-3 border-2 border-cyan-500/30 border-t-cyan-500 rounded-full animate-spin" />
                                                ) : (
                                                    <FlaskConical size={12} />
                                                )}
                                            </button>

                                            {(hasModification || hasReason) && (
                                                resetConfirmQuery === item.query ? (
                                                    <div className="flex items-center gap-1 bg-slate-900/80 rounded border border-slate-700/50 p-0.5" onClick={e => e.stopPropagation()}>
                                                        <button
                                                            onClick={(e) => {
                                                                e.stopPropagation();
                                                                executeReset(item.query);
                                                            }}
                                                            className="p-1 text-emerald-400 hover:bg-emerald-500/20 rounded transition-colors"
                                                            title="确认重置"
                                                        >
                                                            <CheckCircle2 size={12} />
                                                        </button>
                                                        <button
                                                            onClick={(e) => {
                                                                e.stopPropagation();
                                                                setResetConfirmQuery(null);
                                                            }}
                                                            className="p-1 text-slate-400 hover:text-red-400 hover:bg-red-500/20 rounded transition-colors"
                                                            title="取消"
                                                        >
                                                            <X size={12} />
                                                        </button>
                                                    </div>
                                                ) : (
                                                    <button
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            setResetConfirmQuery(item.query);
                                                        }}
                                                        className="p-1.5 text-slate-400 hover:text-amber-400 hover:bg-amber-500/10 rounded transition-colors"
                                                        title="重置此条记录"
                                                    >
                                                        <RotateCcw size={12} />
                                                    </button>
                                                )
                                            )}
                                            {!isEditing && (
                                                <button
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        setEditingReason({
                                                            query: item.query,
                                                            value: item.reason || '',
                                                            target: item.target || '',
                                                            originalValue: item.reason || '',
                                                            originalTarget: item.target || ''
                                                        });
                                                    }}
                                                    className="p-1.5 text-slate-400 hover:text-cyan-400 hover:bg-cyan-500/10 rounded transition-colors"
                                                    title="编辑原因"
                                                >
                                                    <Edit3 size={12} />
                                                </button>
                                            )}
                                        </div>
                                    </div>


                                    {/* Query 内容 */}
                                    <div className="bg-black/20 rounded p-2 text-xs text-slate-300 mb-2 border border-white/5 font-mono break-all">
                                        {item.query}
                                    </div>

                                    {/* 编辑区域 或 展示区域 */}
                                    {
                                        isEditing ? (
                                            <div
                                                ref={editPanelRef}
                                                className="space-y-2 mt-3 bg-slate-900/50 p-3 rounded-lg border border-cyan-500/30"
                                                onClick={e => e.stopPropagation()}
                                            >
                                                <div className="flex items-center justify-between text-xs text-cyan-400 mb-1">
                                                    <span className="font-semibold flex items-center gap-1">
                                                        <Edit3 size={10} /> 编辑意图与原因
                                                    </span>
                                                </div>

                                                {/* 预期结果编辑 */}
                                                <div className="space-y-1">
                                                    <label className="text-[10px] text-slate-500">预期结果 (Target)</label>
                                                    <input
                                                        type="text"
                                                        className="w-full bg-black/40 border border-cyan-500/30 rounded px-2 py-1.5 text-xs text-white focus:outline-none focus:border-cyan-500 transition-colors"
                                                        value={editingReason?.target}
                                                        onChange={e => setEditingReason(prev => prev ? { ...prev, target: e.target.value } : null)}
                                                        placeholder="输入预期的意图结果..."
                                                    />
                                                </div>

                                                {/* 原因编辑 */}
                                                <div className="space-y-1">
                                                    <label className="text-[10px] text-slate-500">问题原因 (Reason)</label>
                                                    <textarea
                                                        className="w-full bg-black/40 border border-slate-700 rounded px-2 py-1.5 text-xs text-white focus:outline-none focus:border-cyan-500 transition-colors resize-none h-16"
                                                        value={editingReason?.value}
                                                        onChange={e => setEditingReason(prev => prev ? { ...prev, value: e.target.value } : null)}
                                                        placeholder="输入导致识别错误的原因..."
                                                    />
                                                </div>

                                                {/* 操作按钮栏 */}
                                                <div className="flex justify-end gap-2 pt-2">
                                                    <button
                                                        onClick={tryCloseEditor}
                                                        className="px-2 py-1 rounded text-xs bg-slate-700 text-slate-300 hover:bg-slate-600 transition-colors"
                                                    >
                                                        取消
                                                    </button>
                                                    <button
                                                        onClick={async () => {
                                                            if (editingReason) {
                                                                await saveReason(editingReason.query, editingReason.value, editingReason.target);
                                                                // 保存后刷新当前视图（保持页码）
                                                                const currentPages = loadedPagesRef.current;
                                                                refreshResults(currentPages * 20, searchQuery, filterStatus);
                                                                setEditingReason(null);
                                                            }
                                                        }}
                                                        className="px-3 py-1 rounded text-xs bg-cyan-600 text-white hover:bg-cyan-500 transition-colors flex items-center gap-1 shadow-lg shadow-cyan-500/20"
                                                    >
                                                        <Save size={12} /> 保存
                                                    </button>
                                                </div>

                                                {/* 退出确认弹窗 */}
                                                {showExitConfirm && (
                                                    <div className="absolute inset-0 bg-slate-900/95 backdrop-blur-sm rounded-lg flex flex-col items-center justify-center z-10 p-4 text-center border border-slate-700">
                                                        <AlertCircle size={24} className="text-amber-500 mb-2" />
                                                        <p className="text-slate-200 text-xs font-bold mb-1">有未保存的更改</p>
                                                        <p className="text-slate-400 text-[10px] mb-3">确定要放弃更改并退出编辑吗？</p>
                                                        <div className="flex gap-2">
                                                            <button
                                                                onClick={cancelExit}
                                                                className="px-3 py-1 rounded text-xs bg-slate-700 text-slate-300 hover:bg-slate-600"
                                                            >
                                                                继续编辑
                                                            </button>
                                                            <button
                                                                onClick={confirmExit}
                                                                className="px-3 py-1 rounded text-xs bg-amber-600 text-white hover:bg-amber-500"
                                                            >
                                                                放弃保存
                                                            </button>
                                                        </div>
                                                    </div>
                                                )}
                                            </div>
                                        ) : (
                                            <div
                                                className="flex gap-2 mt-2 cursor-pointer"
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    setEditingReason({
                                                        query: item.query,
                                                        target: item.target || '',
                                                        value: item.reason || '',
                                                        originalTarget: item.target || '',
                                                        originalValue: item.reason || ''
                                                    })
                                                }
                                                }
                                            >
                                                {/* 预期结果 */}
                                                <div className="flex-1 p-2 rounded-lg bg-emerald-500/5 border border-emerald-500/10 hover:bg-emerald-500/10 transition-all">
                                                    <div className="text-[9px] font-bold text-emerald-500/70 uppercase tracking-wider flex items-center gap-1 mb-1">
                                                        <CheckCircle2 size={8} /> 预期结果
                                                    </div>
                                                    <p className="text-[11px] text-emerald-100/80 line-clamp-2">
                                                        {item.target || <span className="text-slate-500 italic">未设置</span>}
                                                    </p>
                                                </div>

                                                {/* 问题原因 */}
                                                <div className="flex-1 p-2 rounded-lg bg-rose-500/5 border border-rose-500/10 hover:bg-rose-500/10 transition-all">
                                                    <div className="text-[9px] font-bold text-rose-500/70 uppercase tracking-wider flex items-center gap-1 mb-1">
                                                        <AlertCircle size={8} /> 问题原因
                                                    </div>
                                                    <p className="text-[11px] text-rose-100/80 line-clamp-2">
                                                        {item.reason || <span className="text-slate-500 italic">未标注</span>}
                                                    </p>
                                                </div>
                                            </div>
                                        )
                                    }
                                </div>
                            );
                        })}
                    </>
                )}
            </div>

            {/* 加载更多指示器 */}
            <div ref={loadMoreRef} className="py-4 text-center">
                {isLoadingMore && (
                    <div className="flex justify-center items-center gap-2 text-slate-500 text-xs">
                        <div className="w-3 h-3 border-2 border-slate-500/30 border-t-slate-500 rounded-full animate-spin" />
                        <span>加载更多...</span>
                    </div>
                )}
                {!isLoadingMore && !hasMore && intentItems.length > 0 && (
                    <div className="text-slate-600 text-[10px]">· 已加载全部 ·</div>
                )}
            </div>

            {/* 空状态 */}
            {
                !isRefreshing && intentItems.length === 0 && (
                    <div className="flex flex-col items-center justify-center py-20">
                        <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-slate-700/50 to-slate-600/50 flex items-center justify-center mb-4 border border-slate-600/30">
                            <Sparkles className="w-8 h-8 text-slate-500" />
                        </div>
                        <p className="text-slate-400 text-sm">未找到匹配的数据</p>
                        <p className="text-slate-600 text-xs mt-1">尝试调整搜索条件或筛选器</p>
                    </div>
                )
            }

            {/* 新增干预Modal */}
            {
                showCreateModal && (
                    <div
                        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
                        onClick={tryCloseCreateModal}
                    >
                        <div
                            className="bg-slate-900 border border-slate-700 rounded-xl w-full max-w-lg shadow-2xl overflow-hidden animate-in fade-in zoom-in duration-200 relative"
                            onClick={(e) => e.stopPropagation()}
                        >
                            <div className="px-4 py-3 border-b border-slate-800 flex justify-between items-center bg-slate-900/50">
                                <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                                    <Edit3 size={14} className="text-cyan-400" /> 新增意图干预
                                </h3>
                                <button
                                    onClick={tryCloseCreateModal}
                                    className="text-slate-500 hover:text-white transition-colors"
                                >
                                    <X size={16} />
                                </button>
                            </div>
                            <div className="p-4 space-y-4">
                                <div className="space-y-1">
                                    <label className="text-xs text-slate-400">用户查询 (Query) <span className="text-red-500">*</span></label>
                                    <textarea
                                        className="w-full bg-black/40 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:border-cyan-500 outline-none transition-colors resize-none h-20"
                                        placeholder="输入用户原始查询语句..."
                                        value={createForm.query}
                                        onChange={e => setCreateForm({ ...createForm, query: e.target.value })}
                                    />
                                </div>
                                <div className="space-y-1">
                                    <label className="text-xs text-slate-400">预期结果 (Target) <span className="text-slate-600">(可选)</span></label>
                                    <input
                                        type="text"
                                        className="w-full bg-black/40 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:border-cyan-500 outline-none transition-colors"
                                        placeholder="输入期望的意图分类或结果..."
                                        value={createForm.target}
                                        onChange={e => setCreateForm({ ...createForm, target: e.target.value })}
                                    />
                                </div>
                                <div className="space-y-1">
                                    <label className="text-xs text-slate-400">干预原因 (Reason)</label>
                                    <textarea
                                        className="w-full bg-black/40 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:border-cyan-500 outline-none transition-colors resize-none h-16"
                                        placeholder="说明为什么需要干预该Query..."
                                        value={createForm.reason}
                                        onChange={e => setCreateForm({ ...createForm, reason: e.target.value })}
                                    />
                                </div>

                                {/* 操作按钮 (Moved here) */}
                                <div className="flex justify-end gap-2 pt-2">
                                    <button
                                        onClick={tryCloseCreateModal}
                                        className="px-3 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
                                    >
                                        取消
                                    </button>
                                    <button
                                        onClick={handleCreate}
                                        disabled={!createForm.query.trim()}
                                        className="px-3 py-1.5 rounded-lg text-xs font-medium bg-cyan-600 text-white hover:bg-cyan-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5 shadow-lg shadow-cyan-500/20"
                                    >
                                        <Save size={14} /> 保存
                                    </button>
                                </div>
                            </div>
                        </div>

                        {/* 退出确认弹窗 (Nested) */}
                        {showCreateExitConfirm && (
                            <div className="absolute inset-0 bg-slate-900/95 backdrop-blur-sm flex flex-col items-center justify-center z-20 p-4 text-center">
                                <AlertCircle size={32} className="text-amber-500 mb-3" />
                                <p className="text-slate-200 text-sm font-bold mb-1">放弃新增？</p>
                                <p className="text-slate-400 text-xs mb-4">您已输入了内容，直接退出将丢失所有数据。</p>
                                <div className="flex gap-3">
                                    <button
                                        onClick={cancelExitCreate}
                                        className="px-4 py-1.5 rounded-lg text-xs bg-slate-700 text-slate-300 hover:bg-slate-600 border border-slate-600"
                                    >
                                        继续编辑
                                    </button>
                                    <button
                                        onClick={confirmExitCreate}
                                        className="px-4 py-1.5 rounded-lg text-xs bg-amber-600 text-white hover:bg-amber-500 shadow-lg shadow-amber-500/20"
                                    >
                                        确认放弃
                                    </button>
                                </div>
                            </div>
                        )}
                    </div>
                )
            }
            {/* 测试结果 Modal */}
            {
                testResult && (
                    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                        <div className="bg-slate-900 border border-slate-700 rounded-xl w-full max-w-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in duration-200 flex flex-col max-h-[85vh]">
                            <div className="px-4 py-3 border-b border-slate-800 flex justify-between items-center bg-slate-900/50 shrink-0">
                                <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                                    <FlaskConical size={14} className="text-indigo-400" /> 测试结果
                                </h3>
                                <button
                                    onClick={() => setTestResult(null)}
                                    className="text-slate-500 hover:text-white transition-colors"
                                >
                                    <X size={16} />
                                </button>
                            </div>

                            <div className="p-0 overflow-y-auto custom-scrollbar flex-1">
                                {/* 状态横幅 */}
                                <div className={`p-4 flex items-center gap-3 border-b border-slate-800 ${testResult?.is_correct ? 'bg-emerald-500/10' : 'bg-rose-500/10'}`}>
                                    <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${testResult?.is_correct ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}`}>
                                        {testResult?.is_correct ? <CheckCircle2 size={20} /> : <XCircle size={20} />}
                                    </div>
                                    <div>
                                        <h4 className={`text-base font-bold ${testResult?.is_correct ? 'text-emerald-400' : 'text-rose-400'}`}>
                                            {testResult?.is_correct ? '验证通过' : '验证不通过'}
                                        </h4>
                                        <p className="text-xs text-slate-400 mt-0.5">
                                            Query: <span className="font-mono text-slate-300">{testResult?.query}</span>
                                        </p>
                                    </div>
                                </div>

                                <div className="p-4 space-y-4">
                                    {/* 对比区域 */}
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        {/* 预期结果 */}
                                        <div className="space-y-1.5">
                                            <label className="text-xs font-medium text-slate-500 flex items-center gap-1">
                                                <CheckCircle2 size={10} className="text-emerald-500" /> 预期结果 (Target)
                                            </label>
                                            <div className="bg-emerald-950/30 border border-emerald-500/20 rounded-lg p-3 text-xs text-emerald-100/90 font-mono min-h-[100px] whitespace-pre-wrap">
                                                {testResult?.target || <span className="text-slate-600 italic">未设置</span>}
                                            </div>
                                        </div>

                                        {/* 实际输出 */}
                                        <div className="space-y-1.5">
                                            <label className="text-xs font-medium text-slate-500 flex items-center gap-1">
                                                <Sparkles size={10} className="text-indigo-500" /> 实际输出 (Actual)
                                            </label>
                                            <div className={`bg-slate-950/50 border rounded-lg p-3 text-xs font-mono min-h-[100px] whitespace-pre-wrap ${testResult?.is_correct ? 'border-emerald-500/20 text-emerald-100/90' : 'border-rose-500/20 text-rose-100/90'}`}>
                                                {testResult?.output}
                                            </div>
                                        </div>
                                    </div>

                                    {/* 提取原因/分析 (如果有) */}
                                    {testResult?.reason && (
                                        <div className="space-y-1.5">
                                            <label className="text-xs font-medium text-slate-500">分析/原因 (Reason)</label>
                                            <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-3 text-xs text-slate-300">
                                                {testResult?.reason}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>

                            <div className="p-3 border-t border-slate-800 bg-slate-900/50 flex justify-end">
                                <button
                                    onClick={() => setTestResult(null)}
                                    className="px-4 py-1.5 rounded-lg bg-slate-800 text-slate-300 text-xs hover:bg-slate-700 transition-colors"
                                >
                                    关闭
                                </button>
                            </div>
                        </div>
                    </div>
                )
            }
        </div >
    );
}
