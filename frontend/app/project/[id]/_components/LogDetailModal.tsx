import { motion, AnimatePresence } from "framer-motion";
import { CheckCircle2, AlertCircle, X, Edit3, Save, AlertTriangle, RotateCcw } from "lucide-react";
import { useEffect, useState } from "react";

interface LogDetailModalProps {
    selectedLog: any;
    onClose: () => void;
    onSaveReason?: (query: string, reason: string, target: string) => Promise<void>;
    onReset?: (query: string) => Promise<void>;
    projectId: string;
}

export default function LogDetailModal({ selectedLog, onClose, onSaveReason, onReset, projectId }: LogDetailModalProps) {
    const [isEditing, setIsEditing] = useState(false);
    const [reasonValue, setReasonValue] = useState("");
    const [savedReason, setSavedReason] = useState("");

    // targetValue stores the "Corrected Intent"
    const [targetValue, setTargetValue] = useState("");
    const [savedTarget, setSavedTarget] = useState("");

    const [availableTargets, setAvailableTargets] = useState<string[]>([]);
    const [showConfirmClose, setShowConfirmClose] = useState(false);
    const [isResetting, setIsResetting] = useState(false);

    /**
     * 重置当前记录的意图修正和原因
     */
    const handleReset = async () => {
        if (!onReset || !selectedLog?.query) return;
        if (!window.confirm("确定要重置此条记录吗？\n这将恢复原始预期意图并清空原因。")) return;

        setIsResetting(true);
        try {
            await onReset(selectedLog.query);
            // 重置成功后关闭 Modal
            onClose();
        } catch (e) {
            console.error("Reset failed:", e);
            alert("重置失败");
        } finally {
            setIsResetting(false);
        }
    };

    // Fetch available targets
    useEffect(() => {
        if (projectId && isEditing) {
            fetch(`/api/projects/${projectId}/interventions/targets`)
                .then(res => res.json())
                .then(data => {
                    if (Array.isArray(data)) {
                        setAvailableTargets(data);
                    } else {
                        setAvailableTargets([]);
                    }
                })
                .catch(err => {
                    console.error("Failed to fetch targets:", err);
                    setAvailableTargets([]);
                });
        }
    }, [projectId, isEditing]);

    useEffect(() => {
        if (selectedLog) {
            const initialReason = selectedLog.reason || "";
            setReasonValue(initialReason);
            setSavedReason(initialReason);

            // Initialize correction value
            // If we have an explicit intervention record, use its target as the correction
            // Otherwise, default to the log's target (assuming no correction yet)
            const intervention = selectedLog.intervention;
            const initialCorrection = intervention ? intervention.target : (selectedLog.target || "");

            setTargetValue(initialCorrection);
            setSavedTarget(initialCorrection);

            setIsEditing(false);
            setShowConfirmClose(false);
        }
    }, [selectedLog]);

    // Check if there are unsaved changes
    const hasUnsavedChanges = () => {
        return reasonValue !== savedReason || targetValue !== savedTarget;
    };

    const handleCloseRequest = () => {
        if (isEditing && hasUnsavedChanges()) {
            setShowConfirmClose(true);
        } else {
            onClose();
        }
    };

    const handleDiscardAndClose = () => {
        setIsEditing(false);
        setShowConfirmClose(false);
        onClose();
    };

    const handleSaveAndClose = async () => {
        await handleSave();
        onClose();
    };

    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === "Escape") {
                if (showConfirmClose) {
                    setShowConfirmClose(false);
                } else {
                    handleCloseRequest();
                }
            }
        };
        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [onClose, isEditing, reasonValue, savedReason, showConfirmClose]);

    const handleSave = async () => {
        if (onSaveReason) {
            // Save the "Intent Correction" (targetValue) as the new target
            await onSaveReason(selectedLog.query, reasonValue, targetValue);
            setSavedReason(reasonValue);
            setSavedTarget(targetValue);
            setIsEditing(false);
            setShowConfirmClose(false);
        }
    };

    if (!selectedLog) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
            {/* Backdrop */}
            <div
                className="absolute inset-0 bg-black/60 backdrop-blur-sm"
                onClick={handleCloseRequest}
            />

            <motion.div
                initial={{ scale: 0.9, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                onClick={(e) => e.stopPropagation()} // Prevent backdrop click
                className="relative glass w-full max-w-2xl p-6 rounded-3xl max-h-[80vh] overflow-y-auto custom-scrollbar z-10"
            >
                <div className="flex justify-between items-start mb-6">
                    <h2 className="text-xl font-bold flex items-center gap-2">
                        {selectedLog.is_correct ? <CheckCircle2 className="text-emerald-500" /> : <AlertCircle className="text-red-500" />}
                        Log Details #{selectedLog.index + 1}
                    </h2>
                    <button onClick={handleCloseRequest} className="p-2 hover:bg-white/10 rounded-full transition-colors">
                        <X size={20} />
                    </button>
                </div>

                <div className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-slate-400 mb-1">Query / Input</label>
                        <div className="bg-black/20 rounded-xl p-4 text-sm whitespace-pre-wrap text-slate-300">{selectedLog.query}</div>
                    </div>

                    {/* Original Target (Read-only) */}
                    <div>
                        <label className="block text-sm font-medium text-slate-400 mb-1">预期意图 (Original Target)</label>
                        <div className="bg-black/20 border border-white/5 rounded-xl p-4 text-sm text-slate-400 italic">
                            {selectedLog.target || "无预期结果"}
                        </div>
                    </div>

                    {/* Intent Correction (Editable) */}
                    <div>
                        <label className="block text-sm font-medium text-indigo-400 mb-1">意图修正 (Intent Correction)</label>
                        {isEditing ? (
                            <div>
                                <input
                                    list="target-options"
                                    className="w-full bg-black/20 border border-white/10 rounded-xl p-3 text-sm text-slate-300 focus:border-indigo-500/50 outline-none transition-colors"
                                    value={targetValue}
                                    onChange={(e) => setTargetValue(e.target.value)}
                                    placeholder="输入修正后的意图..."
                                />
                                <datalist id="target-options">
                                    {Array.isArray(availableTargets) && availableTargets.map((t, i) => (
                                        <option key={i} value={t} />
                                    ))}
                                </datalist>
                                <p className="text-xs text-slate-500 mt-1 ml-1">修改此处不会变更原始记录，但会影响后续优化的判断标准。</p>
                            </div>
                        ) : (
                            <div
                                className={`rounded-xl p-4 text-sm cursor-pointer hover:bg-white/5 transition-colors border ${savedTarget && savedTarget !== selectedLog.target
                                    ? "bg-indigo-500/10 border-indigo-500/30 text-indigo-300"
                                    : "bg-white/5 border-white/5 text-slate-500"
                                    }`}
                                onClick={() => onSaveReason && setIsEditing(true)}
                                title="点击修正意图"
                            >
                                {savedTarget && savedTarget !== selectedLog.target ? (
                                    <div className="flex items-center gap-2">
                                        <Edit3 size={14} />
                                        <span>{savedTarget} (已修正)</span>
                                    </div>
                                ) : (
                                    <span className="italic">暂无修正 (点击添加) - 当前使用原始意图</span>
                                )}
                            </div>
                        )}
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-slate-400 mb-1">Actual Output</label>
                        <pre className="bg-black/20 border border-white/10 rounded-xl p-4 text-sm overflow-x-auto font-mono text-slate-300">
                            {selectedLog.output}
                        </pre>
                    </div>

                    {/* Reason Section */}
                    <div className="pt-4 border-t border-white/10">
                        <div className="flex justify-between items-center mb-2">
                            <label className="block text-sm font-medium text-amber-500">标注原因 (Reason)</label>
                        </div>

                        {isEditing ? (
                            <div className="space-y-2">
                                <textarea
                                    className="w-full bg-black/20 border border-white/10 rounded-xl p-3 text-sm text-slate-300 focus:border-amber-500/50 outline-none resize-none"
                                    rows={3}
                                    value={reasonValue}
                                    onChange={(e) => setReasonValue(e.target.value)}
                                    placeholder="输入原因..."
                                    autoFocus
                                />
                                <div className="flex justify-end gap-2">
                                    <button
                                        onClick={() => {
                                            // Canceling edit resets value to SAVED reason
                                            setReasonValue(savedReason);
                                            setTargetValue(savedTarget);
                                            setIsEditing(false);
                                        }}
                                        className="px-3 py-1.5 text-xs text-slate-400 hover:bg-white/5 rounded-lg transition-colors"
                                    >
                                        取消
                                    </button>
                                    <button
                                        onClick={handleSave}
                                        className="px-3 py-1.5 text-xs bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg flex items-center gap-1 transition-colors"
                                    >
                                        <Save size={12} /> 保存
                                    </button>
                                </div>
                            </div>
                        ) : (
                            <div
                                className={`rounded-xl p-4 text-sm cursor-pointer hover:bg-white/5 transition-colors ${savedReason ? "bg-amber-500/5 border border-amber-500/10 text-slate-300" : "bg-white/5 border border-white/5 text-slate-500 italic"}`}
                                onClick={() => onSaveReason && setIsEditing(true)}
                            >
                                {savedReason || "暂无原因标注 (点击添加)"}
                            </div>
                        )}
                    </div>

                    {/* Reset Button - 显示在底部，仅当有修改时显示 */}
                    {onReset && (savedTarget !== selectedLog.target || savedReason) && !isEditing && (
                        <div className="pt-4 border-t border-white/10">
                            <button
                                onClick={handleReset}
                                disabled={isResetting}
                                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-sm text-red-400 hover:text-red-300 bg-red-500/10 hover:bg-red-500/20 rounded-xl border border-red-500/20 hover:border-red-500/30 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                <RotateCcw size={14} className={isResetting ? "animate-spin" : ""} />
                                重置此条记录（恢复原始意图，清空原因）
                            </button>
                        </div>
                    )}
                </div>
            </motion.div>

            {/* Unsaved Changes Confirm Modal */}
            <AnimatePresence>
                {showConfirmClose && (
                    <div className="absolute inset-0 z-20 flex items-center justify-center">
                        {/* Inner Backdrop */}
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="absolute inset-0 bg-black/50"
                            onClick={() => setShowConfirmClose(false)} // Click outside confirm -> Cancel
                        />
                        <motion.div
                            initial={{ scale: 0.95, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ scale: 0.95, opacity: 0 }}
                            className="bg-slate-800 border border-amber-500/30 rounded-2xl p-5 shadow-2xl max-w-sm w-full relative z-30"
                            onClick={e => e.stopPropagation()}
                        >
                            <div className="flex items-center gap-3 mb-4 text-amber-400">
                                <AlertTriangle size={24} />
                                <h3 className="font-bold text-lg">未保存的更改</h3>
                            </div>
                            <p className="text-slate-300 text-sm mb-6">
                                检测到您有未保存的内容，是否保存？
                            </p>
                            <div className="flex gap-2 justify-end">
                                <button
                                    onClick={handleDiscardAndClose}
                                    className="px-3 py-2 text-xs text-slate-400 hover:bg-white/5 rounded-lg transition-colors"
                                >
                                    直接退出
                                </button>
                                <button
                                    onClick={() => setShowConfirmClose(false)}
                                    className="px-3 py-2 text-xs text-white bg-slate-700 hover:bg-slate-600 rounded-lg transition-colors"
                                >
                                    取消
                                </button>
                                <button
                                    onClick={handleSaveAndClose}
                                    className="px-3 py-2 text-xs text-white bg-emerald-600 hover:bg-emerald-500 rounded-lg transition-colors"
                                >
                                    保存并退出
                                </button>
                            </div>
                        </motion.div>
                    </div>
                )}
            </AnimatePresence>
        </div>
    );
}
