import { motion } from "framer-motion";
import { CheckCircle2, AlertCircle, X } from "lucide-react";

interface LogDetailModalProps {
    selectedLog: any;
    onClose: () => void;
}

export default function LogDetailModal({ selectedLog, onClose }: LogDetailModalProps) {
    if (!selectedLog) return null;

    return (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
            <motion.div
                initial={{ scale: 0.9, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                className="glass w-full max-w-2xl p-6 rounded-3xl max-h-[80vh] overflow-y-auto"
            >
                <div className="flex justify-between items-start mb-6">
                    <h2 className="text-xl font-bold flex items-center gap-2">
                        {selectedLog.is_correct ? <CheckCircle2 className="text-emerald-500" /> : <AlertCircle className="text-red-500" />}
                        Log Details #{selectedLog.index + 1}
                    </h2>
                    <button onClick={onClose} className="p-2 hover:bg-white/10 rounded-full transition-colors">
                        <X size={20} />
                    </button>
                </div>

                <div className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-slate-400 mb-1">Query / Input</label>
                        <div className="bg-black/20 rounded-xl p-4 text-sm whitespace-pre-wrap">{selectedLog.query}</div>
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-slate-400 mb-1">Expected Target</label>
                        <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-xl p-4 text-sm">{selectedLog.target}</div>
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-slate-400 mb-1">Actual Output</label>
                        <pre className="bg-black/20 border border-white/10 rounded-xl p-4 text-sm overflow-x-auto font-mono text-slate-300">
                            {selectedLog.output}
                        </pre>
                    </div>
                </div>
            </motion.div>
        </div>
    );
}
