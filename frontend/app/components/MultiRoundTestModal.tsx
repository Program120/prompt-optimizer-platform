/**
 * 多轮测试结果弹窗组件
 */
import { motion } from "framer-motion";
import { CheckCircle2, AlertCircle, X, Clock, ChevronDown, ChevronUp, Copy, Check } from "lucide-react";
import { useState, useEffect } from "react";
import { createPortal } from "react-dom";

interface TestRoundResult {
    round: number;
    query: string;
    target: string;
    output: string;
    extracted_intent?: string;
    extracted_response?: string;
    is_correct: boolean;
    latency_ms: number;
    request_params?: Record<string, unknown>;
}

interface MultiRoundTestModalProps {
    results: TestRoundResult[];
    accuracy: number;
    rowIndex: number;
    onClose: () => void;
}

export default function MultiRoundTestModal({ results, accuracy, rowIndex, onClose }: MultiRoundTestModalProps) {
    const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(["extracted-1"]));
    const [copiedField, setCopiedField] = useState<string | null>(null);

    // 防止滚动穿透
    useEffect(() => {
        document.body.style.overflow = "hidden";
        return () => {
            document.body.style.overflow = "";
        };
    }, []);

    const toggleSection = (section: string) => {
        const newExpanded = new Set(expandedSections);
        if (newExpanded.has(section)) {
            newExpanded.delete(section);
        } else {
            newExpanded.add(section);
        }
        setExpandedSections(newExpanded);
    };

    const handleCopy = async (text: string, field: string) => {
        try {
            await navigator.clipboard.writeText(text);
            setCopiedField(field);
            setTimeout(() => setCopiedField(null), 2000);
        } catch (err) {
            console.error("Copy failed:", err);
        }
    };

    const correctCount = results.filter(r => r.is_correct).length;

    const modalContent = (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4">
            <div
                className="absolute inset-0 bg-black/60 backdrop-blur-sm"
                onClick={onClose}
            />

            <motion.div
                initial={{ scale: 0.9, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                onClick={(e) => e.stopPropagation()}
                className="relative bg-slate-900 border border-slate-700 w-full max-w-3xl rounded-2xl z-10 max-h-[85vh] overflow-hidden flex flex-col"
            >
                {/* 头部 - 固定 */}
                <div className="flex justify-between items-start p-6 pb-4 border-b border-slate-700">
                    <div>
                        <h2 className="text-xl font-bold flex items-center gap-2">
                            {accuracy === 100 ? (
                                <CheckCircle2 className="text-emerald-500" />
                            ) : (
                                <AlertCircle className="text-red-500" />
                            )}
                            测试结果 #{rowIndex}
                        </h2>
                        <p className="text-sm text-slate-400 mt-1">
                            {correctCount}/{results.length} 轮正确 · 准确率 {accuracy}%
                        </p>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-white/10 rounded-full transition-colors">
                        <X size={20} />
                    </button>
                </div>

                {/* 内容区域 - 可滚动 */}
                <div className="flex-1 overflow-y-auto p-6 pt-4 pb-8 space-y-4">
                    {results.map((result) => (
                        <div
                            key={result.round}
                            className={`rounded-xl border overflow-hidden ${
                                result.is_correct
                                    ? "bg-emerald-500/5 border-emerald-500/20"
                                    : "bg-red-500/5 border-red-500/20"
                            }`}
                        >
                            {/* 轮次头部 */}
                            <div className="flex items-center justify-between p-4 border-b border-white/5">
                                <div className="flex items-center gap-3">
                                    {result.is_correct ? (
                                        <CheckCircle2 size={20} className="text-emerald-400" />
                                    ) : (
                                        <AlertCircle size={20} className="text-red-400" />
                                    )}
                                    <span className="font-medium">第 {result.round} 轮</span>
                                    <span className={`text-sm ${result.is_correct ? "text-emerald-400" : "text-red-400"}`}>
                                        {result.is_correct ? "通过" : "不通过"}
                                    </span>
                                </div>
                                <div className="flex items-center gap-2 text-sm text-slate-400">
                                    <Clock size={14} />
                                    {result.latency_ms}ms
                                </div>
                            </div>

                            <div className="p-4 space-y-4">
                                {/* Query */}
                                <div>
                                    <label className="block text-xs font-medium text-slate-500 mb-1">Query / Input</label>
                                    <div className="bg-black/20 rounded-lg p-3 text-sm text-slate-300">
                                        {result.query}
                                    </div>
                                </div>

                                {/* 抽取结果 */}
                                <div className="bg-slate-800/50 rounded-lg border border-white/5 overflow-hidden">
                                    <button
                                        onClick={() => toggleSection(`extracted-${result.round}`)}
                                        className="w-full flex items-center justify-between p-3 hover:bg-white/5 transition-colors"
                                    >
                                        <span className="text-xs font-medium text-cyan-400">抽取结果</span>
                                        {expandedSections.has(`extracted-${result.round}`) ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                                    </button>
                                    {expandedSections.has(`extracted-${result.round}`) && (
                                        <div className="p-3 pt-0 space-y-3 border-t border-white/5">
                                            <div>
                                                <label className="block text-[10px] text-slate-500 mb-1">抽取的意图 (Extracted Intent)</label>
                                                <div className={`bg-black/20 rounded px-2 py-1.5 text-xs font-mono ${result.is_correct ? "text-emerald-400" : "text-red-400"}`}>
                                                    {result.extracted_intent || "N/A"}
                                                </div>
                                            </div>
                                            <div>
                                                <label className="block text-[10px] text-slate-500 mb-1">抽取的回复内容 (Extracted Response)</label>
                                                <div className="bg-black/20 rounded px-2 py-1.5 text-xs text-slate-300 max-h-20 overflow-y-auto">
                                                    {result.extracted_response || "N/A"}
                                                </div>
                                            </div>
                                        </div>
                                    )}
                                </div>

                                {/* 预期意图 */}
                                <div>
                                    <label className="block text-xs font-medium text-slate-500 mb-1">预期意图 (Target)</label>
                                    <div className="bg-black/20 rounded-lg p-3 text-sm text-emerald-400">
                                        {result.target || "N/A"}
                                    </div>
                                </div>

                                {/* 完整入参 */}
                                <div className="bg-slate-800/50 rounded-lg border border-white/5 overflow-hidden">
                                    <button
                                        onClick={() => toggleSection(`request-${result.round}`)}
                                        className="w-full flex items-center justify-between p-3 hover:bg-white/5 transition-colors"
                                    >
                                        <span className="text-xs font-medium text-amber-400">完整入参 (Request Params)</span>
                                        <div className="flex items-center gap-2">
                                            {result.request_params && (
                                                <button
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        handleCopy(JSON.stringify(result.request_params, null, 2), `request-${result.round}`);
                                                    }}
                                                    className="p-1 hover:bg-white/10 rounded transition-colors"
                                                    title="复制"
                                                >
                                                    {copiedField === `request-${result.round}` ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                                                </button>
                                            )}
                                            {expandedSections.has(`request-${result.round}`) ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                                        </div>
                                    </button>
                                    {expandedSections.has(`request-${result.round}`) && (
                                        <div className="p-3 pt-0 border-t border-white/5">
                                            {result.request_params ? (
                                                <pre className="text-xs font-mono text-slate-300 overflow-x-auto max-h-[150px] overflow-y-auto">
                                                    {JSON.stringify(result.request_params, null, 2)}
                                                </pre>
                                            ) : (
                                                <div className="text-xs text-slate-500 italic">无入参数据</div>
                                            )}
                                        </div>
                                    )}
                                </div>

                                {/* 完整出参 */}
                                <div className="bg-slate-800/50 rounded-lg border border-white/5 overflow-hidden">
                                    <button
                                        onClick={() => toggleSection(`output-${result.round}`)}
                                        className="w-full flex items-center justify-between p-3 hover:bg-white/5 transition-colors"
                                    >
                                        <span className="text-xs font-medium text-purple-400">完整出参 (Raw Output)</span>
                                        <div className="flex items-center gap-2">
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleCopy(result.output || "", `output-${result.round}`);
                                                }}
                                                className="p-1 hover:bg-white/10 rounded transition-colors"
                                                title="复制"
                                            >
                                                {copiedField === `output-${result.round}` ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                                            </button>
                                            {expandedSections.has(`output-${result.round}`) ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                                        </div>
                                    </button>
                                    {expandedSections.has(`output-${result.round}`) && (
                                        <pre className="p-3 pt-0 text-xs font-mono text-slate-300 overflow-x-auto max-h-[150px] overflow-y-auto border-t border-white/5">
                                            {result.output || "N/A"}
                                        </pre>
                                    )}
                                </div>
                            </div>
                        </div>
                    ))}
                </div>

                {/* 底部关闭按钮 - 固定 */}
                <div className="p-4 border-t border-slate-700 flex justify-end">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm transition-colors"
                    >
                        关闭
                    </button>
                </div>
            </motion.div>
        </div>
    );

    // 使用 Portal 渲染到 body，确保弹窗覆盖整个页面
    if (typeof window !== "undefined") {
        return createPortal(modalContent, document.body);
    }
    return modalContent;
}
