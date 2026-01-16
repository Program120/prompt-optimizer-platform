import { Layers, Trash2 } from "lucide-react";
import { NoteSection } from "./NoteSection";

interface KnowledgeTabProps {
    records?: any[];
    onSelectKnowledge?: (record: any) => void;
    onDeleteKnowledge?: (record: any) => void;
    onSaveNote: (type: string, id: string, value: string) => Promise<boolean>;
}

export default function KnowledgeTab({ records, onSelectKnowledge, onDeleteKnowledge, onSaveNote }: KnowledgeTabProps) {
    return (
        <div className="flex-1 overflow-y-auto p-4 custom-scrollbar space-y-3">
            {records?.map((record: any) => (
                <div
                    key={record.id}
                    className="p-3 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 transition-colors cursor-pointer group"
                    onClick={() => onSelectKnowledge && onSelectKnowledge(record)}
                >
                    <div className="flex justify-between items-start mb-2">
                        <div>
                            <div className="text-sm text-purple-200 font-medium mb-1">
                                {record.strategy_name || `Optimization V${record.version}`}
                            </div>
                            <div className="text-xs text-slate-500">
                                Version {record.version}
                            </div>
                        </div>
                        {onDeleteKnowledge && (
                            <button
                                onClick={(e) => { e.stopPropagation(); onDeleteKnowledge(record); }}
                                className="opacity-0 group-hover:opacity-100 p-1 text-slate-500 hover:text-red-400 transition-all"
                            >
                                <Trash2 size={12} />
                            </button>
                        )}
                    </div>

                    <p className="text-[11px] text-slate-400 line-clamp-2">
                        {record.analysis_summary || "暂无优化总结"}
                    </p>

                    <NoteSection
                        type="knowledge"
                        id={record.id}
                        initialNote={record.note}
                        onSave={onSaveNote}
                    />
                </div>
            ))}
            {!records?.length && (
                <div className="text-center mt-20">
                    <Layers size={32} className="mx-auto text-slate-600 mb-2" />
                    <p className="text-slate-600 text-sm">暂无优化分析记录</p>
                    <p className="text-slate-700 text-xs mt-1">完成优化后将自动记录分析历史</p>
                </div>
            )}
        </div>
    );
}
