import { useState } from "react";
import { CheckCircle2, AlertCircle, ArrowRight } from "lucide-react";

interface HistoryPanelProps {
    taskStatus: any;
    project: any;
    onSelectLog: (log: any) => void;
    onSelectIteration: (iteration: any) => void;
}

export default function HistoryPanel({ taskStatus, project, onSelectLog, onSelectIteration }: HistoryPanelProps) {
    const [activeTab, setActiveTab] = useState("run"); // run, history

    return (
        <section className="glass rounded-2xl overflow-hidden h-[600px] flex flex-col">
            <div className="flex border-b border-white/10">
                <button
                    onClick={() => setActiveTab("run")}
                    className={`flex-1 py-4 text-sm font-medium transition-colors ${activeTab === "run" ? "bg-white/5 text-blue-400 border-b-2 border-blue-500" : "text-slate-500 hover:text-slate-300"}`}
                >
                    运行日志
                </button>
                <button
                    onClick={() => setActiveTab("history")}
                    className={`flex-1 py-4 text-sm font-medium transition-colors ${activeTab === "history" ? "bg-white/5 text-blue-400 border-b-2 border-blue-500" : "text-slate-500 hover:text-slate-300"}`}
                >
                    迭代历史
                </button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
                {activeTab === "run" ? (
                    <>
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
                ) : (
                    <div className="space-y-4">
                        {project.iterations?.slice().reverse().map((it: any, idx: number) => (
                            <div
                                key={idx}
                                onClick={() => onSelectIteration(it)}
                                className="relative pl-6 before:absolute before:left-0 before:top-2 before:bottom-0 before:w-[2px] before:bg-blue-500/30 cursor-pointer hover:opacity-80 transition-opacity"
                            >
                                <div className="absolute left-[-4px] top-2 w-2 h-2 rounded-full bg-blue-500" />
                                <div className="flex justify-between items-center mb-2">
                                    <span className="text-sm font-bold">迭代 #{project.iterations.length - idx}</span>
                                    <span className="text-[10px] text-slate-600">{new Date(it.created_at).toLocaleString()}</span>
                                </div>
                                <div className="text-xs bg-white/5 rounded-lg p-3 border border-white/5 hover:bg-white/10 transition-colors">
                                    <div className="text-emerald-400 font-bold mb-1">准确率: {(it.accuracy * 100).toFixed(1)}%</div>
                                    <p className="text-slate-500 line-clamp-3 italic">"{it.new_prompt}"</p>
                                </div>
                            </div>
                        ))}
                        {!project.iterations?.length && <p className="text-center text-slate-600 mt-20">暂无优化历史</p>}
                    </div>
                )}
            </div>
        </section>
    );
}
