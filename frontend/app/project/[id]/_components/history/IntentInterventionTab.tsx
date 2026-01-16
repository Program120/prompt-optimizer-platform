import { useState, useEffect } from "react";
import { Database, Edit3, FileText, CheckCircle2, AlertCircle } from "lucide-react";

const API_BASE = "/api";

interface IntentInterventionTabProps {
    project: any;
    fileId?: string;
    saveReason: (query: string, reason: string, target: string) => Promise<void>;
}

export default function IntentInterventionTab({ project, fileId, saveReason }: IntentInterventionTabProps) {
    const [intentItems, setIntentItems] = useState<any[]>([]);
    const [intentPage, setIntentPage] = useState(1);
    const [intentTotal, setIntentTotal] = useState(0);
    const [intentLoading, setIntentLoading] = useState(false);
    const [intentSearch, setIntentSearch] = useState("");
    const [intentFilter, setIntentFilter] = useState("all");
    const [editingReason, setEditingReason] = useState<{ query: string, value: string, target: string } | null>(null);

    const fetchIntentData = async (pageNum: number = 1, search: string = "") => {
        if (!project?.id || !fileId) return;
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
            }
        } catch (e) {
            console.error("Failed to fetch intent data", e);
        } finally {
            setIntentLoading(false);
        }
    };

    // Initial load and filter change
    useEffect(() => {
        setIntentPage(1);
        setIntentItems([]);
        fetchIntentData(1, intentSearch);
    }, [project?.id, fileId, intentFilter]);

    // Search debounce
    useEffect(() => {
        const timer = setTimeout(() => {
            setIntentPage(1);
            setIntentItems([]);
            fetchIntentData(1, intentSearch);
        }, 500);
        return () => clearTimeout(timer);
    }, [intentSearch]);

    if (!fileId) {
        return (
            <div className="flex flex-col items-center justify-center h-64 text-slate-500">
                <Database className="w-12 h-12 mb-4 opacity-20" />
                <p>请先上传或选择一个数据文件</p>
                <p className="text-sm opacity-60 mt-2">意图干预数据与文件版本绑定</p>
            </div>
        );
    }

    return (
        <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
            {/* Toolbar */}
            <div className="bg-slate-800/40 p-3 rounded-xl border border-white/5 mb-4 space-y-3">
                {/* Filter & Actions Row */}
                <div className="flex justify-between items-center gap-4">
                    <div className="flex items-center gap-2">
                        <span className="text-xs text-slate-400">筛选:</span>
                        <select
                            value={intentFilter}
                            onChange={(e) => setIntentFilter(e.target.value)}
                            className="bg-black/30 border border-white/10 text-xs text-slate-300 rounded px-2 py-1 outline-none focus:border-blue-500/50"
                        >
                            <option value="all">全部数据</option>
                            <option value="modified">意图修正</option>
                            <option value="reason_added">原因标注</option>
                        </select>
                    </div>
                </div>

                {/* Search Row */}
                <input
                    type="text"
                    className="w-full bg-black/30 border border-white/10 rounded px-3 py-1.5 text-xs text-slate-300 outline-none focus:border-blue-500/50 placeholder:text-slate-600"
                    placeholder="搜索 Query, 预期结果 或 原因..."
                    value={intentSearch}
                    onChange={(e) => setIntentSearch(e.target.value)}
                />
            </div>

            {/* Content List */}
            {intentLoading && intentPage === 1 ? (
                <div className="flex justify-center py-10">
                    <div className="w-6 h-6 border-2 border-slate-500/30 border-t-slate-500 rounded-full animate-spin"></div>
                </div>
            ) : (
                <div className="space-y-3">
                    {intentItems.map((item, idx) => {
                        const isEditing = editingReason?.query === item.query;
                        return (
                            <div key={item.id || idx} className="p-4 rounded-xl border border-white/5 bg-slate-900/40 hover:bg-slate-900/60 transition-colors gap-3 flex flex-col group relative overflow-hidden">
                                {/* Decorative gradient blob */}
                                <div className="absolute top-0 right-0 w-32 h-32 bg-blue-500/5 rounded-full blur-3xl -z-10 pointer-events-none"></div>

                                {/* Header: Query & Badges */}
                                <div className="mb-2">
                                    <div className="flex items-center gap-2 mb-2">
                                        <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-blue-500/10 border border-blue-500/20">
                                            <span className="w-1.5 h-1.5 rounded-full bg-blue-400"></span>
                                            <span className="text-blue-200 font-medium text-xs">Query</span>
                                        </div>
                                        {item.is_target_modified && (
                                            <span className="px-1.5 py-0.5 bg-indigo-500/20 text-indigo-300 text-[10px] rounded border border-indigo-500/30 flex items-center gap-1">
                                                <Edit3 size={8} /> 意图修正
                                            </span>
                                        )}
                                        {item.reason && (
                                            <span className="px-1.5 py-0.5 bg-amber-500/20 text-amber-300 text-[10px] rounded border border-amber-500/30 flex items-center gap-1">
                                                <FileText size={8} /> 原因标注
                                            </span>
                                        )}
                                    </div>
                                    <div className="bg-black/30 p-3 rounded-lg border border-white/10 text-slate-200 min-h-[36px] break-all text-sm font-mono leading-relaxed shadow-inner">
                                        {item.query}
                                    </div>
                                </div>

                                {/* Body: Target & Reason (Editable) */}
                                {isEditing ? (
                                    <div className="space-y-3 bg-black/40 p-4 rounded-xl border border-blue-500/20 shadow-lg relative">
                                        <div className="space-y-1.5">
                                            <label className="text-[11px] text-emerald-400 font-medium flex items-center gap-1.5">
                                                <CheckCircle2 size={12} /> 预期结果 (Target)
                                            </label>
                                            <textarea
                                                className="w-full bg-slate-900/80 border border-emerald-500/20 rounded-lg p-2.5 text-xs text-emerald-100 focus:border-emerald-500/50 outline-none resize-none shadow-inner font-mono"
                                                rows={3}
                                                value={editingReason?.target || ""}
                                                onChange={(e) => setEditingReason(prev => prev ? { ...prev, target: e.target.value } : null)}
                                            />
                                        </div>
                                        <div className="space-y-1.5">
                                            <label className="text-[11px] text-rose-400 font-medium flex items-center gap-1.5">
                                                <AlertCircle size={12} /> 原因 (Reason)
                                            </label>
                                            <textarea
                                                className="w-full bg-slate-900/80 border border-rose-500/20 rounded-lg p-2.5 text-xs text-rose-100 focus:border-rose-500/50 outline-none resize-none shadow-inner"
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
                                                        setEditingReason(null);
                                                    }
                                                }}
                                                className="px-4 py-1.5 text-xs font-medium bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition-all shadow-lg hover:shadow-blue-500/25"
                                            >
                                                保存修改
                                            </button>
                                            <button
                                                onClick={() => setEditingReason(null)}
                                                className="px-3 py-1.5 text-xs text-slate-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
                                            >
                                                取消
                                            </button>
                                        </div>
                                    </div>
                                ) : (
                                    <div
                                        className="grid grid-cols-1 md:grid-cols-2 gap-4 cursor-pointer hover:bg-white/5 rounded-xl transition-all p-3 border border-transparent hover:border-white/5 relative group/item"
                                        onClick={() => setEditingReason({ query: item.query, target: item.target, value: item.reason })}
                                    >
                                        <div className="flex flex-col gap-1.5">
                                            <span className="text-[10px] uppercase tracking-wider text-emerald-500/70 font-bold flex items-center gap-1.5">
                                                <CheckCircle2 size={10} /> 预期结果
                                            </span>
                                            <div className="text-xs text-emerald-100/90 break-words leading-relaxed font-medium">
                                                {item.target || <span className="text-slate-600 italic font-normal">未设置 (保持原样)</span>}
                                            </div>
                                        </div>
                                        <div className="flex flex-col gap-1.5 border-t md:border-t-0 md:border-l border-white/5 pt-2 md:pt-0 md:pl-4">
                                            <span className="text-[10px] uppercase tracking-wider text-rose-500/70 font-bold flex items-center gap-1.5">
                                                <AlertCircle size={10} /> 标注原因
                                            </span>
                                            <div className="text-xs text-rose-100/90 break-words leading-relaxed">
                                                {item.reason || <span className="text-slate-600 italic font-normal">未标注</span>}
                                            </div>
                                        </div>

                                        {/* Edit Hint - Visible on Hover */}
                                        <div className="absolute top-2 right-2 opacity-0 group-hover/item:opacity-100 transition-opacity">
                                            <div className="bg-white/10 p-1.5 rounded-lg backdrop-blur-sm border border-white/5">
                                                <Edit3 size={12} className="text-blue-400" />
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        );
                    })}

                    {/* Infinite Scroll Trigger */}
                    <div ref={(node) => {
                        if (node && !intentLoading && intentItems.length < intentTotal) {
                            const observer = new IntersectionObserver(entries => {
                                if (entries[0].isIntersecting) {
                                    fetchIntentData(intentPage + 1, intentSearch);
                                }
                            }, { threshold: 1.0 });
                            observer.observe(node);
                            return () => observer.disconnect();
                        }
                    }} className="py-4 text-center">
                        {intentLoading ? (
                            <div className="flex justify-center items-center gap-2 text-slate-500 text-xs">
                                <div className="w-4 h-4 border-2 border-slate-500/30 border-t-slate-500 rounded-full animate-spin"></div>
                                加载更多...
                            </div>
                        ) : intentItems.length >= intentTotal && intentItems.length > 0 ? (
                            <span className="text-slate-600 text-xs">没有更多数据了</span>
                        ) : null}
                    </div>
                </div>
            )}
        </div>
    );
}
