import React, { useState, useEffect } from "react";
import { Edit3, Save, X } from "lucide-react";

interface NoteSectionProps {
    type: 'task' | 'iteration' | 'knowledge';
    id: string;
    initialNote?: string;
    // Callback to save note externally (API call)
    // It should handle optimistic updates or return success/fail
    onSave: (type: string, id: string, value: string) => Promise<boolean>;
}

export const NoteSection: React.FC<NoteSectionProps> = ({ type, id, initialNote = "", onSave }) => {
    const [isEditing, setIsEditing] = useState(false);
    const [noteValue, setNoteValue] = useState(initialNote);
    const [displayValue, setDisplayValue] = useState(initialNote);

    // Sync if prop changes externally
    useEffect(() => {
        setNoteValue(initialNote);
        setDisplayValue(initialNote);
    }, [initialNote]);

    const handleSave = async (e: React.MouseEvent) => {
        e.stopPropagation();
        const success = await onSave(type, id, noteValue);
        if (success) {
            setDisplayValue(noteValue);
            setIsEditing(false);
        }
    };

    const handleCancel = (e: React.MouseEvent) => {
        e.stopPropagation();
        setNoteValue(displayValue);
        setIsEditing(false);
    };

    const startEditing = (e: React.MouseEvent) => {
        e.stopPropagation();
        setIsEditing(true);
    };

    return (
        <div className="mt-2 pt-2 border-t border-white/5 cursor-pointer" onClick={startEditing}>
            {isEditing ? (
                <div className="flex gap-2 items-start">
                    <textarea
                        className="flex-1 bg-black/20 border border-white/10 rounded p-1 text-xs text-slate-300 focus:border-blue-500/50 outline-none resize-none"
                        rows={2}
                        value={noteValue}
                        onChange={(e) => setNoteValue(e.target.value)}
                        placeholder="添加备注..."
                        autoFocus
                        onClick={e => e.stopPropagation()}
                    />
                    <div className="flex flex-col gap-1">
                        <button
                            onClick={handleSave}
                            className="p-1 text-emerald-400 hover:bg-emerald-500/10 rounded"
                        >
                            <Save size={12} />
                        </button>
                        <button
                            onClick={handleCancel}
                            className="p-1 text-slate-400 hover:bg-slate-500/10 rounded"
                        >
                            <X size={12} />
                        </button>
                    </div>
                </div>
            ) : (
                <div
                    className="flex justify-between items-start group/note cursor-pointer hover:bg-white/5 rounded p-1 -m-1 transition-colors"
                    onClick={startEditing}
                >
                    <div className="flex-1 text-xs">
                        <span className="text-slate-500 mr-2 font-medium">备注:</span>
                        {displayValue ? (
                            <span className="text-slate-300">{displayValue}</span>
                        ) : (
                            <span className="text-slate-600 italic">无</span>
                        )}
                    </div>
                    <button
                        onClick={startEditing}
                        className={`p-1 text-slate-500 hover:text-blue-400 transition-colors ${!displayValue ? 'opacity-0 group-hover/note:opacity-100' : ''}`}
                        title="编辑备注"
                    >
                        <Edit3 size={12} />
                    </button>
                </div>
            )}
        </div>
    );
};
