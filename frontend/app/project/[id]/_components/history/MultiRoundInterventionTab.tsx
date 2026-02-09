import { useState, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
    Search, RefreshCw, Download, Trash2, ChevronDown, ChevronUp,
    Save, RotateCcw, Edit3, FileText, AlertCircle, CheckCircle2
} from "lucide-react";

const API_BASE = "/api";

// ==================== 类型定义 ====================

interface RoundData {
    target: string;
    original_target: string;
    query_rewrite: string;
    reason: string;
    original_query?: string;
}

interface MultiRoundInterventionItem {
    id: number;
    project_id: string;
    file_id: string;
    row_index: number;
    original_query: string;
    rounds_data: Record<string, RoundData>;
    is_modified: boolean;
    created_at: string;
    updated_at: string;
}

interface MultiRoundInterventionTabProps {
    project: any;
    fileId?: string;
    roundsConfig?: Array<{ round: number; query_col: string; target_col: string }>;
    onDataChange?: () => void;
}

// ==================== 组件 ====================

export default function MultiRoundInterventionTab({
    project,
    fileId,
    roundsConfig = [],
    onDataChange
}: MultiRoundInterventionTabProps) {
    // 数据状态
    const [items, setItems] = useState<MultiRoundInterventionItem[]>([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(1);
    const [hasMore, setHasMore] = useState(true);
    const [isLoading, setIsLoading] = useState(false);
    const [isSyncing, setIsSyncing] = useState(false);

    // 搜索和筛选
    const [search, setSearch] = useState("");
    const [filterType, setFilterType] = useState<"all" | "modified">("all");

    // 展开状态
    const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());

    // 编辑状态
    const [editingId, setEditingId] = useState<number | null>(null);
    const [editingData, setEditingData] = useState<Record<string, RoundData>>({});
    const [isSaving, setIsSaving] = useState(false);

    // 滚动容器引用
    const scrollContainerRef = useRef<HTMLDivElement>(null);

    // 获取数据
    const fetchData = useCallback(async (pageNum: number, append: boolean = false) => {
        if (!project?.id) return;

        setIsLoading(true);
        try {
            const params = new URLSearchParams({
                page: pageNum.toString(),
                page_size: "30"
            });
            if (search) params.append("search", search);
            if (filterType !== "all") params.append("filter_type", filterType);
            if (fileId) params.append("file_id", fileId);

            const res = await fetch(
                `${API_BASE}/projects/${project.id}/multi-round-interventions?${params}`
            );

            if (res.ok) {
                const data = await res.json();
                if (append) {
                    setItems(prev => [...prev, ...data.items]);
                } else {
                    setItems(data.items);
                }
                setTotal(data.total);
                setHasMore(data.items.length === 30);
                setPage(pageNum);
            }
        } catch (err) {
            console.error("获取多轮干预数据失败:", err);
        } finally {
            setIsLoading(false);
        }
    }, [project?.id, search, filterType, fileId]);

    // 初始加载
    useEffect(() => {
        fetchData(1, false);
    }, [project?.id, fileId, filterType]);

    // 搜索防抖
    useEffect(() => {
        const timer = setTimeout(() => {
            fetchData(1, false);
        }, 300);
        return () => clearTimeout(timer);
    }, [search]);

    // 加载更多
    const loadMore = () => {
        if (!isLoading && hasMore) {
            fetchData(page + 1, true);
        }
    };

    // 滚动加载
    const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
        const { scrollTop, scrollHeight, clientHeight } = e.currentTarget;
        if (scrollHeight - scrollTop - clientHeight < 100 && !isLoading && hasMore) {
            loadMore();
        }
    };

    // 同步数据（从数据文件同步）
    const handleSync = async () => {
        if (!project?.id || !fileId) {
            alert("请先上传数据文件");
            return;
        }

        if (!roundsConfig || roundsConfig.length === 0) {
            alert("请先配置轮次（Query列和Target列）");
            return;
        }

        setIsSyncing(true);
        try {
            // 获取验证配置中的数据限制
            const validationLimit = project?.config?.multi_round_config?.validation_limit || null;

            const res = await fetch(
                `${API_BASE}/projects/${project.id}/multi-round-interventions/sync`,
                {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        file_id: fileId,
                        rounds_config: roundsConfig,
                        validation_limit: validationLimit
                    })
                }
            );

            if (res.ok) {
                const result = await res.json();
                alert(`同步完成：新增 ${result.synced} 条，跳过 ${result.skipped} 条（共 ${result.total_rows} 行数据）`);
                fetchData(1, false);
                onDataChange?.();
            } else {
                const err = await res.json();
                alert(`同步失败: ${err.detail || "未知错误"}`);
            }
        } catch (err) {
            console.error("同步失败:", err);
            alert("同步失败");
        } finally {
            setIsSyncing(false);
        }
    };

    // 导出
    const handleExport = () => {
        if (!project?.id) return;
        let url = `${API_BASE}/projects/${project.id}/multi-round-interventions/export`;
        if (fileId) url += `?file_id=${encodeURIComponent(fileId)}`;
        window.open(url);
    };

    // 清空
    const handleClear = async () => {
        if (!project?.id) return;
        if (!confirm("确定要清空所有多轮干预数据吗？此操作不可恢复。")) return;

        try {
            let url = `${API_BASE}/projects/${project.id}/multi-round-interventions/clear`;
            if (fileId) url += `?file_id=${encodeURIComponent(fileId)}`;

            const res = await fetch(url, { method: "DELETE" });
            if (res.ok) {
                const result = await res.json();
                alert(`已删除 ${result.deleted} 条记录`);
                fetchData(1, false);
                onDataChange?.();
            }
        } catch (err) {
            console.error("清空失败:", err);
            alert("清空失败");
        }
    };

    // 展开/折叠行
    const toggleExpand = (id: number) => {
        setExpandedRows(prev => {
            const newSet = new Set(prev);
            if (newSet.has(id)) {
                newSet.delete(id);
            } else {
                newSet.add(id);
            }
            return newSet;
        });
    };

    // 开始编辑
    const startEdit = (item: MultiRoundInterventionItem) => {
        setEditingId(item.id);
        setEditingData(JSON.parse(JSON.stringify(item.rounds_data)));
        // 确保展开
        setExpandedRows(prev => new Set(prev).add(item.id));
    };

    // 取消编辑
    const cancelEdit = () => {
        setEditingId(null);
        setEditingData({});
    };

    // 保存编辑
    const saveEdit = async (item: MultiRoundInterventionItem) => {
        if (!project?.id) return;

        setIsSaving(true);
        try {
            const res = await fetch(
                `${API_BASE}/projects/${project.id}/multi-round-interventions`,
                {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        id: item.id,
                        row_index: item.row_index,
                        original_query: item.original_query,
                        rounds_data: editingData,
                        file_id: fileId || ""
                    })
                }
            );

            if (res.ok) {
                const updated = await res.json();
                // 更新本地数据
                setItems(prev => prev.map(i => i.id === item.id ? updated : i));
                setEditingId(null);
                setEditingData({});
                onDataChange?.();
            } else {
                const err = await res.json();
                alert(`保存失败: ${err.detail || "未知错误"}`);
            }
        } catch (err) {
            console.error("保存失败:", err);
            alert("保存失败");
        } finally {
            setIsSaving(false);
        }
    };

    // 重置记录
    const resetItem = async (item: MultiRoundInterventionItem) => {
        if (!project?.id) return;
        if (!confirm("确定要重置此条记录吗？将恢复所有轮次的原始意图，清空改写和备注。")) return;

        try {
            const res = await fetch(
                `${API_BASE}/projects/${project.id}/multi-round-interventions/${item.id}/reset`,
                { method: "POST" }
            );

            if (res.ok) {
                const updated = await res.json();
                setItems(prev => prev.map(i => i.id === item.id ? updated : i));
                onDataChange?.();
            }
        } catch (err) {
            console.error("重置失败:", err);
            alert("重置失败");
        }
    };

    // 删除记录
    const deleteItem = async (item: MultiRoundInterventionItem) => {
        if (!project?.id) return;
        if (!confirm("确定要删除此条记录吗？")) return;

        try {
            const res = await fetch(
                `${API_BASE}/projects/${project.id}/multi-round-interventions/${item.id}`,
                { method: "DELETE" }
            );

            if (res.ok) {
                setItems(prev => prev.filter(i => i.id !== item.id));
                setTotal(prev => prev - 1);
                onDataChange?.();
            }
        } catch (err) {
            console.error("删除失败:", err);
            alert("删除失败");
        }
    };

    // 更新编辑数据
    const updateEditingRound = (roundNum: string, field: keyof RoundData, value: string) => {
        setEditingData(prev => ({
            ...prev,
            [roundNum]: {
                ...prev[roundNum],
                [field]: value
            }
        }));
    };

    // 获取轮次数量
    const getMaxRounds = (item: MultiRoundInterventionItem) => {
        const keys = Object.keys(item.rounds_data || {});
        if (keys.length === 0) return 0;
        return Math.max(...keys.map(k => parseInt(k)));
    };

    return (
        <div className="flex flex-col h-full">
            {/* 工具栏 */}
            <div className="p-4 border-b border-white/10 space-y-3">
                {/* 搜索和筛选 */}
                <div className="flex gap-3">
                    <div className="flex-1 relative">
                        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                        <input
                            type="text"
                            placeholder="搜索 Query..."
                            value={search}
                            onChange={e => setSearch(e.target.value)}
                            className="w-full bg-white/5 border border-white/10 rounded-lg pl-10 pr-4 py-2 text-sm focus:border-purple-500/50 outline-none"
                        />
                    </div>
                    <select
                        value={filterType}
                        onChange={e => setFilterType(e.target.value as "all" | "modified")}
                        className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm focus:border-purple-500/50 outline-none"
                    >
                        <option value="all">全部</option>
                        <option value="modified">已修改</option>
                    </select>
                </div>

                {/* 操作按钮 */}
                <div className="flex gap-2">
                    <button
                        onClick={handleSync}
                        disabled={isSyncing || !fileId || !roundsConfig || roundsConfig.length === 0}
                        className="flex items-center gap-1.5 px-3 py-1.5 bg-purple-500/10 hover:bg-purple-500/20 text-purple-400 text-xs rounded-lg transition-colors disabled:opacity-50"
                    >
                        <RefreshCw size={14} className={isSyncing ? "animate-spin" : ""} />
                        同步数据
                    </button>
                    <button
                        onClick={handleExport}
                        disabled={items.length === 0}
                        className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 text-xs rounded-lg transition-colors disabled:opacity-50"
                    >
                        <Download size={14} />
                        导出
                    </button>
                    <button
                        onClick={handleClear}
                        disabled={items.length === 0}
                        className="flex items-center gap-1.5 px-3 py-1.5 bg-red-500/10 hover:bg-red-500/20 text-red-400 text-xs rounded-lg transition-colors disabled:opacity-50"
                    >
                        <Trash2 size={14} />
                        清空
                    </button>
                    <div className="flex-1" />
                    <span className="text-xs text-slate-500 self-center">
                        共 {total} 条记录
                    </span>
                </div>
            </div>

            {/* 数据列表 */}
            <div
                ref={scrollContainerRef}
                className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-3"
                onScroll={handleScroll}
            >
                {items.length === 0 && !isLoading ? (
                    <div className="flex flex-col items-center justify-center h-full text-slate-500">
                        <FileText size={48} className="mb-4 opacity-50" />
                        <p className="text-sm">暂无多轮干预数据</p>
                        <p className="text-xs mt-2">
                            {!fileId ? "请先在左侧上传数据文件" :
                             !roundsConfig || roundsConfig.length === 0 ? "请先配置轮次（Query列和Target列）" :
                             "点击上方「同步数据」按钮初始化干预数据"}
                        </p>
                    </div>
                ) : (
                    items.map(item => (
                        <InterventionCard
                            key={item.id}
                            item={item}
                            isExpanded={expandedRows.has(item.id)}
                            isEditing={editingId === item.id}
                            editingData={editingId === item.id ? editingData : null}
                            isSaving={isSaving}
                            onToggleExpand={() => toggleExpand(item.id)}
                            onStartEdit={() => startEdit(item)}
                            onCancelEdit={cancelEdit}
                            onSaveEdit={() => saveEdit(item)}
                            onReset={() => resetItem(item)}
                            onDelete={() => deleteItem(item)}
                            onUpdateRound={updateEditingRound}
                            roundsConfig={roundsConfig}
                        />
                    ))
                )}

                {isLoading && (
                    <div className="flex justify-center py-4">
                        <RefreshCw size={20} className="animate-spin text-purple-400" />
                    </div>
                )}

                {!isLoading && hasMore && items.length > 0 && (
                    <button
                        onClick={loadMore}
                        className="w-full py-2 text-xs text-slate-500 hover:text-slate-300 transition-colors"
                    >
                        加载更多...
                    </button>
                )}
            </div>
        </div>
    );
}

// ==================== 子组件：干预卡片 ====================

interface InterventionCardProps {
    item: MultiRoundInterventionItem;
    isExpanded: boolean;
    isEditing: boolean;
    editingData: Record<string, RoundData> | null;
    isSaving: boolean;
    onToggleExpand: () => void;
    onStartEdit: () => void;
    onCancelEdit: () => void;
    onSaveEdit: () => void;
    onReset: () => void;
    onDelete: () => void;
    onUpdateRound: (roundNum: string, field: keyof RoundData, value: string) => void;
    roundsConfig: Array<{ round: number; query_col: string; target_col: string }>;
}

function InterventionCard({
    item,
    isExpanded,
    isEditing,
    editingData,
    isSaving,
    onToggleExpand,
    onStartEdit,
    onCancelEdit,
    onSaveEdit,
    onReset,
    onDelete,
    onUpdateRound,
    roundsConfig
}: InterventionCardProps) {
    const roundNums = Object.keys(item.rounds_data || {}).sort((a, b) => parseInt(a) - parseInt(b));

    return (
        <div className={`bg-slate-800/50 rounded-xl border transition-colors ${
            item.is_modified ? "border-purple-500/30" : "border-white/5"
        }`}>
            {/* 头部 */}
            <div
                className="flex items-center gap-3 p-3 cursor-pointer hover:bg-white/5 transition-colors"
                onClick={onToggleExpand}
            >
                <div className="flex-shrink-0 w-12 h-8 flex items-center justify-center bg-slate-700/50 rounded text-xs font-mono text-slate-400">
                    #{item.row_index}
                </div>
                <div className="flex-1 min-w-0">
                    <p className="text-sm text-slate-300 truncate">
                        {item.original_query || "(无 Query)"}
                    </p>
                    <p className="text-xs text-slate-500 mt-0.5">
                        {roundNums.length} 轮 · 更新于 {new Date(item.updated_at).toLocaleString()}
                    </p>
                </div>
                {item.is_modified && (
                    <span className="px-2 py-0.5 bg-purple-500/20 text-purple-400 text-xs rounded">
                        已修改
                    </span>
                )}
                {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </div>

            {/* 展开内容 */}
            <AnimatePresence>
                {isExpanded && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="overflow-hidden"
                    >
                        <div className="border-t border-white/5 p-3 space-y-3">
                            {/* 各轮次数据 */}
                            {roundNums.map(roundNum => {
                                const rd = isEditing && editingData
                                    ? editingData[roundNum] || {}
                                    : item.rounds_data[roundNum] || {};
                                const isModified = rd.target !== rd.original_target || rd.query_rewrite || rd.reason;

                                return (
                                    <div
                                        key={roundNum}
                                        className={`p-3 rounded-lg border ${
                                            isModified ? "bg-purple-500/5 border-purple-500/20" : "bg-black/20 border-white/5"
                                        }`}
                                    >
                                        <div className="flex items-center gap-2 mb-2">
                                            <span className="text-xs font-medium text-slate-400">
                                                第 {roundNum} 轮
                                            </span>
                                            {isModified && (
                                                <span className="text-[10px] text-purple-400">已修改</span>
                                            )}
                                        </div>

                                        <div className="space-y-2">
                                            {/* 原始 Query */}
                                            <div>
                                                <label className="text-[10px] text-slate-500 block mb-1">原始 Query</label>
                                                <div className="text-xs text-slate-400 bg-black/20 rounded px-2 py-1.5 truncate">
                                                    {rd.original_query || item.original_query || "-"}
                                                </div>
                                            </div>

                                            {/* 期望意图 */}
                                            <div>
                                                <label className="text-[10px] text-slate-500 block mb-1">
                                                    期望意图
                                                    {rd.original_target && rd.target !== rd.original_target && (
                                                        <span className="ml-2 text-slate-600">(原始: {rd.original_target})</span>
                                                    )}
                                                </label>
                                                {isEditing ? (
                                                    <input
                                                        type="text"
                                                        value={rd.target || ""}
                                                        onChange={e => onUpdateRound(roundNum, "target", e.target.value)}
                                                        className="w-full bg-black/30 border border-white/10 rounded px-2 py-1.5 text-xs text-slate-300 focus:border-purple-500/50 outline-none"
                                                        placeholder="输入期望意图..."
                                                    />
                                                ) : (
                                                    <div className={`text-xs rounded px-2 py-1.5 ${
                                                        rd.target !== rd.original_target
                                                            ? "bg-purple-500/10 text-purple-300"
                                                            : "bg-black/20 text-emerald-400"
                                                    }`}>
                                                        {rd.target || "-"}
                                                    </div>
                                                )}
                                            </div>

                                            {/* Query 改写 */}
                                            <div>
                                                <label className="text-[10px] text-slate-500 block mb-1">Query 改写</label>
                                                {isEditing ? (
                                                    <input
                                                        type="text"
                                                        value={rd.query_rewrite || ""}
                                                        onChange={e => onUpdateRound(roundNum, "query_rewrite", e.target.value)}
                                                        className="w-full bg-black/30 border border-white/10 rounded px-2 py-1.5 text-xs text-slate-300 focus:border-purple-500/50 outline-none"
                                                        placeholder="输入改写后的 Query（留空使用原始）..."
                                                    />
                                                ) : (
                                                    <div className={`text-xs rounded px-2 py-1.5 ${
                                                        rd.query_rewrite
                                                            ? "bg-blue-500/10 text-blue-300"
                                                            : "bg-black/20 text-slate-500 italic"
                                                    }`}>
                                                        {rd.query_rewrite || "未改写"}
                                                    </div>
                                                )}
                                            </div>

                                            {/* 备注 */}
                                            <div>
                                                <label className="text-[10px] text-slate-500 block mb-1">备注</label>
                                                {isEditing ? (
                                                    <textarea
                                                        value={rd.reason || ""}
                                                        onChange={e => onUpdateRound(roundNum, "reason", e.target.value)}
                                                        className="w-full bg-black/30 border border-white/10 rounded px-2 py-1.5 text-xs text-slate-300 focus:border-purple-500/50 outline-none resize-none"
                                                        rows={2}
                                                        placeholder="输入备注..."
                                                    />
                                                ) : (
                                                    <div className={`text-xs rounded px-2 py-1.5 ${
                                                        rd.reason
                                                            ? "bg-amber-500/10 text-amber-300"
                                                            : "bg-black/20 text-slate-500 italic"
                                                    }`}>
                                                        {rd.reason || "无备注"}
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                );
                            })}

                            {/* 操作按钮 */}
                            <div className="flex justify-end gap-2 pt-2 border-t border-white/5">
                                {isEditing ? (
                                    <>
                                        <button
                                            onClick={onCancelEdit}
                                            className="px-3 py-1.5 text-xs text-slate-400 hover:text-slate-300 transition-colors"
                                        >
                                            取消
                                        </button>
                                        <button
                                            onClick={onSaveEdit}
                                            disabled={isSaving}
                                            className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 text-xs rounded-lg transition-colors disabled:opacity-50"
                                        >
                                            <Save size={12} />
                                            {isSaving ? "保存中..." : "保存"}
                                        </button>
                                    </>
                                ) : (
                                    <>
                                        <button
                                            onClick={onDelete}
                                            className="flex items-center gap-1.5 px-3 py-1.5 text-red-400 hover:bg-red-500/10 text-xs rounded-lg transition-colors"
                                        >
                                            <Trash2 size={12} />
                                            删除
                                        </button>
                                        {item.is_modified && (
                                            <button
                                                onClick={onReset}
                                                className="flex items-center gap-1.5 px-3 py-1.5 text-amber-400 hover:bg-amber-500/10 text-xs rounded-lg transition-colors"
                                            >
                                                <RotateCcw size={12} />
                                                重置
                                            </button>
                                        )}
                                        <button
                                            onClick={onStartEdit}
                                            className="flex items-center gap-1.5 px-3 py-1.5 bg-purple-500/10 hover:bg-purple-500/20 text-purple-400 text-xs rounded-lg transition-colors"
                                        >
                                            <Edit3 size={12} />
                                            编辑
                                        </button>
                                    </>
                                )}
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}
