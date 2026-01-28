import { useState, useRef, useEffect, useCallback } from "react";
import { Search, RotateCcw } from "lucide-react";
import RunLogTab from "./history/RunLogTab";
import RunHistoryTab from "./history/RunHistoryTab";
import IterationHistoryTab from "./history/IterationHistoryTab";
import OptimizationAnalysisTab from "./history/OptimizationAnalysisTab";
import IntentInterventionTab from "./history/IntentInterventionTab";

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
    onInterventionDataChange?: () => void;  // 意图干预数据变更时回调
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
    reasonsUpdateCount = 0,
    onInterventionDataChange
}: HistoryPanelProps) {
    const [activeTab, setActiveTab] = useState("run"); // run, history, runHistory, knowledge, intent
    const [showPromptModal, setShowPromptModal] = useState(false);
    const [currentPrompt, setCurrentPrompt] = useState("");

    // Reasons state (Shared across tabs)
    const [reasons, setReasons] = useState<Record<string, any>>({});

    // Fetch Reasons - 使用 useCallback 保持引用稳定
    const fetchReasons = useCallback(async () => {
        if (!project?.id) return;
        try {
            // 使用较大的 page_size 确保获取所有干预数据
            // 添加 file_id 参数确保获取正确版本的数据
            let url = `${API_BASE}/projects/${project.id}/interventions?page_size=10000`;
            if (fileId) {
                url += `&file_id=${encodeURIComponent(fileId)}`;
            }
            const res = await fetch(url);
            if (res.ok) {
                const data = await res.json();
                const map: Record<string, any> = {};
                // Note: Update assuming paginated API returns {items: []}
                if (data.items) {
                    data.items.forEach((r: any) => map[r.query] = r);
                } else if (Array.isArray(data)) {
                    data.forEach((r: any) => map[r.query] = r);
                }
                setReasons(map);
            }
        } catch (e) {
            console.error("Failed to fetch reasons", e);
        }
    }, [project?.id, fileId]);

    useEffect(() => {
        fetchReasons();
    }, [project?.id, reasonsUpdateCount, fileId]);

    // Save Reason Handler - 使用 useCallback 保持引用稳定，避免子组件不必要的重渲染
    // 返回 boolean 表示保存成功/失败
    const saveReason = useCallback(async (query: string, reason: string, target: string, id?: number): Promise<boolean> => {
        if (!project?.id) return false;
        try {
            const res = await fetch(`${API_BASE}/projects/${project.id}/interventions`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                // [修复] 添加 file_id 确保更新正确的记录
                // [修复] 添加 id 确保更新唯一记录
                body: JSON.stringify({ query, reason, target, file_id: fileId || "", id })
            });
            if (res.ok) {
                await fetchReasons();
                return true;
            } else {
                console.error("保存原因失败:", await res.text());
                return false;
            }
        } catch (e) {
            console.error("保存原因出错:", e);
            return false;
        }
    }, [project?.id, fetchReasons, fileId]);

    // Prompt View Logic
    const handleViewPrompt = (prompt: string) => {
        setCurrentPrompt(prompt);
        setShowPromptModal(true);
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

    // Save Note Handler
    const handleSaveNote = async (type: string, id: string, value: string): Promise<boolean> => {
        if (!project?.id) return false;
        try {
            let url = "";
            let method = "PUT";
            let body = { note: value };

            if (type === 'task') {
                url = `${API_BASE}/projects/${project.id}/tasks/${id}/note`;
            } else if (type === 'iteration') {
                url = `${API_BASE}/projects/${project.id}/iterations/${id}/note`;
            } else if (type === 'knowledge') {
                url = `${API_BASE}/projects/${project.id}/knowledge-base/${id}`;
            }

            const response = await fetch(url, {
                method,
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body)
            });

            if (response.ok) {
                if (onRefresh) onRefresh();
                return true;
            } else {
                return false;
            }
        } catch (err) {
            console.error("Save note error:", err);
            return false;
        }
    };

    return (
        <section className="glass rounded-2xl overflow-hidden h-[850px] flex flex-col relative">
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
                <button
                    onClick={() => setActiveTab("intent")}
                    className={`flex-1 py-4 text-sm font-medium transition-colors ${activeTab === "intent" ? "bg-white/5 text-indigo-400 border-b-2 border-indigo-500" : "text-slate-500 hover:text-slate-300"}`}
                >
                    意图干预
                </button>
            </div>

            <div className="flex-1 overflow-hidden flex flex-col relative">
                {/* 使用 CSS display 控制可见性，避免组件反复挂载卸载 */}
                <div className={`flex-1 overflow-hidden flex flex-col ${activeTab === "run" ? "" : "hidden"}`}>
                    <RunLogTab
                        taskId={taskStatus?.id}
                        projectId={project?.id}
                        totalCount={taskStatus?.total_count}
                        currentIndex={taskStatus?.current_index}
                        reasons={reasons}
                        saveReason={saveReason}
                        onSelectLog={onSelectLog}
                    />
                </div>

                <div className={`flex-1 overflow-hidden flex flex-col ${activeTab === "runHistory" ? "" : "hidden"}`}>
                    <RunHistoryTab
                        runHistory={runHistory}
                        projectId={project?.id || ""}
                        onDeleteTask={onDeleteTask}
                        onSaveNote={handleSaveNote}
                        onViewPrompt={handleViewPrompt}
                    />
                </div>

                <div className={`flex-1 overflow-hidden flex flex-col ${activeTab === "history" ? "" : "hidden"}`}>
                    <IterationHistoryTab
                        iterations={project?.iterations}
                        onSelectIteration={onSelectIteration}
                        onDeleteIteration={onDeleteIteration}
                        onSaveNote={handleSaveNote}
                    />
                </div>

                <div className={`flex-1 overflow-hidden flex flex-col ${activeTab === "knowledge" ? "" : "hidden"}`}>
                    <OptimizationAnalysisTab
                        records={knowledgeRecords}
                        onSelectRecord={onSelectKnowledge}
                        onDeleteRecord={onDeleteKnowledge}
                        onSaveNote={handleSaveNote}
                    />
                </div>

                <div className={`flex-1 overflow-hidden flex flex-col ${activeTab === "intent" ? "" : "hidden"}`}>
                    <IntentInterventionTab
                        project={project}
                        fileId={fileId}
                        saveReason={saveReason}
                        reasonsUpdateCount={reasonsUpdateCount}
                        onDataChange={onInterventionDataChange}
                    />
                </div>
            </div>

            {/* Prompt Detail Modal */}
            {showPromptModal && (
                <PromptModalContent prompt={currentPrompt} onClose={() => setShowPromptModal(false)} />
            )}
        </section>
    );
}

function PromptModalContent({ prompt, onClose }: { prompt: string, onClose: () => void }) {
    const modalRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (modalRef.current && !modalRef.current.contains(event.target as Node)) {
                onClose();
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [onClose]);

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
            <div ref={modalRef} className="bg-[#0f172a] border border-white/10 rounded-xl w-full max-w-4xl h-[600px] flex flex-col shadow-2xl">
                <div className="flex justify-between items-center p-4 border-b border-white/10 bg-white/5">
                    <h3 className="text-sm font-medium text-slate-200">提示词详情</h3>
                    <button onClick={onClose} className="text-slate-500 hover:text-white transition-colors">
                        <RotateCcw className="rotate-45" size={16} />
                    </button>
                </div>
                <div className="p-4 overflow-y-auto custom-scrollbar flex-1 bg-[#0f172a] flex flex-col">
                    <textarea
                        readOnly
                        className="w-full h-full bg-black/30 text-xs text-slate-300 font-mono leading-relaxed p-4 rounded-lg border border-white/5 resize-none focus:outline-none focus:border-blue-500/30"
                        value={prompt}
                    />
                </div>
                <div className="p-3 border-t border-white/10 bg-white/5 flex justify-end">
                    <button
                        onClick={() => {
                            navigator.clipboard.writeText(prompt);
                        }}
                        className="px-3 py-1.5 bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 text-xs rounded-lg transition-colors border border-blue-500/20"
                    >
                        复制内容
                    </button>
                </div>
            </div>
        </div>
    );
}
