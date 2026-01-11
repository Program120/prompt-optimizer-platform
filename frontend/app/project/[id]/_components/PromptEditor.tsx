import { FileText } from "lucide-react";

interface PromptEditorProps {
    currentPrompt: string;
    onPromptChange: (value: string) => void;
    isAutoIterating: boolean;
}

export default function PromptEditor({ currentPrompt, onPromptChange, isAutoIterating }: PromptEditorProps) {
    return (
        <section className="glass p-6 rounded-2xl">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <FileText size={20} className="text-blue-400" />
                当前提示词
            </h2>
            <textarea
                value={currentPrompt}
                onChange={(e) => onPromptChange(e.target.value)}
                disabled={isAutoIterating}
                placeholder={isAutoIterating ? "自动迭代优化中，请稍候..." : "输入系统提示词..."}
                className={`w-full h-48 bg-black/20 border border-white/10 rounded-xl p-4 font-mono text-sm focus:outline-none focus:border-blue-500 transition-colors ${isAutoIterating ? "opacity-50 cursor-not-allowed" : ""}`}
            />
        </section>
    );
}
