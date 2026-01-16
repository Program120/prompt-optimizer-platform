import { Clock, Trash2, Database, FileText, Download } from "lucide-react";
import { NoteSection } from "./NoteSection";

const API_BASE = "/api";

interface RunHistoryTabProps {
    runHistory: any[];
    projectId: string;
    onDeleteTask?: (task: any) => void;
    onSaveNote: (type: string, id: string, value: string) => Promise<boolean>;
    onViewPrompt?: (prompt: string) => void;
}

export default function RunHistoryTab({ runHistory, projectId, onDeleteTask, onSaveNote, onViewPrompt }: RunHistoryTabProps) {
    /**
     * 下载指定版本的意图干预数据
     * @param fileId 文件版本 ID
     */
    const downloadInterventions = async (fileId: string) => {
        if (!projectId || !fileId) return;

        try {
            const url = `${API_BASE}/projects/${projectId}/interventions/export?file_id=${encodeURIComponent(fileId)}`;
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error("下载失败");
            }
            const blob = await response.blob();
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = downloadUrl;
            a.download = `intent_intervention_${fileId}.csv`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(downloadUrl);
            document.body.removeChild(a);
        } catch (e) {
            console.error("Download interventions failed:", e);
            alert("下载意图干预数据失败");
        }
    };
    const formatTime = (timestamp: string) => {
        if (!timestamp) return "未知";
        try {
            const ts = parseInt(timestamp) * 1000;
            return new Date(ts).toLocaleString();
        } catch {
            return "未知";
        }
    };

    const getStatusStyle = (status: string) => {
        switch (status) {
            case "running": return "bg-blue-500/20 text-blue-400";
            case "completed": return "bg-emerald-500/20 text-emerald-400";
            case "stopped": return "bg-orange-500/20 text-orange-400";
            default: return "bg-slate-500/20 text-slate-400";
        }
    };

    const getStatusText = (status: string) => {
        switch (status) {
            case "running": return "运行中";
            case "completed": return "已完成";
            case "stopped": return "已终止";
            default: return status;
        }
    };

    return (
        <div className="flex-1 overflow-y-auto p-4 custom-scrollbar space-y-3">
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
                                    onClick={(e) => { e.stopPropagation(); onDeleteTask(task); }}
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
                        {onViewPrompt && (
                            <button
                                onClick={(e) => { e.stopPropagation(); onViewPrompt(task.prompt); }}
                                className="text-[10px] text-blue-400 hover:text-blue-300 whitespace-nowrap flex-shrink-0"
                            >
                                查看提示词
                            </button>
                        )}
                    </div>

                    {/* 底部: 进度和准确率 & 结果下载 */}
                    <div className="flex justify-between items-center pt-2 border-t border-white/5">
                        <div className="flex items-center gap-4 text-xs">
                            <span className="text-slate-500">
                                进度: <span className="text-slate-300">{task.results_count}/{task.total_count}</span>
                            </span>
                            <span className="text-slate-500">
                                准确率: <span className="text-emerald-400 font-medium">{task.accuracy !== undefined ? (task.accuracy * 100).toFixed(1) : 0.0}%</span>
                            </span>
                        </div>
                        <a
                            href={`${API_BASE}/tasks/${task.id}/export`}
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
                    <NoteSection
                        type="task"
                        id={task.id}
                        initialNote={task.note}
                        onSave={onSaveNote}
                    />
                </div>
            ))}
            {!runHistory?.length && <p className="text-center text-slate-600 mt-20">暂无运行历史</p>}
        </div>
    );
}
