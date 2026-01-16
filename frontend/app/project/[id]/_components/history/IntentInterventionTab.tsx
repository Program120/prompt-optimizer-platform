import { useState, useEffect, useRef, useCallback } from "react";
import { Database, Edit3, FileText, CheckCircle2, AlertCircle, RotateCcw, Search, Filter, MessageSquare, Sparkles, X, Save, LogOut } from "lucide-react";
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
 */
export default function IntentInterventionTab({ project, fileId, saveReason }: IntentInterventionTabProps) {
    const [intentItems, setIntentItems] = useState<any[]>([]);
    const [intentPage, setIntentPage] = useState(1);
    const [intentTotal, setIntentTotal] = useState(0);
    const [intentLoading, setIntentLoading] = useState(false);
    const [intentSearch, setIntentSearch] = useState("");
    const [intentFilter, setIntentFilter] = useState("all");
    const [editingReason, setEditingReason] = useState<EditingState | null>(null);
    const [resettingQuery, setResettingQuery] = useState<string | null>(null);
    const [showExitConfirm, setShowExitConfirm] = useState(false);
    // 用于标记是否是组件内的首次加载（只在组件挂载时为 false）
    const [hasMounted, setHasMounted] = useState(false);

    // 无限滚动的observer引用
    const observerRef = useRef<IntersectionObserver | null>(null);
    const loaderRef = useRef<HTMLDivElement | null>(null);
    // 编辑面板引用，用于点击外部检测
    const editPanelRef = useRef<HTMLDivElement | null>(null);
    // 用于在 observer 回调中访问最新状态
    const stateRef = useRef({ intentPage: 1, intentSearch: '', intentLoading: false, intentTotal: 0, itemsLength: 0 });

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
     * 如果有未保存内容则显示确认弹窗
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
     * 重置单条意图干预记录
     */
    const resetIntervention = async (query: string) => {
        if (!project?.id) return;
        if (!window.confirm("确定要重置此条记录吗？\n这将恢复原始预期意图并清空原因。")) return;

        setResettingQuery(query);
        try {
            const res = await fetch(`${API_BASE}/projects/${project.id}/interventions/reset`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ query })
            });
            if (res.ok) {
                fetchIntentData(1, intentSearch);
            } else {
                alert("重置失败");
            }
        } catch (e) {
            console.error("Reset intervention failed:", e);
            alert("重置出错");
        } finally {
            setResettingQuery(null);
        }
    };

    const fetchIntentData = async (pageNum: number = 1, search: string = "") => {
        if (!project?.id || !fileId) return;
        // 更新 ref 状态防止重复加载
        stateRef.current.intentLoading = true;
        stateRef.current.intentPage = pageNum;
        stateRef.current.intentSearch = search;
        setIntentLoading(true);
        try {
            let url = `${API_BASE}/projects/${project.id}/interventions?page=${pageNum}&page_size=20`;
            if (search) url += `&search=${encodeURIComponent(search)}`;
            if (intentFilter !== "all") url += `&filter_type=${intentFilter}`;
            if (fileId) url += `&file_id=${fileId}`;

            const res = await fetch(url);
            if (res.ok) {
                const data = await res.json();
                if (pageNum === 1) {
                    setIntentItems(data.items || []);
                } else {
                    setIntentItems(prev => [...prev, ...(data.items || [])]);
                }
                setIntentTotal(data.total || 0);
                setIntentPage(data.page || 1);
                // 更新 ref 状态
                stateRef.current.intentTotal = data.total || 0;
                stateRef.current.intentPage = data.page || 1;
                stateRef.current.itemsLength = pageNum === 1 ? (data.items?.length || 0) : stateRef.current.itemsLength + (data.items?.length || 0);
                // 组件已挂载
                if (!hasMounted) {
                    setHasMounted(true);
                }
            }
        } catch (e) {
            console.error("Failed to fetch intent data", e);
        } finally {
            setIntentLoading(false);
            stateRef.current.intentLoading = false;
        }
    };

    /**
     * 保存并退出编辑
     */
    const saveAndExit = useCallback(async () => {
        if (editingReason) {
            const currentItem = intentItems.find(item => item.query === editingReason.query);
            if (currentItem) {
                await saveReason(currentItem.query, editingReason.value, editingReason.target);
                fetchIntentData(intentPage, intentSearch);
            }
            setShowExitConfirm(false);
            setEditingReason(null);
        }
    }, [editingReason, intentItems, intentPage, intentSearch, saveReason]);

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

        // 使用 mousedown 而非 click，以便在用户点击时立即响应
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [editingReason, tryCloseEditor]);

    // 无限滚动 Observer 管理 - 只在组件挂载后初始化一次
    useEffect(() => {
        // 创建 observer，在回调中使用 ref 获取最新状态
        observerRef.current = new IntersectionObserver(
            (entries) => {
                if (entries[0].isIntersecting) {
                    const { intentLoading, itemsLength, intentTotal, intentPage, intentSearch } = stateRef.current;
                    // 检查是否可以加载更多
                    if (!intentLoading && itemsLength < intentTotal) {
                        fetchIntentData(intentPage + 1, intentSearch);
                    }
                }
            },
            { threshold: 0.1, rootMargin: '100px' }
        );

        return () => {
            if (observerRef.current) {
                observerRef.current.disconnect();
            }
        };
    }, []);

    // 当 loaderRef 存在时，绑定 observer
    useEffect(() => {
        if (loaderRef.current && observerRef.current) {
            observerRef.current.observe(loaderRef.current);
        }
        return () => {
            if (observerRef.current) {
                observerRef.current.disconnect();
            }
        };
    }, [intentItems.length > 0]);

    useEffect(() => {
        setIntentPage(1);
        setIntentItems([]);
        stateRef.current = { intentPage: 1, intentSearch, intentLoading: false, intentTotal: 0, itemsLength: 0 };
        fetchIntentData(1, intentSearch);
    }, [project?.id, fileId, intentFilter]);

    useEffect(() => {
        const timer = setTimeout(() => {
            setIntentPage(1);
            setIntentItems([]);
            stateRef.current = { intentPage: 1, intentSearch, intentLoading: false, intentTotal: 0, itemsLength: 0 };
            fetchIntentData(1, intentSearch);
        }, 500);
        return () => clearTimeout(timer);
    }, [intentSearch]);

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
        <div className="flex-1 overflow-y-auto p-4 custom-scrollbar space-y-3">
            {/* 搜索与筛选工具栏 */}
            <div className="flex flex-col sm:flex-row gap-2">
                {/* 搜索框 */}
                <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={12} />
                    <input
                        type="text"
                        className="w-full bg-slate-800/50 border border-slate-700/50 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-200 outline-none focus:border-cyan-500/50 transition-all placeholder:text-slate-600"
                        placeholder="搜索 Query, 预期结果 或 原因..."
                        value={intentSearch}
                        onChange={(e) => setIntentSearch(e.target.value)}
                    />
                </div>

                {/* 筛选下拉 */}
                <div className="flex items-center gap-1.5 px-2.5 py-1.5 bg-slate-800/50 rounded-lg border border-slate-700/50">
                    <Filter size={12} className="text-slate-400" />
                    <select
                        value={intentFilter}
                        onChange={(e) => setIntentFilter(e.target.value)}
                        className="bg-transparent text-xs text-slate-300 outline-none cursor-pointer"
                    >
                        <option value="all" className="bg-slate-900">全部</option>
                        <option value="modified" className="bg-slate-900">已修正</option>
                        <option value="reason_added" className="bg-slate-900">已标注</option>
                    </select>
                </div>
            </div>

            {/* 数据列表 */}
            <div className="space-y-3">
                {intentLoading && intentPage === 1 ? (
                    <div className="flex flex-col items-center justify-center py-20 gap-3">
                        <div className="w-6 h-6 border-2 border-cyan-500/30 border-t-cyan-500 rounded-full animate-spin" />
                        <span className="text-xs text-slate-500">加载中...</span>
                    </div>
                ) : (
                    <>
                        {intentItems.map((item, idx) => {
                            const isEditing = editingReason?.query === item.query;
                            const hasModification = item.is_target_modified;
                            const hasReason = !!item.reason;

                            return (
                                <div
                                    key={item.id || item.query}
                                    className="relative p-3 rounded-xl border border-cyan-500/20 bg-gradient-to-br from-cyan-600/5 to-blue-600/5 hover:from-cyan-600/10 hover:to-blue-600/10 transition-all group"
                                >
                                    {/* 头部：Query 标签和状态 */}
                                    <div className="flex justify-between items-center mb-2">
                                        <div className="flex items-center gap-2">
                                            <div className="w-6 h-6 rounded-lg bg-cyan-500/20 flex items-center justify-center">
                                                <MessageSquare size={12} className="text-cyan-400" />
                                            </div>
                                            <span className="text-sm font-bold text-white">Query</span>
                                            {hasModification && (
                                                <span className="px-1.5 py-0.5 bg-indigo-500/20 text-indigo-300 text-[10px] rounded border border-indigo-500/30 flex items-center gap-0.5">
                                                    <Edit3 size={8} /> 已修正
                                                </span>
                                            )}
                                            {hasReason && (
                                                <span className="px-1.5 py-0.5 bg-amber-500/20 text-amber-300 text-[10px] rounded border border-amber-500/30 flex items-center gap-0.5">
                                                    <FileText size={8} /> 已标注
                                                </span>
                                            )}
                                        </div>
                                        {(hasModification || hasReason) && (
                                            <button
                                                onClick={(e) => { e.stopPropagation(); resetIntervention(item.query); }}
                                                disabled={resettingQuery === item.query}
                                                className="opacity-0 group-hover:opacity-100 p-1 text-slate-500 hover:text-red-400 transition-all"
                                                title="重置"
                                            >
                                                <RotateCcw size={12} className={resettingQuery === item.query ? "animate-spin" : ""} />
                                            </button>
                                        )}
                                    </div>

                                    {/* Query 内容 */}
                                    <p className="text-[11px] text-slate-300 font-mono bg-black/20 p-2 rounded-lg border border-white/5 mb-2 line-clamp-2 break-all">
                                        {item.query}
                                    </p>

                                    {/* 编辑模式 */}
                                    {isEditing ? (
                                        <motion.div
                                            ref={editPanelRef}
                                            initial={{ opacity: 0 }}
                                            animate={{ opacity: 1 }}
                                            className="space-y-2 pt-2 border-t border-white/10"
                                        >
                                            {/* 预期结果 */}
                                            <div>
                                                <label className="text-[10px] font-medium text-emerald-400 flex items-center gap-1 mb-1">
                                                    <CheckCircle2 size={10} /> 预期结果
                                                </label>
                                                <textarea
                                                    className="w-full bg-black/30 border border-emerald-500/30 rounded-lg p-2 text-xs text-emerald-100 focus:border-emerald-500/60 outline-none resize-none font-mono"
                                                    rows={2}
                                                    value={editingReason?.target || ""}
                                                    onChange={(e) => setEditingReason(prev => prev ? { ...prev, target: e.target.value } : null)}
                                                    placeholder="输入期望的模型输出..."
                                                />
                                            </div>

                                            {/* 问题原因 */}
                                            <div>
                                                <label className="text-[10px] font-medium text-rose-400 flex items-center gap-1 mb-1">
                                                    <AlertCircle size={10} /> 问题原因
                                                </label>
                                                <textarea
                                                    className="w-full bg-black/30 border border-rose-500/30 rounded-lg p-2 text-xs text-rose-100 focus:border-rose-500/60 outline-none resize-none"
                                                    rows={2}
                                                    value={editingReason?.value || ""}
                                                    onChange={(e) => setEditingReason(prev => prev ? { ...prev, value: e.target.value } : null)}
                                                    placeholder="分析为什么模型回答错误..."
                                                />
                                            </div>

                                            {/* 操作按钮 */}
                                            <div className="flex justify-end gap-2 pt-1">
                                                <button
                                                    onClick={(e) => { e.stopPropagation(); tryCloseEditor(); }}
                                                    className="px-2.5 py-1 text-[10px] text-slate-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
                                                >
                                                    取消
                                                </button>
                                                <button
                                                    onClick={async () => {
                                                        if (editingReason) {
                                                            await saveReason(item.query, editingReason.value, editingReason.target);
                                                            fetchIntentData(intentPage, intentSearch);
                                                            setEditingReason(null);
                                                        }
                                                    }}
                                                    className="px-3 py-1 text-[10px] font-medium bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white rounded-lg transition-all"
                                                >
                                                    保存
                                                </button>
                                            </div>
                                        </motion.div>
                                    ) : (
                                        /* 查看模式 - 横向紧凑布局 */
                                        <div
                                            className="flex gap-2 cursor-pointer"
                                            onClick={() => setEditingReason({
                                                query: item.query,
                                                target: item.target || '',
                                                value: item.reason || '',
                                                originalTarget: item.target || '',
                                                originalValue: item.reason || ''
                                            })}
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
                                    )}
                                </div>
                            );
                        })}
                    </>
                )}

                {/* 无限滚动触发器 - 放在条件渲染外面，确保始终可见 */}
                <div ref={loaderRef} className="py-4 text-center">
                    {intentLoading && intentPage > 1 && (
                        <div className="flex justify-center items-center gap-2 text-slate-500 text-xs">
                            <div className="w-3 h-3 border-2 border-slate-500/30 border-t-slate-500 rounded-full animate-spin" />
                            <span>加载更多...</span>
                        </div>
                    )}
                    {!intentLoading && intentItems.length >= intentTotal && intentItems.length > 0 && (
                        <div className="text-slate-600 text-[10px]">· 已加载全部 ·</div>
                    )}
                </div>
            </div>

            {/* 空状态 */}
            {!intentLoading && intentItems.length === 0 && (
                <div className="flex flex-col items-center justify-center py-20">
                    <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-slate-700/50 to-slate-600/50 flex items-center justify-center mb-4 border border-slate-600/30">
                        <Sparkles className="w-8 h-8 text-slate-500" />
                    </div>
                    <p className="text-slate-400 text-sm">未找到匹配的数据</p>
                    <p className="text-slate-600 text-xs mt-1">尝试调整搜索条件或筛选器</p>
                </div>
            )}

            {/* 未保存内容确认对话框 */}
            <AnimatePresence>
                {showExitConfirm && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center"
                        onClick={(e) => { e.stopPropagation(); cancelExit(); }}
                    >
                        <motion.div
                            initial={{ scale: 0.9, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ scale: 0.9, opacity: 0 }}
                            className="bg-slate-800 border border-slate-700 rounded-xl p-5 shadow-2xl max-w-sm w-full mx-4"
                            onClick={(e) => e.stopPropagation()}
                        >
                            <div className="flex items-center gap-3 mb-4">
                                <div className="w-10 h-10 rounded-xl bg-amber-500/20 flex items-center justify-center">
                                    <AlertCircle className="w-5 h-5 text-amber-400" />
                                </div>
                                <div>
                                    <h3 className="text-white font-semibold">有未保存的更改</h3>
                                    <p className="text-slate-400 text-xs">您有未保存的编辑内容，是否保存？</p>
                                </div>
                            </div>
                            <div className="flex justify-end gap-2">
                                <button
                                    onClick={cancelExit}
                                    className="px-3 py-1.5 text-xs text-slate-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
                                >
                                    取消
                                </button>
                                <button
                                    onClick={confirmExit}
                                    className="px-3 py-1.5 text-xs text-rose-400 hover:text-white hover:bg-rose-500/20 rounded-lg transition-colors flex items-center gap-1"
                                >
                                    <LogOut size={12} />
                                    不保存退出
                                </button>
                                <button
                                    onClick={saveAndExit}
                                    className="px-3 py-1.5 text-xs font-medium bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white rounded-lg transition-all flex items-center gap-1"
                                >
                                    <Save size={12} />
                                    保存并退出
                                </button>
                            </div>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}
