import { motion } from "framer-motion";
import { History, X } from "lucide-react";
import * as Diff from "diff";
import { useEffect } from "react";

interface IterationDetailModalProps {
    selectedIteration: any;
    onClose: () => void;
    onApply: (newPrompt: string) => void;
}

export default function IterationDetailModal({ selectedIteration, onClose, onApply }: IterationDetailModalProps) {
    if (!selectedIteration) return null;

    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === "Escape") {
                onClose();
            }
        };
        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [onClose]);

    return (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
            <motion.div
                initial={{ scale: 0.9, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                className="glass w-full max-w-4xl p-6 rounded-3xl max-h-[85vh] overflow-y-auto"
            >
                <div className="flex justify-between items-start mb-6">
                    <div>
                        <h2 className="text-xl font-bold flex items-center gap-2">
                            <History className="text-blue-400" />
                            迭代详情
                        </h2>
                        <div className="flex gap-4 mt-2 text-sm text-slate-400">
                            <span>准确率: <span className="text-emerald-400 font-bold">{(selectedIteration.accuracy * 100).toFixed(1)}%</span></span>
                            <span>时间: {new Date(selectedIteration.created_at).toLocaleString()}</span>
                        </div>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-white/10 rounded-full transition-colors">
                        <X size={20} />
                    </button>
                </div>

                <div className="space-y-6">
                    {/* Diff View */}
                    <div>
                        <label className="block text-sm font-medium text-slate-400 mb-2">提示词变更对比</label>
                        <div className="bg-black/30 rounded-xl p-4 font-mono text-sm overflow-x-auto border border-white/10 whitespace-pre-wrap">
                            {Diff.diffWords(selectedIteration.old_prompt || "", selectedIteration.new_prompt || "").map((part: any, i: number) => (
                                <span
                                    key={i}
                                    className={
                                        part.added ? "bg-emerald-500/30 text-emerald-300" :
                                            part.removed ? "bg-red-500/30 text-red-300 line-through" :
                                                "text-slate-300"
                                    }
                                >
                                    {part.value}
                                </span>
                            ))}
                        </div>
                    </div>

                    {/* Side by side */}
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-medium text-red-400 mb-2">旧提示词</label>
                            <div className="bg-red-500/5 border border-red-500/20 rounded-xl p-4 text-sm whitespace-pre-wrap max-h-48 overflow-y-auto">
                                {selectedIteration.old_prompt || "(无)"}
                            </div>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-emerald-400 mb-2">新提示词</label>
                            <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-xl p-4 text-sm whitespace-pre-wrap max-h-48 overflow-y-auto">
                                {selectedIteration.new_prompt || "(无)"}
                            </div>
                        </div>
                    </div>

                    {/* Apply button */}
                    <button
                        onClick={() => {
                            onApply(selectedIteration.new_prompt);
                            onClose();
                        }}
                        className="w-full bg-blue-600 hover:bg-blue-500 py-3 rounded-xl font-medium transition-colors"
                    >
                        应用此版本提示词
                    </button>
                </div>
            </motion.div>
        </div>
    );
}
