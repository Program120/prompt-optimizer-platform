import { TrendingUp, Trash2, Clock } from "lucide-react";
import { NoteSection } from "./NoteSection";

interface IterationHistoryTabProps {
    iterations?: any[];
    onSelectIteration: (iteration: any) => void;
    onDeleteIteration?: (iteration: any) => void;
    onSaveNote: (type: string, id: string, value: string) => Promise<boolean>;
}

export default function IterationHistoryTab({ iterations, onSelectIteration, onDeleteIteration, onSaveNote }: IterationHistoryTabProps) {
    const formatTime = (timestamp: string) => {
        if (!timestamp) return "未知";
        try {
            const ts = parseInt(timestamp) * 1000;
            return new Date(ts).toLocaleString();
        } catch {
            return "未知";
        }
    };

    return (
        <div className="flex-1 overflow-y-auto p-4 custom-scrollbar space-y-3">
            {iterations?.map((iter: any) => (
                <div
                    key={iter.id}
                    className="p-3 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 transition-colors cursor-pointer group"
                    onClick={() => onSelectIteration(iter)}
                >
                    <div className="flex justify-between items-center mb-2">
                        <div className="flex items-center gap-2">
                            <span className="text-emerald-400 font-bold text-sm">V{iter.version}</span>
                            <div className="flex items-center gap-1 text-[10px] bg-emerald-500/10 text-emerald-400 px-1.5 py-0.5 rounded">
                                <TrendingUp size={10} />
                                <span>+{((iter.score || 0) * 100).toFixed(1)}%</span>
                            </div>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-xs text-slate-500">{formatTime(iter.created_at)}</span>
                            {onDeleteIteration && (
                                <button
                                    onClick={(e) => { e.stopPropagation(); onDeleteIteration(iter); }}
                                    className="opacity-0 group-hover:opacity-100 p-1 text-slate-500 hover:text-red-400 transition-all"
                                >
                                    <Trash2 size={12} />
                                </button>
                            )}
                        </div>
                    </div>
                    <div className="bg-black/20 p-2 rounded text-xs text-slate-300 font-mono mb-2 line-clamp-2">
                        {iter.prompt_content}
                    </div>

                    <NoteSection
                        type="iteration"
                        id={iter.id}
                        initialNote={iter.note}
                        onSave={onSaveNote}
                    />
                </div>
            ))}
            {!iterations?.length && <p className="text-center text-slate-600 mt-20">暂无迭代历史</p>}
        </div>
    );
}
