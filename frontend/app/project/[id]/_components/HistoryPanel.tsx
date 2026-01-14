import { useState, useEffect } from "react";
import { CheckCircle2, AlertCircle, ArrowRight, Download, Clock, FileText, Database, X, Copy, Layers, TrendingUp, Trash2, Edit3, Save } from "lucide-react";

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
}

export default function HistoryPanel({
    taskStatus,
    project,
    runHistory,
    onSelectLog,
    onSelectIteration,
    knowledgeRecords,
    onSelectKnowledge,
    onDeleteTask,
    onDeleteIteration,
    onDeleteKnowledge,
    onRefresh
}: HistoryPanelProps) {
    const [activeTab, setActiveTab] = useState("run"); // run, history, runHistory
    const [showPromptModal, setShowPromptModal] = useState(false);
    const [currentPrompt, setCurrentPrompt] = useState("");

    // Note editing state
    const [editingNote, setEditingNote] = useState<{ type: 'task' | 'iteration' | 'knowledge', id: string, value: string } | null>(null);

    // Optimistic UI state for notes: stores { [key]: noteValue }
    // Key format: `${type}_${id}`
    // This allows immediate feedback while background refresh happens
    const [localNotes, setLocalNotes] = useState<Record<string, string>>({});

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
                    onClick={() => setActiveTab("knowledge")}
                    className={`flex-1 py-4 text-sm font-medium transition-colors ${activeTab === "knowledge" ? "bg-white/5 text-purple-400 border-b-2 border-purple-500" : "text-slate-500 hover:text-slate-300"}`}
                >
                    优化分析
                </button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
                {activeTab === "run" ? (
                    <>
                        {/* 进度信息 (移除了下载按钮) */}
                        {taskStatus?.id && taskStatus?.results?.length > 0 && (
                            <div className="mb-3 flex justify-between items-center">
                                <span className="text-xs text-slate-500">
                                    已完成 {taskStatus.results.length}/{taskStatus.total_count || '?'} 条
                                </span>
                            </div>
                        )}
                        {taskStatus?.results?.slice().reverse().map((r: any, idx: number) => (
                            <div
                                key={idx}
                                onClick={() => onSelectLog(r)}
                                className={`p-3 rounded-xl border text-xs cursor-pointer hover:opacity-80 transition-opacity mb-2 ${r.is_correct ? "bg-emerald-500/5 border-emerald-500/20" : "bg-red-500/5 border-red-500/20"}`}
                            >
                                <div className="flex justify-between items-center mb-1">
                                    <span className="font-medium text-slate-500">Query {r.index + 1}</span>
                                    {r.is_correct ? <CheckCircle2 size={14} className="text-emerald-500" /> : <AlertCircle size={14} className="text-red-500" />}
                                </div>
                                <p className="text-slate-300 mb-1 truncate">{r.query}</p>
                                <div className="flex items-center gap-2 text-slate-500">
                                    <span className="truncate flex-1">预期: {r.target}</span>
                                    <ArrowRight size={10} />
                                    <span className="truncate flex-1 text-slate-400">输出: {r.output}</span>
                                </div>
                            </div>
                        ))}
                        {!taskStatus?.results?.length && <p className="text-center text-slate-600 mt-20">暂无运行日志</p>}
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
                                    <span className="text-sm font-bold">迭代 #{project.iterations.length - idx}</span>
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
                                <div className="text-xs bg-white/5 rounded-lg p-3 border border-white/5 hover:bg-white/10 transition-colors">
                                    <div className="flex justify-between items-start mb-1">
                                        <div className="text-emerald-400 font-bold">准确率: {(it.accuracy * 100).toFixed(1)}%</div>
                                        {it.dataset_name && (
                                            <span className="text-[10px] text-slate-500 bg-white/5 px-2 py-0.5 rounded-full truncate max-w-[120px]" title={it.dataset_name}>
                                                {it.dataset_name}
                                            </span>
                                        )}
                                    </div>
                                    <p className="text-slate-500 line-clamp-3 italic mb-2">"{it.new_prompt}"</p>

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
                ) : null}
            </div>

            {/* Prompt Modal */}
            {showPromptModal && (
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
            )}
        </section>
    );
}
