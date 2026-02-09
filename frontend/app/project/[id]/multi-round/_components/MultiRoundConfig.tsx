"use client";

import { useState } from "react";
import { Plus, Trash2, Wand2, Sparkles, X, Loader2, Maximize2 } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import axios from "axios";

const API_BASE = "/api";

export interface RoundConfig {
    round: number;
    query_col: string;
    target_col: string;  // 每轮都有 target（期望意图）
    rewrite_col?: string;  // Query 改写列（可选）
    reason_col?: string;   // 原因/备注列（可选）
}

interface MultiRoundConfigProps {
    roundsConfig: RoundConfig[];
    onRoundsConfigChange: (config: RoundConfig[]) => void;
    availableColumns: string[];
    onAutoDetect: () => void;
    isDetecting?: boolean;
    // 提取配置
    intentExtractField: string;
    onIntentExtractFieldChange: (field: string) => void;
    responseExtractField: string;
    onResponseExtractFieldChange: (field: string) => void;
    // 项目信息（用于获取优化模型配置）
    projectId?: string;
    showToast?: (message: string, type?: "success" | "error") => void;
}

export default function MultiRoundConfig({
    roundsConfig,
    onRoundsConfigChange,
    availableColumns,
    onAutoDetect,
    isDetecting = false,
    intentExtractField,
    onIntentExtractFieldChange,
    responseExtractField,
    onResponseExtractFieldChange,
    projectId,
    showToast
}: MultiRoundConfigProps) {
    // AI 补全相关状态
    const [showAiExtract, setShowAiExtract] = useState(false);
    const [aiExtractInput, setAiExtractInput] = useState("");
    const [aiExtractDescription, setAiExtractDescription] = useState("");  // 额外描述
    const [isAiExtracting, setIsAiExtracting] = useState(false);

    // 放大编辑弹窗状态
    const [expandedEditor, setExpandedEditor] = useState<"intent" | "response" | null>(null);
    const [tempEditValue, setTempEditValue] = useState("");

    const addRound = () => {
        const newRound = roundsConfig.length + 1;
        const newConfig: RoundConfig = {
            round: newRound,
            query_col: "",
            target_col: "",
            rewrite_col: "",
            reason_col: ""
        };
        onRoundsConfigChange([...roundsConfig, newConfig]);
    };

    const removeRound = (index: number) => {
        if (roundsConfig.length <= 1) return;
        const newConfig = roundsConfig
            .filter((_, i) => i !== index)
            .map((cfg, i) => ({ ...cfg, round: i + 1 }));
        onRoundsConfigChange(newConfig);
    };

    const updateRound = (index: number, field: keyof RoundConfig, value: string) => {
        const newConfig = [...roundsConfig];
        newConfig[index] = { ...newConfig[index], [field]: value };
        onRoundsConfigChange(newConfig);
    };

    // AI 补全提取路径
    const handleAiExtract = async () => {
        if (!aiExtractInput.trim()) {
            showToast?.("请输入 API 响应示例", "error");
            return;
        }

        if (!projectId) {
            showToast?.("项目 ID 不存在", "error");
            return;
        }

        setIsAiExtracting(true);
        try {
            const res = await axios.post(`${API_BASE}/ai/generate-extract-paths`, {
                sample_response: aiExtractInput,
                project_id: projectId,
                extra_description: aiExtractDescription  // 额外描述
            });

            if (res.data.intent_code) {
                onIntentExtractFieldChange(res.data.intent_code);
            }
            if (res.data.response_code) {
                onResponseExtractFieldChange(res.data.response_code);
            }

            showToast?.("提取代码生成成功！", "success");
            setShowAiExtract(false);
            setAiExtractInput("");
            setAiExtractDescription("");
        } catch (e: any) {
            console.error("AI extract failed:", e);
            showToast?.(e.response?.data?.detail || "AI 生成失败", "error");
        } finally {
            setIsAiExtracting(false);
        }
    };

    // 打开放大编辑器
    const openExpandedEditor = (type: "intent" | "response") => {
        setExpandedEditor(type);
        setTempEditValue(type === "intent" ? intentExtractField : responseExtractField);
    };

    // 保存放大编辑器内容
    const saveExpandedEditor = () => {
        if (expandedEditor === "intent") {
            onIntentExtractFieldChange(tempEditValue);
        } else if (expandedEditor === "response") {
            onResponseExtractFieldChange(tempEditValue);
        }
        setExpandedEditor(null);
        setTempEditValue("");
    };

    return (
        <div className="space-y-4">
            {/* 轮次配置 */}
            <div className="bg-slate-800/40 border border-white/5 rounded-xl p-4">
                <div className="flex justify-between items-center mb-4">
                    <label className="block text-sm font-medium text-slate-400">
                        轮次配置 ({roundsConfig.length} 轮)
                    </label>
                    <div className="flex gap-2">
                        <button
                            onClick={onAutoDetect}
                            disabled={isDetecting || availableColumns.length === 0}
                            className="flex items-center gap-1 text-xs bg-purple-500/10 text-purple-400 hover:bg-purple-500/20 disabled:opacity-50 px-3 py-1.5 rounded-lg transition-colors"
                        >
                            <Wand2 size={14} />
                            {isDetecting ? "检测中..." : "自动检测"}
                        </button>
                        <button
                            onClick={addRound}
                            className="flex items-center gap-1 text-xs bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 px-3 py-1.5 rounded-lg transition-colors"
                        >
                            <Plus size={14} />
                            添加轮次
                        </button>
                    </div>
                </div>

                <div className="space-y-3 max-h-[300px] overflow-y-auto pr-2">
                    {roundsConfig.map((cfg, index) => (
                        <div
                            key={cfg.round}
                            className="p-3 rounded-lg border bg-slate-700/30 border-white/5"
                        >
                            <div className="flex justify-between items-center mb-2">
                                <span className="text-sm font-medium text-slate-300">
                                    第 {cfg.round} 轮
                                </span>
                                {roundsConfig.length > 1 && (
                                    <button
                                        onClick={() => removeRound(index)}
                                        className="text-red-400 hover:text-red-300 p-1"
                                    >
                                        <Trash2 size={14} />
                                    </button>
                                )}
                            </div>

                            <div className="grid grid-cols-4 gap-2">
                                {/* Query 列 */}
                                <div>
                                    <label className="block text-xs text-blue-400 mb-1">Query 列</label>
                                    <select
                                        value={cfg.query_col}
                                        onChange={(e) => updateRound(index, "query_col", e.target.value)}
                                        className="w-full bg-slate-800 border border-white/10 rounded-lg px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
                                    >
                                        <option value="">选择列...</option>
                                        {availableColumns.map((col) => (
                                            <option key={col} value={col}>{col}</option>
                                        ))}
                                    </select>
                                </div>

                                {/* Target 列（期望意图） */}
                                <div>
                                    <label className="block text-xs text-emerald-400 mb-1">
                                        Target 列
                                    </label>
                                    <select
                                        value={cfg.target_col}
                                        onChange={(e) => updateRound(index, "target_col", e.target.value)}
                                        className="w-full bg-slate-800 border border-white/10 rounded-lg px-2 py-1.5 text-sm focus:border-emerald-500 focus:outline-none"
                                    >
                                        <option value="">选择列...</option>
                                        {availableColumns.map((col) => (
                                            <option key={col} value={col}>{col}</option>
                                        ))}
                                    </select>
                                </div>

                                {/* Query 改写列（可选） */}
                                <div>
                                    <label className="block text-xs text-purple-400 mb-1">
                                        改写列
                                    </label>
                                    <select
                                        value={cfg.rewrite_col || ""}
                                        onChange={(e) => updateRound(index, "rewrite_col", e.target.value)}
                                        className="w-full bg-slate-800 border border-white/10 rounded-lg px-2 py-1.5 text-sm focus:border-purple-500 focus:outline-none"
                                    >
                                        <option value="">选择列...</option>
                                        {availableColumns.map((col) => (
                                            <option key={col} value={col}>{col}</option>
                                        ))}
                                    </select>
                                </div>

                                {/* 原因列（可选） */}
                                <div>
                                    <label className="block text-xs text-amber-400 mb-1">
                                        原因列
                                    </label>
                                    <select
                                        value={cfg.reason_col || ""}
                                        onChange={(e) => updateRound(index, "reason_col", e.target.value)}
                                        className="w-full bg-slate-800 border border-white/10 rounded-lg px-2 py-1.5 text-sm focus:border-amber-500 focus:outline-none"
                                    >
                                        <option value="">选择列...</option>
                                        {availableColumns.map((col) => (
                                            <option key={col} value={col}>{col}</option>
                                        ))}
                                    </select>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* 响应解析配置 */}
            <div className="bg-slate-800/40 border border-white/5 rounded-xl p-4">
                <div className="flex justify-between items-center mb-3">
                    <label className="block text-sm font-medium text-slate-400">响应解析配置</label>
                    <button
                        onClick={() => setShowAiExtract(true)}
                        className="flex items-center gap-1 text-xs bg-purple-500/10 text-purple-400 hover:bg-purple-500/20 px-2 py-1 rounded-md transition-colors"
                    >
                        <Sparkles size={12} />
                        AI 补全
                    </button>
                </div>
                <div className="grid grid-cols-2 gap-4">
                    <div>
                        <div className="flex items-center justify-between mb-1">
                            <label className="block text-xs text-amber-400">
                                意图提取代码 <span className="text-red-400">*</span>
                            </label>
                            <button
                                onClick={() => openExpandedEditor("intent")}
                                className="text-slate-500 hover:text-amber-400 transition-colors p-1"
                                title="放大编辑"
                            >
                                <Maximize2 size={12} />
                            </button>
                        </div>
                        <div
                            onClick={() => openExpandedEditor("intent")}
                            className="w-full bg-slate-800 border border-white/10 rounded-lg px-3 py-2 text-sm font-mono h-[80px] overflow-hidden cursor-pointer hover:border-amber-500/50 transition-colors"
                        >
                            <pre className="text-slate-300 whitespace-pre-wrap text-xs overflow-hidden">
                                {intentExtractField || <span className="text-slate-500 italic">点击编辑...</span>}
                            </pre>
                        </div>
                        <p className="text-xs text-slate-500 mt-1">支持简单路径或 py: 前缀的 Python 代码</p>
                    </div>
                    <div>
                        <div className="flex items-center justify-between mb-1">
                            <label className="block text-xs text-cyan-400">
                                回复内容提取代码 <span className="text-red-400">*</span>
                            </label>
                            <button
                                onClick={() => openExpandedEditor("response")}
                                className="text-slate-500 hover:text-cyan-400 transition-colors p-1"
                                title="放大编辑"
                            >
                                <Maximize2 size={12} />
                            </button>
                        </div>
                        <div
                            onClick={() => openExpandedEditor("response")}
                            className="w-full bg-slate-800 border border-white/10 rounded-lg px-3 py-2 text-sm font-mono h-[80px] overflow-hidden cursor-pointer hover:border-cyan-500/50 transition-colors"
                        >
                            <pre className="text-slate-300 whitespace-pre-wrap text-xs overflow-hidden">
                                {responseExtractField || <span className="text-slate-500 italic">点击编辑...</span>}
                            </pre>
                        </div>
                        <p className="text-xs text-slate-500 mt-1">支持简单路径或 py: 前缀的 Python 代码</p>
                    </div>
                </div>
            </div>

            {/* 配置说明 */}
            <div className="p-3 bg-slate-700/20 rounded-lg">
                <p className="text-xs text-slate-500">
                    <span className="text-slate-400 font-medium">执行逻辑：</span>
                    同一轮的所有数据并发请求 API 接口，等待全部完成后，再执行下一轮。每轮都会验证意图是否匹配 Target。
                </p>
                <p className="text-xs text-slate-500 mt-1">
                    <span className="text-slate-400 font-medium">接口配置：</span>
                    请在右上角【项目配置】-【验证配置】中设置 API 地址和参数转换脚本。
                </p>
            </div>

            {/* AI 补全弹窗 */}
            <AnimatePresence>
                {showAiExtract && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-[60]"
                        onClick={(e) => {
                            if (e.target === e.currentTarget && !isAiExtracting) {
                                setShowAiExtract(false);
                            }
                        }}
                    >
                        <motion.div
                            initial={{ scale: 0.9, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ scale: 0.9, opacity: 0 }}
                            className="bg-slate-900 border border-white/10 rounded-xl w-full max-w-2xl shadow-2xl max-h-[90vh] overflow-y-auto"
                        >
                            <div className="flex items-center justify-between p-4 border-b border-white/10">
                                <div className="flex items-center gap-2">
                                    <Sparkles className="text-purple-400" size={20} />
                                    <h3 className="text-lg font-semibold">AI 生成提取代码</h3>
                                </div>
                                <button
                                    onClick={() => !isAiExtracting && setShowAiExtract(false)}
                                    className="text-slate-400 hover:text-white transition-colors"
                                    disabled={isAiExtracting}
                                >
                                    <X size={20} />
                                </button>
                            </div>
                            <div className="p-4 space-y-4">
                                <div>
                                    <label className="block text-sm font-medium text-slate-300 mb-2">
                                        API 响应示例 (JSON) <span className="text-red-400">*</span>
                                    </label>
                                    <textarea
                                        value={aiExtractInput}
                                        onChange={(e) => setAiExtractInput(e.target.value)}
                                        className="w-full bg-slate-800 border border-white/10 rounded-lg px-3 py-2 focus:outline-none focus:border-purple-500 transition-colors text-sm font-mono h-[200px]"
                                        placeholder={`{
  "code": 0,
  "data": {
    "intent_result": {
      "intent": "查询余额",
      "confidence": 0.95
    },
    "lastResponse": "您的账户余额为 1000 元"
  }
}`}
                                        disabled={isAiExtracting}
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-slate-300 mb-2">
                                        额外说明（可选）
                                    </label>
                                    <p className="text-xs text-slate-500 mb-2">
                                        描述你的提取需求，AI 会根据说明生成更精确的 Python 代码
                                    </p>
                                    <textarea
                                        value={aiExtractDescription}
                                        onChange={(e) => setAiExtractDescription(e.target.value)}
                                        className="w-full bg-slate-800 border border-white/10 rounded-lg px-3 py-2 focus:outline-none focus:border-purple-500 transition-colors text-sm h-[80px]"
                                        placeholder="例如：意图在 intent_result.intent 字段中，回复内容在 lastResponse 字段中"
                                        disabled={isAiExtracting}
                                    />
                                </div>
                                <div className="bg-slate-800/50 rounded-lg p-3 space-y-2">
                                    <p className="text-xs text-slate-400">
                                        <span className="text-purple-400 font-medium">生成格式：</span>
                                        AI 会生成带 <code className="text-amber-300">py:</code> 前缀的 Python 代码，将提取结果赋值给 <code className="text-cyan-300">result</code> 变量
                                    </p>
                                    <p className="text-xs text-slate-400">
                                        <span className="text-purple-400 font-medium">可用变量：</span>
                                        <code className="text-cyan-300">data</code> (解析后的 JSON)、
                                        <code className="text-cyan-300">output</code> (原始文本)、
                                        <code className="text-cyan-300">is_json</code> (是否为 JSON)
                                    </p>
                                </div>
                            </div>
                            <div className="flex justify-end gap-3 p-4 border-t border-white/10">
                                <button
                                    onClick={() => setShowAiExtract(false)}
                                    disabled={isAiExtracting}
                                    className="px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 transition-colors text-sm disabled:opacity-50"
                                >
                                    取消
                                </button>
                                <button
                                    onClick={handleAiExtract}
                                    disabled={isAiExtracting || !aiExtractInput.trim()}
                                    className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors text-sm ${isAiExtracting || !aiExtractInput.trim()
                                        ? "bg-purple-600/50 cursor-not-allowed"
                                        : "bg-purple-600 hover:bg-purple-500"
                                        }`}
                                >
                                    {isAiExtracting ? (
                                        <>
                                            <Loader2 size={14} className="animate-spin" />
                                            生成中...
                                        </>
                                    ) : (
                                        <>
                                            <Sparkles size={14} />
                                            生成代码
                                        </>
                                    )}
                                </button>
                            </div>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* 放大编辑弹窗 */}
            <AnimatePresence>
                {expandedEditor && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-[60]"
                        onClick={(e) => {
                            if (e.target === e.currentTarget) {
                                setExpandedEditor(null);
                            }
                        }}
                    >
                        <motion.div
                            initial={{ scale: 0.9, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ scale: 0.9, opacity: 0 }}
                            className="bg-slate-900 border border-white/10 rounded-xl w-full max-w-3xl shadow-2xl"
                        >
                            <div className="flex items-center justify-between p-4 border-b border-white/10">
                                <div className="flex items-center gap-2">
                                    <Maximize2 className={expandedEditor === "intent" ? "text-amber-400" : "text-cyan-400"} size={20} />
                                    <h3 className="text-lg font-semibold">
                                        {expandedEditor === "intent" ? "意图提取代码" : "回复内容提取代码"}
                                    </h3>
                                </div>
                                <button
                                    onClick={() => setExpandedEditor(null)}
                                    className="text-slate-400 hover:text-white transition-colors"
                                >
                                    <X size={20} />
                                </button>
                            </div>
                            <div className="p-4">
                                <textarea
                                    value={tempEditValue}
                                    onChange={(e) => setTempEditValue(e.target.value)}
                                    placeholder={expandedEditor === "intent"
                                        ? `简单路径: data.intent\n\n或 Python 代码:\npy:\nresult = data.get("intent", "")`
                                        : `简单路径: data.response\n\n或 Python 代码:\npy:\nresult = data.get("response", "")`
                                    }
                                    className={`w-full bg-slate-800 border border-white/10 rounded-lg px-4 py-3 text-sm font-mono focus:outline-none transition-colors h-[300px] resize-none ${
                                        expandedEditor === "intent" ? "focus:border-amber-500" : "focus:border-cyan-500"
                                    }`}
                                    autoFocus
                                />
                                <div className="mt-3 bg-slate-800/50 rounded-lg p-3 space-y-2">
                                    <p className="text-xs text-slate-400">
                                        <span className={expandedEditor === "intent" ? "text-amber-400 font-medium" : "text-cyan-400 font-medium"}>格式说明：</span>
                                        支持简单路径（如 <code className="text-slate-300">data.intent</code>）或 <code className="text-purple-400">py:</code> 前缀的 Python 代码
                                    </p>
                                    <p className="text-xs text-slate-400">
                                        <span className={expandedEditor === "intent" ? "text-amber-400 font-medium" : "text-cyan-400 font-medium"}>可用变量：</span>
                                        <code className="text-slate-300">data</code> (解析后的 JSON)、
                                        <code className="text-slate-300">output</code> (原始文本)、
                                        <code className="text-slate-300">is_json</code> (是否为 JSON)
                                    </p>
                                    <p className="text-xs text-slate-400">
                                        <span className={expandedEditor === "intent" ? "text-amber-400 font-medium" : "text-cyan-400 font-medium"}>输出要求：</span>
                                        将提取结果赋值给 <code className="text-emerald-400">result</code> 变量
                                    </p>
                                </div>
                            </div>
                            <div className="flex justify-end gap-3 p-4 border-t border-white/10">
                                <button
                                    onClick={() => setExpandedEditor(null)}
                                    className="px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 transition-colors text-sm"
                                >
                                    取消
                                </button>
                                <button
                                    onClick={saveExpandedEditor}
                                    className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors text-sm ${
                                        expandedEditor === "intent"
                                            ? "bg-amber-600 hover:bg-amber-500"
                                            : "bg-cyan-600 hover:bg-cyan-500"
                                    }`}
                                >
                                    保存
                                </button>
                            </div>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}
