import { useState } from "react";
import { ChevronLeft, Activity, Save, Settings, RotateCcw } from "lucide-react";
import Link from "next/link";

interface ProjectHeaderProps {
    projectName: string;
    onNameChange: (name: string) => void;
    isSaving: boolean;
    onSave: () => void;
    onOpenConfig: () => void;
    onTest: () => void;
    /** 重置项目回调 */
    onReset: () => void;
}

export default function ProjectHeader({
    projectName,
    onNameChange,
    isSaving,
    onSave,
    onOpenConfig,
    onTest,
    onReset
}: ProjectHeaderProps) {
    const [isEditingName, setIsEditingName] = useState(false);

    return (
        <div className="flex items-center justify-between mb-8">
            <div className="flex items-center gap-4">
                <Link href="/" className="p-2 hover:bg-white/10 rounded-full transition-colors">
                    <ChevronLeft size={24} />
                </Link>
                {isEditingName ? (
                    <input
                        autoFocus
                        value={projectName}
                        onChange={(e) => onNameChange(e.target.value)}
                        onBlur={() => setIsEditingName(false)}
                        onKeyDown={(e) => e.key === "Enter" && setIsEditingName(false)}
                        className="text-3xl font-bold bg-transparent border-b-2 border-blue-500 outline-none px-1"
                    />
                ) : (
                    <h1
                        className="text-3xl font-bold cursor-pointer hover:text-blue-400 transition-colors"
                        onClick={() => setIsEditingName(true)}
                        title="点击编辑项目名称"
                    >
                        {projectName}
                    </h1>
                )}
            </div>
            <div className="flex items-center gap-3">
                <button
                    onClick={onTest}
                    className="flex items-center gap-2 bg-purple-600/20 hover:bg-purple-600/30 text-purple-400 hover:text-purple-300 border border-purple-500/30 px-4 py-2 rounded-xl transition-colors text-sm font-medium"
                >
                    <Activity size={18} />
                    测试 Prompt
                </button>
                <button
                    onClick={onSave}
                    disabled={isSaving}
                    className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 px-4 py-2 rounded-xl transition-colors text-sm font-medium"
                >
                    <span className="w-[18px] h-[18px] relative">
                        <Save size={18} className={`absolute inset-0 transition-opacity ${isSaving ? 'opacity-0' : 'opacity-100'}`} />
                        <Activity size={18} className={`absolute inset-0 animate-spin transition-opacity ${isSaving ? 'opacity-100' : 'opacity-0'}`} />
                    </span>
                    保存项目
                </button>
                <button
                    onClick={onOpenConfig}
                    className="flex items-center gap-2 bg-white/5 hover:bg-white/10 border border-white/10 px-4 py-2 rounded-xl transition-colors text-sm"
                >
                    <Settings size={18} />
                    项目配置
                </button>
                <button
                    onClick={onReset}
                    className="flex items-center gap-2 bg-orange-600/20 hover:bg-orange-600/30 text-orange-400 hover:text-orange-300 border border-orange-500/30 px-4 py-2 rounded-xl transition-colors text-sm"
                    title="重置项目到初始状态"
                >
                    <RotateCcw size={18} />
                    重置
                </button>
            </div>
        </div>
    );
}
