/**
 * 模型输出测试弹窗组件
 * 支持 System Prompt、会话历史、用户 Query 输入
 */
import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Play, Clock, Cpu, ChevronDown, Copy, Check, Plus, Trash2, MessageSquare, FileJson, RefreshCcw, History, RotateCcw, Wand2 } from "lucide-react";
import axios from "axios";

/**
 * 历史消息接口
 */
interface HistoryMessage {
    role: "user" | "assistant";
    content: string;
}

/**
 * 组件属性接口
 */
interface TestOutputModalProps {
    onClose: () => void;
    initialPrompt?: string;
    initialModelConfig?: any;
}

/**
 * 模型输出测试弹窗
 * 
 * @param onClose - 关闭弹窗回调
 * @param initialPrompt - 初始提示词
 * @param initialModelConfig - 初始模型配置
 */
export default function TestOutputModal({ onClose, initialPrompt = "", initialModelConfig }: TestOutputModalProps) {
    const [prompt, setPrompt] = useState(initialPrompt);
    const [query, setQuery] = useState("");
    const [output, setOutput] = useState("");
    const [latency, setLatency] = useState<number | null>(null);
    const [requestId, setRequestId] = useState<string | null>(null);
    const [copied, setCopied] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    const [globalModels, setGlobalModels] = useState<any[]>([]);
    const [selectedModelId, setSelectedModelId] = useState<string>("");
    const [useCustomConfig, setUseCustomConfig] = useState(!!initialModelConfig);

    // 会话历史相关状态
    const [historyMessages, setHistoryMessages] = useState<HistoryMessage[]>([]);
    // 输入模式：json = JSON导入，manual = 手动添加
    const [inputMode, setInputMode] = useState<"json" | "manual">("json");
    // JSON 输入临时存储
    const [jsonInput, setJsonInput] = useState("");
    // JSON 解析错误
    const [jsonError, setJsonError] = useState("");
    // 手动添加的当前消息
    const [manualRole, setManualRole] = useState<"user" | "assistant">("assistant");
    const [manualContent, setManualContent] = useState("");
    // 是否展开历史消息区域
    const [showHistory, setShowHistory] = useState(false);

    // AI 修复中
    const [repairing, setRepairing] = useState(false);

    // Playground 运行历史
    const [runHistory, setRunHistory] = useState<any[]>([]);
    const [showRunHistory, setShowRunHistory] = useState(false);

    /** 获取运行历史 */
    const fetchRunHistory = () => {
        axios.get("/api/playground/history")
            .then(res => setRunHistory(res.data || []))
            .catch(console.error);
    };

    /** 恢复历史记录（异步获取完整详情） */
    const restoreHistory = async (item: any) => {
        try {
            // 先调用详情接口获取完整记录（包含 prompt）
            const detailRes = await axios.get(`/api/playground/history/${item.id}`);
            const fullItem = detailRes.data;

            setPrompt(fullItem.prompt || "");
            setQuery(fullItem.query || "");

            // 处理 history_messages：可能是 JSON 字符串或数组
            let parsedMessages: HistoryMessage[] = [];
            try {
                if (typeof fullItem.history_messages === 'string') {
                    // 如果是字符串，尝试解析 JSON
                    parsedMessages = JSON.parse(fullItem.history_messages) || [];
                } else if (Array.isArray(fullItem.history_messages)) {
                    // 如果已经是数组，直接使用
                    parsedMessages = fullItem.history_messages;
                }
            } catch (e) {
                // 解析失败时使用空数组
                console.error("解析历史消息失败:", e);
                parsedMessages = [];
            }
            setHistoryMessages(parsedMessages);

            // 如果有历史消息，自动展开消息列表
            if (parsedMessages.length > 0) {
                setShowHistory(true);
            }

            setOutput(fullItem.output || "");
            setLatency(fullItem.latency_ms);
            if (fullItem.model_config) {
                // 简单处理：如果是历史记录恢复的，尝试匹配 Config
                // 这里为了简化，我们可能无法完全恢复复杂的 model selection 状态
                // 但可以使用 custom config 模式
                setUseCustomConfig(true);
            }
            setShowRunHistory(false);
        } catch (e) {
            console.error("获取历史记录详情失败:", e);
            setError("加载历史记录失败");
        }
    };

    /** 删除历史记录 */
    const deleteRunHistory = (e: any, id: number) => {
        e.stopPropagation();
        axios.delete(`/api/playground/history/${id}`)
            .then(() => fetchRunHistory())
            .catch(console.error);
    };

    /** 清空历史记录 */
    const clearRunHistory = () => {
        if (!confirm("确定清空所有测试记录吗？")) return;
        axios.delete("/api/playground/history")
            .then(() => fetchRunHistory())
            .catch(console.error);
    };

    useEffect(() => {
        fetchRunHistory();
    }, []);

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

    /**
     * 重置所有状态（恢复到初始打开状态）
     */
    const handleReset = () => {
        // 将 prompt 恢复为项目初始提示词
        setPrompt(initialPrompt);
        setQuery("");
        setOutput("");
        setError("");
        setLatency(null);
        setRequestId(null);
        setHistoryMessages([]);
        setJsonInput("");
        setJsonError("");
        setInputMode("manual");
        setCopied(false);
        setShowHistory(false);
    };

    /**
     * AI 自动修复 JSON
     */
    const handleRepairJson = async () => {
        if (!jsonInput.trim()) return;

        setRepairing(true);
        try {
            // 获取当前选中的模型配置作为修复工具
            let modelConfig = null;
            if (useCustomConfig && initialModelConfig) {
                modelConfig = initialModelConfig;
            } else {
                const selected = globalModels.find(m => m.id === selectedModelId);
                if (selected) modelConfig = selected;
            }

            const res = await axios.post("/api/playground/fix_json", {
                text: jsonInput,
                llm_config: modelConfig
            });

            if (res.data.fixed_text) {
                // 尝试使用 execCommand 以保留撤销(Ctrl+Z)历史
                const textarea = document.getElementById("history-json-input") as HTMLTextAreaElement;
                if (textarea) {
                    textarea.focus();
                    textarea.select();
                    // document.execCommand('insertText') is deprecated but widely supported for preserving undo history
                    const success = document.execCommand("insertText", false, res.data.fixed_text);
                    if (!success) setJsonInput(res.data.fixed_text);
                } else {
                    setJsonInput(res.data.fixed_text);
                }
                setJsonError("");
            }
        } catch (e: any) {
            console.error(e);
            setJsonError("修复失败: " + (e.response?.data?.detail || e.message));
        } finally {
            setRepairing(false);
        }
    };

    /**
     * 解析 JSON 并导入历史消息
     */
    const handleParseJson = () => {
        setJsonError("");
        if (!jsonInput.trim()) {
            setJsonError("请输入 JSON 数据");
            return;
        }
        try {
            const parsed = JSON.parse(jsonInput);
            if (!Array.isArray(parsed)) {
                setJsonError("JSON 必须是数组格式");
                return;
            }
            // 过滤并转换消息格式
            const messages: HistoryMessage[] = parsed
                .filter((item: any) => item.role && item.content)
                .map((item: any) => ({
                    role: item.role === "assistant" ? "assistant" : "user",
                    content: String(item.content)
                }));

            if (messages.length === 0) {
                setJsonError("未找到有效消息（需要包含 role 和 content 字段）");
                return;
            }

            setHistoryMessages(messages);
            setJsonInput("");
            setShowHistory(true);
        } catch (e: any) {
            setJsonError(`JSON 解析失败: ${e.message}`);
        }
    };

    /**
     * 添加单条手动消息
     */
    const handleAddManualMessage = () => {
        if (!manualContent.trim()) return;
        setHistoryMessages([...historyMessages, { role: manualRole, content: manualContent }]);
        setManualContent("");
        setShowHistory(true);
    };

    /**
     * 删除指定索引的消息
     */
    const handleDeleteMessage = (index: number) => {
        setHistoryMessages(historyMessages.filter((_, i) => i !== index));
    };

    /**
     * 清空所有历史消息
     */
    const handleClearHistory = () => {
        setHistoryMessages([]);
    };

    /**
     * 执行测试
     */
    const handleRun = async () => {
        // 校验逻辑：如果有 Query 直接通过；如果不传 Query，则必须有历史消息且最后一条是 user
        const hasQuery = !!query.trim();
        const lastMessageIsUser = historyMessages.length > 0 && historyMessages[historyMessages.length - 1].role === "user";

        if (!hasQuery && !lastMessageIsUser) {
            setError("请输入测试 Query (或确保历史消息最后一条为 user)");
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

        setLoading(true);
        setError("");
        setOutput("");
        setLatency(null);
        setRequestId(null);
        setCopied(false);

        try {
            const res = await axios.post("/api/playground/test", {
                prompt,
                query,
                llm_config: modelConfig,
                // 传递历史消息（如果有）
                history_messages: historyMessages.length > 0 ? historyMessages : undefined
            });

            setOutput(res.data.output);
            setLatency(res.data.latency_ms);
            setRequestId(res.data.request_id);
            fetchRunHistory(); // 刷新历史
        } catch (e: any) {
            console.error(e);
            setError(e.response?.data?.detail || "请求失败");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-[100]">
            {/* 点击背景关闭（带确认提示） */}
            <div className="absolute inset-0" onClick={() => {
                if (confirm("确定要退出 Playground 吗？未保存的内容将丢失。")) {
                    onClose();
                }
            }} />

            <motion.div
                initial={{ scale: 0.9, opacity: 0, y: 20 }}
                animate={{ scale: 1, opacity: 1, y: 0 }}
                exit={{ scale: 0.9, opacity: 0, y: 20 }}
                className="glass w-full max-w-5xl p-6 rounded-3xl max-h-[90vh] flex flex-col relative z-10"
                onClick={e => e.stopPropagation()}
            >
                <div className="flex justify-between items-center mb-6">
                    <h2 className="text-xl font-bold flex items-center gap-2 bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-400">
                        <Cpu size={24} className="text-blue-400" />
                        模型输出测试 (Playground)
                    </h2>
                    <div className="flex items-center gap-2">
                        {/* 历史记录按钮 */}
                        <button
                            onClick={() => setShowRunHistory(!showRunHistory)}
                            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg transition-colors text-sm font-medium ${showRunHistory ? "bg-white/10 text-white" : "text-slate-400 hover:text-white hover:bg-white/5"}`}
                        >
                            <History size={16} />
                            {showRunHistory ? "隐藏记录" : "历史记录"}
                        </button>
                        <button onClick={onClose} className="p-2 hover:bg-white/10 rounded-full transition-colors text-slate-400 hover:text-white">
                            <X size={20} />
                        </button>
                    </div>
                </div>

                <div className="flex-1 flex overflow-hidden">
                    {/* Main Content */}
                    <div className="flex-1 overflow-y-auto space-y-4 min-h-0 pr-2 custom-scrollbar p-1">
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

                        {/* 会话历史输入区域 */}
                        <div className="bg-white/5 rounded-xl p-4 border border-white/10">
                            <div className="flex justify-between items-center mb-3">
                                <label className="text-sm font-medium text-slate-400 flex items-center gap-2">
                                    <MessageSquare size={14} />
                                    会话历史 (可选)
                                    {historyMessages.length > 0 && (
                                        <span className="text-xs bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded-full">
                                            {historyMessages.length} 条
                                        </span>
                                    )}
                                </label>
                                <div className="text-xs flex gap-2">
                                    <button
                                        onClick={() => setInputMode("json")}
                                        className={`px-3 py-1 rounded-lg transition-colors border flex items-center gap-1 ${inputMode === "json" ? "bg-purple-600 border-purple-500 text-white" : "bg-transparent border-white/10 text-slate-400 hover:text-white"}`}
                                    >
                                        <FileJson size={12} />
                                        JSON 导入
                                    </button>
                                    <button
                                        onClick={() => setInputMode("manual")}
                                        className={`px-3 py-1 rounded-lg transition-colors border flex items-center gap-1 ${inputMode === "manual" ? "bg-purple-600 border-purple-500 text-white" : "bg-transparent border-white/10 text-slate-400 hover:text-white"}`}
                                    >
                                        <Plus size={12} />
                                        手动添加
                                    </button>
                                </div>
                            </div>

                            {/* JSON 导入模式 */}
                            {inputMode === "json" && (
                                <div className="space-y-2">
                                    <textarea
                                        id="history-json-input"
                                        value={jsonInput}
                                        onChange={e => setJsonInput(e.target.value)}
                                        placeholder={'粘贴 JSON 数组，格式如:\n[\n  {"role": "assistant", "content": "您好"},\n  {"role": "user", "content": "查询余额"}\n]'}
                                        className="w-full h-24 bg-black/20 border border-white/10 rounded-xl p-3 focus:outline-none focus:border-purple-500 transition-colors resize-none font-mono text-xs text-slate-300"
                                    />
                                    {jsonError && (
                                        <div className="text-xs text-red-400">{jsonError}</div>
                                    )}
                                    <div className="flex gap-2">
                                        <button
                                            onClick={handleParseJson}
                                            className="text-xs px-4 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white transition-colors"
                                        >
                                            解析导入
                                        </button>
                                        <button
                                            onClick={handleRepairJson}
                                            disabled={repairing}
                                            className="text-xs px-3 py-1.5 rounded-lg border border-purple-500/30 text-purple-400 hover:bg-purple-500/10 transition-colors flex items-center gap-1 disabled:opacity-50"
                                            title="尝试使用 AI 自动修复格式"
                                        >
                                            <Wand2 size={12} className={repairing ? "animate-spin" : ""} />
                                            {repairing ? "修复中..." : "AI 格式修复"}
                                        </button>
                                    </div>
                                </div>
                            )}

                            {/* 手动添加模式 */}
                            {inputMode === "manual" && (
                                <div className="flex gap-2 items-start">
                                    <button
                                        onClick={() => setManualRole(manualRole === "user" ? "assistant" : "user")}
                                        className={`shrink-0 h-[34px] px-3 rounded-lg border flex items-center gap-2 text-xs font-medium transition-all ${manualRole === "user"
                                            ? "bg-blue-500/20 border-blue-500/30 text-blue-400 hover:bg-blue-500/30"
                                            : "bg-emerald-500/20 border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/30"
                                            }`}
                                        title="点击切换角色"
                                    >
                                        {manualRole}
                                        <RefreshCcw size={12} className="opacity-70" />
                                    </button>
                                    <input
                                        value={manualContent}
                                        onChange={e => setManualContent(e.target.value)}
                                        placeholder="输入消息内容..."
                                        className="flex-1 bg-black/20 border border-white/10 rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-purple-500 text-slate-300"
                                        onKeyDown={e => e.key === "Enter" && handleAddManualMessage()}
                                    />
                                    <button
                                        onClick={handleAddManualMessage}
                                        className="px-3 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 text-white transition-colors"
                                    >
                                        <Plus size={14} />
                                    </button>
                                </div>
                            )}

                            {/* 已添加的历史消息列表 */}
                            {historyMessages.length > 0 && (
                                <div className="mt-3 space-y-1">
                                    <div className="flex justify-between items-center mb-2">
                                        <button
                                            onClick={() => setShowHistory(!showHistory)}
                                            className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
                                        >
                                            {showHistory ? "收起" : "展开"} 消息列表
                                        </button>
                                        <button
                                            onClick={handleClearHistory}
                                            className="text-xs text-red-400 hover:text-red-300 transition-colors flex items-center gap-1"
                                        >
                                            <Trash2 size={10} />
                                            清空全部
                                        </button>
                                    </div>
                                    {showHistory && (
                                        <div className="max-h-32 overflow-y-auto space-y-1 custom-scrollbar">
                                            {historyMessages.map((msg, idx) => (
                                                <div
                                                    key={idx}
                                                    className={`flex items-start gap-2 text-xs p-2 rounded-lg ${msg.role === "assistant" ? "bg-emerald-500/10 border border-emerald-500/20" : "bg-blue-500/10 border border-blue-500/20"}`}
                                                >
                                                    <span className={`shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium ${msg.role === "assistant" ? "bg-emerald-500/20 text-emerald-400" : "bg-blue-500/20 text-blue-400"}`}>
                                                        {msg.role}
                                                    </span>
                                                    <span className="flex-1 text-slate-300 line-clamp-2">{msg.content}</span>
                                                    <button
                                                        onClick={() => handleDeleteMessage(idx)}
                                                        className="shrink-0 text-slate-500 hover:text-red-400 transition-colors"
                                                    >
                                                        <X size={12} />
                                                    </button>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>

                        {/* Prompt + Query + Output */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 h-[320px]">
                            <div className="flex flex-col h-full">
                                <label className="block text-sm font-medium text-slate-400 mb-2">System Prompt (提示词)</label>
                                <textarea
                                    value={prompt}
                                    onChange={e => setPrompt(e.target.value)}
                                    className="flex-1 w-full bg-white/5 border border-white/10 rounded-xl p-4 focus:outline-none focus:border-blue-500 transition-colors resize-none font-mono text-sm leading-relaxed"
                                    placeholder="输入系统提示词..."
                                />
                            </div>
                            <div className="flex flex-col h-full space-y-3">
                                <div className="flex-none">
                                    <label className="block text-sm font-medium text-slate-400 mb-2">User Query (用户输入)</label>
                                    <textarea
                                        value={query}
                                        onChange={e => setQuery(e.target.value)}
                                        className="w-full h-24 bg-white/5 border border-white/10 rounded-xl p-4 focus:outline-none focus:border-blue-500 transition-colors resize-none font-mono text-sm"
                                        placeholder="输入测试 Query..."
                                    />
                                </div>

                                <div className="flex-1 flex flex-col min-h-0">
                                    <div className="mb-2">
                                        <div className="flex justify-between items-center">
                                            <label className="block text-sm font-medium text-slate-400">Model Output (模型输出)</label>
                                            {latency !== null && (
                                                <span className="text-xs text-emerald-400 flex items-center gap-1">
                                                    <Clock size={12} />
                                                    耗时: {latency}ms
                                                </span>
                                            )}
                                        </div>
                                        {requestId && (
                                            <div
                                                className="mt-1 text-xs text-blue-400 flex items-center gap-1 cursor-pointer hover:text-blue-300 transition-colors w-fit"
                                                onClick={() => {
                                                    navigator.clipboard.writeText(requestId);
                                                    setCopied(true);
                                                    setTimeout(() => setCopied(false), 2000);
                                                }}
                                                title="点击复制完整 Request ID"
                                            >
                                                {copied ? <Check size={12} /> : <Copy size={12} />}
                                                <span className="font-mono">RequestId: {requestId}</span>
                                            </div>
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

                    {/* History Sidebar Toggle */}
                    <AnimatePresence>
                        {showRunHistory && (
                            <motion.div
                                initial={{ width: 0, opacity: 0 }}
                                animate={{ width: 300, opacity: 1 }}
                                exit={{ width: 0, opacity: 0 }}
                                className="border-l border-white/10 bg-black/20 overflow-hidden flex flex-col"
                            >
                                <div className="p-4 border-b border-white/10 flex justify-between items-center">
                                    <h3 className="font-medium text-slate-300 flex items-center gap-2">
                                        <History size={16} />
                                        测试记录
                                    </h3>
                                    <button
                                        onClick={clearRunHistory}
                                        className="p-1 hover:bg-white/10 rounded text-slate-500 hover:text-red-400"
                                        title="清空所有记录"
                                    >
                                        <Trash2 size={14} />
                                    </button>
                                </div>
                                <div className="flex-1 overflow-y-auto custom-scrollbar p-2 space-y-2">
                                    <div className="space-y-4">
                                        {runHistory.map((run) => {
                                            // 解析历史消息以判断是否多轮
                                            let isMultiTurn = false;
                                            try {
                                                const msgs = typeof run.history_messages === 'string'
                                                    ? JSON.parse(run.history_messages)
                                                    : run.history_messages;
                                                if (Array.isArray(msgs) && msgs.length > 0) {
                                                    isMultiTurn = true;
                                                }
                                            } catch (e) { }

                                            return (
                                                <div
                                                    key={run.id}
                                                    className="bg-black/40 border border-white/5 rounded-lg p-3 cursor-pointer hover:bg-white/5 transition-colors group relative"
                                                    onClick={() => restoreHistory(run)}
                                                >
                                                    <div className="flex justify-between items-start mb-1">
                                                        <div className="text-[10px] text-slate-500 font-mono">
                                                            {new Date(run.created_at).toLocaleTimeString()}
                                                        </div>
                                                        <div className="flex gap-1">
                                                            {/* 轮次标签 */}
                                                            <span className={`text-[9px] px-1 rounded border ${isMultiTurn
                                                                ? "bg-purple-500/10 border-purple-500/30 text-purple-400"
                                                                : "bg-blue-500/10 border-blue-500/30 text-blue-400"
                                                                }`}>
                                                                {isMultiTurn ? "多轮" : "单轮"}
                                                            </span>
                                                            <button
                                                                onClick={(e) => deleteRunHistory(e, run.id)}
                                                                className="text-slate-600 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                                                            >
                                                                <Trash2 size={12} />
                                                            </button>
                                                        </div>
                                                    </div>
                                                    <div className="text-xs text-slate-300 line-clamp-2 mb-1">
                                                        <span className="text-purple-400">Q:</span> {run.query || "(空)"}
                                                    </div>
                                                    <div className="text-xs text-slate-400 line-clamp-1">
                                                        <span className="text-emerald-500">A:</span> {run.output}
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                    {runHistory.length === 0 && (
                                        <div className="text-center py-8 text-slate-600 text-xs">
                                            暂无测试记录
                                        </div>
                                    )}
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>

                <div className="mt-6 flex justify-end items-center pt-4 border-t border-white/5">

                    <div className="flex gap-3">
                        {/* 清空会话按钮：只清空 Query 和历史消息，不动 Prompt */}
                        <button
                            onClick={() => {
                                setQuery("");
                                setHistoryMessages([]);
                                setOutput("");
                                setError("");
                                setLatency(null);
                                setRequestId(null);
                                setJsonInput("");
                                setJsonError("");
                                setShowHistory(false);
                            }}
                            className="px-4 py-2.5 rounded-xl hover:bg-white/5 transition-colors text-slate-400 hover:text-amber-400 font-medium flex items-center gap-2"
                            title="清空会话（保留 Prompt）"
                        >
                            <Trash2 size={16} />
                            清空会话
                        </button>
                        <button
                            onClick={handleReset}
                            className="px-4 py-2.5 rounded-xl hover:bg-white/5 transition-colors text-slate-400 hover:text-red-400 font-medium flex items-center gap-2"
                            title="重置所有输入和历史"
                        >
                            <RotateCcw size={16} />
                            重置
                        </button>
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
                </div>
            </motion.div>
        </div>
    );
}
