import { motion } from "framer-motion";
import { History, X } from "lucide-react";
import * as Diff from "diff";
import { useEffect, useState } from "react";

interface IterationDetailModalProps {
    selectedIteration: any;
    onClose: () => void;
    onApply: (newPrompt: string, message?: string) => void;
}

export default function IterationDetailModal({ selectedIteration, onClose, onApply }: IterationDetailModalProps) {
    const [diffResult, setDiffResult] = useState<any[]>([]);
    const [isDiffing, setIsDiffing] = useState(false);
    const [showFullDiff, setShowFullDiff] = useState(false);
    const TRUNCATE_LENGTH = 5000;



    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === "Escape") {
                onClose();
            }
        };
        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [onClose]);

    useEffect(() => {
        if (!selectedIteration) return;

        // Reset full diff state when iteration changes
        setShowFullDiff(false);
    }, [selectedIteration]);

    useEffect(() => {
        if (!selectedIteration) return;

        const calculateDiff = async () => {
            setIsDiffing(true);
            // Allow UI to render loading state
            await new Promise(resolve => setTimeout(resolve, 10));

            const oldP = selectedIteration.old_prompt || "";
            const newP = selectedIteration.new_prompt || "";

            let oldToDiff = oldP;
            let newToDiff = newP;
            const isLarge = oldP.length > TRUNCATE_LENGTH || newP.length > TRUNCATE_LENGTH;

            if (isLarge && !showFullDiff) {
                oldToDiff = oldP.slice(0, TRUNCATE_LENGTH) + "...";
                newToDiff = newP.slice(0, TRUNCATE_LENGTH) + "...";
            }

            try {
                const result = Diff.diffWords(oldToDiff, newToDiff);
                setDiffResult(result);
            } catch (e) {
                console.error("Diff calculation failed", e);
                setDiffResult([{ value: "Diff calculation failed due to size.", removed: false, added: false }]);
            } finally {
                setIsDiffing(false);
            }
        };

        calculateDiff();
    }, [selectedIteration, showFullDiff]);

    if (!selectedIteration) return null;

    const isLargeContent = (selectedIteration.old_prompt || "").length > TRUNCATE_LENGTH || (selectedIteration.new_prompt || "").length > TRUNCATE_LENGTH;

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
                        <div className="flex justify-between items-center mb-2">
                            <label className="block text-sm font-medium text-slate-400">提示词变更对比</label>
                            {isLargeContent && !showFullDiff && !isDiffing && (
                                <button
                                    onClick={() => setShowFullDiff(true)}
                                    className="text-xs bg-yellow-500/10 text-yellow-400 px-2 py-1 rounded hover:bg-yellow-500/20 transition-colors"
                                >
                                    显示完整对比 (可能较慢)
                                </button>
                            )}
                        </div>

                        <div className="bg-black/30 rounded-xl p-4 font-mono text-sm overflow-x-auto border border-white/10 whitespace-pre-wrap max-h-[300px] overflow-y-auto custom-scrollbar relative min-h-[100px]">
                            {isDiffing ? (
                                <div className="absolute inset-0 flex items-center justify-center">
                                    <div className="flex flex-col items-center gap-2">
                                        <div className="w-6 h-6 border-2 border-blue-400 border-t-transparent rounded-full animate-spin"></div>
                                        <span className="text-slate-400 text-xs">正在计算差异...</span>
                                    </div>
                                </div>
                            ) : (
                                <>
                                    {diffResult.map((part: any, i: number) => (
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
                                    {isLargeContent && !showFullDiff && (
                                        <div className="block mt-4 text-center text-slate-500 text-xs italic bg-white/5 p-2 rounded">
                                            ⚠️ 内容过长，已截断显示。点击上方按钮查看完整对比。
                                        </div>
                                    )}
                                </>
                            )}
                        </div>
                    </div>

                    {/* Side by side */}
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-medium text-red-400 mb-2">旧提示词</label>
                            <div className="bg-red-500/5 border border-red-500/20 rounded-xl p-4 text-sm whitespace-pre-wrap max-h-48 overflow-y-auto custom-scrollbar">
                                {selectedIteration.old_prompt || "(无)"}
                            </div>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-emerald-400 mb-2">新提示词</label>
                            <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-xl p-4 text-sm whitespace-pre-wrap max-h-48 overflow-y-auto custom-scrollbar">
                                {selectedIteration.new_prompt || "(无)"}
                            </div>
                        </div>
                    </div>

                    {/* Action buttons */}
                    <div className="flex gap-4">
                        <button
                            onClick={() => {
                                onApply(selectedIteration.old_prompt, "提示词已回退");
                                onClose();
                            }}
                            className="flex-1 bg-red-500/10 hover:bg-red-500/20 border border-red-500/50 text-red-400 py-3 rounded-xl font-medium transition-colors"
                        >
                            回退提示词 (应用旧版本)
                        </button>
                        <button
                            onClick={() => {
                                onApply(selectedIteration.new_prompt, "此版本提示词已应用");
                                onClose();
                            }}
                            className="flex-1 bg-blue-600 hover:bg-blue-500 py-3 rounded-xl font-medium transition-colors text-white"
                        >
                            应用此版本提示词
                        </button>
                    </div>
                </div>
            </motion.div>
        </div>
    );
}
