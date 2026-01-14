import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Play, Clock, Cpu, ChevronDown } from "lucide-react";
import axios from "axios";

interface TestOutputModalProps {
    onClose: () => void;
    initialPrompt?: string;
    initialModelConfig?: any;
}

export default function TestOutputModal({ onClose, initialPrompt = "", initialModelConfig }: TestOutputModalProps) {
    const [prompt, setPrompt] = useState(initialPrompt);
    const [query, setQuery] = useState("");
    const [output, setOutput] = useState("");
    const [latency, setLatency] = useState<number | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    const [globalModels, setGlobalModels] = useState<any[]>([]);
    const [selectedModelId, setSelectedModelId] = useState<string>("");

    // 如果传入了 initialModelConfig，则使用它，否则使用选择的全局模型
    // 但这里为了灵活性，我们需要决定 priorit
    // 简单起见：如果传入了 config, 我们默认视为 "Custom (Project Settings)"，但也允许用户切换到 Global Models
    const [useCustomConfig, setUseCustomConfig] = useState(!!initialModelConfig);

    useEffect(() => {
        // 锁定背景滚动 (滚轮穿透问题)
        document.body.style.overflow = "hidden";
        return () => {
            document.body.style.overflow = "unset";
        };
    }, []);

    useEffect(() => {
        // 获取全局模型列表
        axios.get("/api/global-models")
            .then(res => {
                setGlobalModels(res.data || []);
                if (res.data && res.data.length > 0 && !initialModelConfig) {
                    setSelectedModelId(res.data[0].id);
                }
            })
            .catch(console.error);
    }, [initialModelConfig]);

    const handleRun = async () => {
        if (!query.trim()) {
            setError("请输入测试 Query");
            return;
        }

        let modelConfig = null;

        if (useCustomConfig && initialModelConfig) {
            modelConfig = initialModelConfig;
        } else {
            const selected = globalModels.find(m => m.id === selectedModelId);
            if (!selected) {
                setError("请选择一个模型配置");
                return;
            }
            modelConfig = selected;
        }

        // 简单校验
        if (!modelConfig.api_key && !modelConfig.base_url) { // 有些可能是本地模型不需要 key，但一般都有 url
            // 这里不做过强校验，交给后端
        }

        setLoading(true);
        setError("");
        setOutput("");
        setLatency(null);

        try {
            const res = await axios.post("/api/playground/test", {
                prompt,
                query,
                model_config: modelConfig
            });

            setOutput(res.data.output);
            setLatency(res.data.latency_ms);
        } catch (e: any) {
            console.error(e);
            setError(e.response?.data?.detail || "请求失败");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-[100]">
            {/* 点击背景关闭 */}
            <div className="absolute inset-0" onClick={onClose} />

            <motion.div
                initial={{ scale: 0.9, opacity: 0, y: 20 }}
                animate={{ scale: 1, opacity: 1, y: 0 }}
                exit={{ scale: 0.9, opacity: 0, y: 20 }}
                className="glass w-full max-w-4xl p-6 rounded-3xl max-h-[90vh] flex flex-col relative z-10"
                onClick={e => e.stopPropagation()} // 防止点击内容关闭
            >
                <div className="flex justify-between items-center mb-6">
                    <h2 className="text-xl font-bold flex items-center gap-2 bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-400">
                        <Cpu size={24} className="text-blue-400" />
                        模型输出测试 (Playground)
                    </h2>
                    <button onClick={onClose} className="p-2 hover:bg-white/10 rounded-full transition-colors text-slate-400 hover:text-white">
                        <X size={20} />
                    </button>
                </div>

                <div className="flex-1 overflow-y-auto space-y-6 min-h-0 pr-2 custom-scrollbar">
                    {/* Model Selection */}
                    <div className="bg-white/5 rounded-xl p-4 border border-white/10">
                        <div className="flex justify-between items-center mb-2">
                            <label className="text-sm font-medium text-slate-400">调用模型配置</label>
                            {initialModelConfig && (
                                <div className="text-xs flex gap-2">
                                    <button
                                        onClick={() => setUseCustomConfig(true)}
                                        className={`px-3 py-1 rounded-lg transition-colors border ${useCustomConfig ? "bg-blue-600 border-blue-500 text-white" : "bg-transparent border-white/10 text-slate-400 hover:text-white"}`}
                                    >
                                        使用项目当前配置
                                    </button>
                                    <button
                                        onClick={() => setUseCustomConfig(false)}
                                        className={`px-3 py-1 rounded-lg transition-colors border ${!useCustomConfig ? "bg-blue-600 border-blue-500 text-white" : "bg-transparent border-white/10 text-slate-400 hover:text-white"}`}
                                    >
                                        选择公共模型
                                    </button>
                                </div>
                            )}
                        </div>

                        {!useCustomConfig ? (
                            <div className="relative">
                                <select
                                    value={selectedModelId}
                                    onChange={(e) => setSelectedModelId(e.target.value)}
                                    className="w-full bg-black/20 border border-white/10 rounded-xl px-4 py-3 appearance-none focus:outline-none focus:border-blue-500 transition-colors text-white"
                                >
                                    <option value="" disabled>选择模型...</option>
                                    {globalModels.map(m => (
                                        <option key={m.id} value={m.id}>
                                            {m.name} ({m.model_name})
                                        </option>
                                    ))}
                                </select>
                                <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" size={16} />
                            </div>
                        ) : (
                            <div className="text-sm text-emerald-400 flex items-center gap-2 bg-emerald-500/10 px-4 py-3 rounded-xl border border-emerald-500/20">
                                <Clock size={14} />
                                当前使用的是项目的【验证模型】配置
                            </div>
                        )}
                    </div>

                    {/* Prompt Input */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 h-[400px]">
                        <div className="flex flex-col h-full">
                            <label className="block text-sm font-medium text-slate-400 mb-2">System Prompt (提示词)</label>
                            <textarea
                                value={prompt}
                                onChange={e => setPrompt(e.target.value)}
                                className="flex-1 w-full bg-white/5 border border-white/10 rounded-xl p-4 focus:outline-none focus:border-blue-500 transition-colors resize-none font-mono text-sm leading-relaxed"
                                placeholder="输入系统提示词..."
                            />
                        </div>
                        <div className="flex flex-col h-full space-y-4">
                            <div className="flex-none">
                                <label className="block text-sm font-medium text-slate-400 mb-2">User Query (用户输入)</label>
                                <textarea
                                    value={query}
                                    onChange={e => setQuery(e.target.value)}
                                    className="w-full h-32 bg-white/5 border border-white/10 rounded-xl p-4 focus:outline-none focus:border-blue-500 transition-colors resize-none font-mono text-sm"
                                    placeholder="输入测试 Query..."
                                />
                            </div>

                            <div className="flex-1 flex flex-col min-h-0">
                                <div className="flex justify-between items-center mb-2">
                                    <label className="block text-sm font-medium text-slate-400">Model Output (模型输出)</label>
                                    {latency !== null && (
                                        <span className="text-xs text-emerald-400 flex items-center gap-1">
                                            <Clock size={12} />
                                            耗时: {latency}ms
                                        </span>
                                    )}
                                </div>
                                <div className="flex-1 bg-black/30 border border-white/10 rounded-xl p-4 overflow-y-auto font-mono text-sm whitespace-pre-wrap text-slate-300">
                                    {loading ? (
                                        <div className="h-full flex items-center justify-center text-slate-500">
                                            <div className="animate-spin mr-2">
                                                <Cpu size={16} />
                                            </div>
                                            生成中...
                                        </div>
                                    ) : output ? output : (
                                        <span className="text-slate-600 italic">等待运行结果...</span>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>

                    {error && (
                        <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-4 rounded-xl text-sm">
                            {error}
                        </div>
                    )}
                </div>

                <div className="mt-6 flex justify-end gap-3 pt-4 border-t border-white/5">
                    <button
                        onClick={onClose}
                        className="px-6 py-2.5 rounded-xl hover:bg-white/5 transition-colors text-slate-400 hover:text-white font-medium"
                    >
                        关闭
                    </button>
                    <button
                        onClick={handleRun}
                        disabled={loading}
                        className="px-6 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 hover:shadow-lg hover:shadow-blue-500/20 transition-all text-white font-medium flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {loading ? <Clock size={18} className="animate-spin" /> : <Play size={18} fill="currentColor" />}
                        执行测试
                    </button>
                </div>
            </motion.div>
        </div>
    );
}
