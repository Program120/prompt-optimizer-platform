import { motion } from "framer-motion";
import {
    Rocket, Pause, Play, Square, Upload, RefreshCw, Copy, Download, X, ClipboardPaste, AlertCircle
} from "lucide-react";

// 统一使用相对路径
const API_BASE = "/api";

interface ExecutionPanelProps {
    taskStatus: any;
    fileInfo: any;
    config: { query_col: string; target_col: string };
    setConfig: (config: { query_col: string; target_col: string }) => void;
    extractField: string;
    setExtractField: (field: string) => void;
    autoIterateConfig: { enabled: boolean; maxRounds: number; targetAccuracy: number };
    setAutoIterateConfig: (config: any) => void;
    autoIterateStatus: any;
    isAutoIterating: boolean;
    onFileUpload: (e: any) => void;
    onStartTask: () => void;
    onControlTask: (action: string) => void;
    onStopAutoIterate: () => void;
    onOptimize: () => void;
    isOptimizing: boolean;
    showExternalOptimize: boolean;
    setShowExternalOptimize: (show: boolean) => void;
    externalPrompt: string;
    setExternalPrompt: (prompt: string) => void;
    onCopyOptimizeContext: () => void;
    onApplyExternalOptimize: () => void;
}

export default function ExecutionPanel({
    taskStatus,
    fileInfo,
    config,
    setConfig,
    extractField,
    setExtractField,
    autoIterateConfig,
    setAutoIterateConfig,
    autoIterateStatus,
    isAutoIterating,
    onFileUpload,
    onStartTask,
    onControlTask,
    onStopAutoIterate,
    onOptimize,
    isOptimizing,
    showExternalOptimize,
    setShowExternalOptimize,
    externalPrompt,
    setExternalPrompt,
    onCopyOptimizeContext,
    onApplyExternalOptimize
}: ExecutionPanelProps) {
    return (
        <section className="glass p-6 rounded-2xl">
            <div className="flex justify-between items-center mb-6">
                <h2 className="text-lg font-semibold flex items-center gap-2">
                    <Rocket size={20} className="text-emerald-400" />
                    批处理执行
                </h2>
                <div className="flex gap-2">
                    {taskStatus?.status === "running" && !isAutoIterating ? (
                        <button onClick={() => onControlTask("pause")} className="flex items-center gap-2 bg-amber-500/10 text-amber-500 hover:bg-amber-500/20 px-4 py-2 rounded-lg font-medium transition-colors">
                            <Pause size={18} /> 暂停
                        </button>
                    ) : taskStatus?.status === "paused" && !isAutoIterating ? (
                        <button onClick={() => onControlTask("resume")} className="flex items-center gap-2 bg-blue-500/10 text-blue-500 hover:bg-blue-500/20 px-4 py-2 rounded-lg font-medium transition-colors">
                            <Play size={18} /> 继续
                        </button>
                    ) : null}

                    {/* 终止按钮 - 自动迭代或普通任务运行时显示 */}
                    {(isAutoIterating || (taskStatus?.status === "running" || taskStatus?.status === "paused")) && (
                        <button
                            onClick={() => isAutoIterating ? onStopAutoIterate() : onControlTask("stop")}
                            className="flex items-center gap-2 bg-red-500/10 text-red-500 hover:bg-red-500/20 px-4 py-2 rounded-lg font-medium transition-colors"
                        >
                            <Square size={18} /> {isAutoIterating ? "停止迭代" : "终止任务"}
                        </button>
                    )}

                    {(!taskStatus || taskStatus.status === "completed" || taskStatus.status === "stopped") && autoIterateStatus?.status !== "running" && (
                        <button
                            onClick={onStartTask}
                            disabled={!fileInfo}
                            className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 px-6 py-2 rounded-lg font-medium transition-colors"
                        >
                            <Play size={18} /> {autoIterateConfig.enabled ? "启动自动迭代" : "启动任务"}
                        </button>
                    )}
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                <div className="space-y-4">
                    <label className="block text-sm font-medium text-slate-400">数据导入</label>
                    <div className="relative group">
                        <input type="file" onChange={onFileUpload} className="absolute inset-0 opacity-0 cursor-pointer" accept=".xlsx,.csv" />
                        <div className="border-2 border-dashed border-white/10 group-hover:border-blue-500/50 rounded-xl p-4 flex flex-col items-center justify-center gap-2 transition-all">
                            <Upload size={24} className="text-slate-500 group-hover:text-blue-400" />
                            <span className="text-sm text-slate-400 group-hover:text-slate-300">
                                {fileInfo ? fileInfo.filename : "点击上传 Excel/CSV (上千条支持)"}
                            </span>
                        </div>
                    </div>
                </div>
                <div className="space-y-4">
                    <label className="block text-sm font-medium text-slate-400">列映射配置</label>
                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-1">
                            <label className="block text-xs text-blue-400 font-medium">Query 输入列</label>
                            <select
                                value={config.query_col}
                                onChange={e => setConfig({ ...config, query_col: e.target.value })}
                                className="w-full bg-slate-900 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500 appearance-none cursor-pointer"
                            >
                                <option value="">选择列...</option>
                                {fileInfo?.columns.map((c: string) => <option key={c} value={c}>{c}</option>)}
                            </select>
                        </div>
                        <div className="space-y-1">
                            <label className="block text-xs text-emerald-400 font-medium">预期结果列</label>
                            <select
                                value={config.target_col}
                                onChange={e => setConfig({ ...config, target_col: e.target.value })}
                                className="w-full bg-slate-900 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500 appearance-none cursor-pointer"
                            >
                                <option value="">选择列...</option>
                                {fileInfo?.columns.map((c: string) => <option key={c} value={c}>{c}</option>)}
                            </select>
                        </div>
                    </div>
                </div>

                <div className="space-y-2">
                    <label className="block text-sm font-medium text-slate-400">JSON 字段提取 (可选)</label>
                    <input
                        type="text"
                        value={extractField}
                        onChange={e => setExtractField(e.target.value)}
                        className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
                        placeholder="例如: intent (如果模型输出是 JSON)"
                    />
                    <p className="text-xs text-slate-500">若模型输出为 {`{"intent": "咨询"}`}, 请填写 intent。留空则进行全文匹配。</p>
                </div>

                {/* 自动迭代配置 */}
                <div className="p-4 bg-purple-500/10 border border-purple-500/20 rounded-xl">
                    <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2">
                            <Rocket size={18} className="text-purple-400" />
                            <span className="text-sm font-bold text-purple-400">自动迭代优化</span>
                        </div>
                        <label className="relative inline-flex items-center cursor-pointer">
                            <input
                                type="checkbox"
                                checked={autoIterateConfig.enabled || false}
                                onChange={e => setAutoIterateConfig({ ...autoIterateConfig, enabled: e.target.checked })}
                                className="sr-only peer"
                            />
                            <div className="w-11 h-6 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-purple-600"></div>
                        </label>
                    </div>

                    {autoIterateConfig.enabled && (
                        <>
                            <p className="text-xs text-slate-400 mb-3">
                                开启后，点击"启动任务"将自动循环：执行→优化→执行，直到达到目标准确率或最大轮数
                            </p>
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-xs text-slate-400 mb-1">最大轮数</label>
                                    <input
                                        type="number"
                                        min={1}
                                        max={20}
                                        value={autoIterateConfig.maxRounds}
                                        onChange={e => setAutoIterateConfig({ ...autoIterateConfig, maxRounds: parseInt(e.target.value) || 5 })}
                                        className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm"
                                    />
                                </div>
                                <div>
                                    <label className="block text-xs text-slate-400 mb-1">目标准确率 (%)</label>
                                    <input
                                        type="number"
                                        min={50}
                                        max={100}
                                        value={autoIterateConfig.targetAccuracy}
                                        onChange={e => setAutoIterateConfig({ ...autoIterateConfig, targetAccuracy: parseInt(e.target.value) || 95 })}
                                        className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm"
                                    />
                                </div>
                            </div>

                            {autoIterateStatus?.status === "running" && (
                                <div className="mt-3 text-xs text-purple-300 bg-purple-500/20 p-2 rounded">
                                    {autoIterateStatus.message}
                                </div>
                            )}

                            {autoIterateStatus && autoIterateStatus.status !== "running" && autoIterateStatus.status !== "idle" && (
                                <div className={`mt-3 text-xs p-2 rounded ${autoIterateStatus.status === "completed" ? "bg-emerald-500/20 text-emerald-300" : "bg-red-500/20 text-red-300"}`}>
                                    {autoIterateStatus.message}
                                </div>
                            )}
                        </>
                    )}
                </div>
            </div>

            {/* Real-time Progress */}
            {taskStatus && (
                <div className="space-y-4 border-t border-white/10 pt-6">
                    <div className="flex justify-between items-end">
                        <div>
                            <span className="text-2xl font-bold text-blue-400">{taskStatus.current_index}</span>
                            <span className="text-slate-500 ml-2">/ {taskStatus.total_count} 已处理</span>
                        </div>
                        <div className="text-right">
                            <span className="text-sm font-medium text-slate-400">准确率: </span>
                            <span className="text-lg font-bold text-emerald-400">
                                {taskStatus.results?.length > 0
                                    ? (((taskStatus.results.length - taskStatus.errors.length) / taskStatus.results.length) * 100).toFixed(1)
                                    : "0.0"}%
                            </span>
                        </div>
                    </div>
                    <div className="h-3 bg-white/5 rounded-full overflow-hidden">
                        <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: `${(taskStatus.current_index / taskStatus.total_count) * 100}%` }}
                            className="h-full bg-gradient-to-r from-blue-500 to-emerald-500"
                        />
                    </div>
                    {taskStatus.status === "completed" && (
                        <div className="space-y-3">
                            <div className="flex gap-4">
                                <button
                                    onClick={onOptimize}
                                    disabled={isOptimizing || taskStatus.errors.length === 0}
                                    className="flex-1 flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 py-3 rounded-xl font-medium transition-colors shadow-lg shadow-blue-900/20"
                                >
                                    {isOptimizing ? <RefreshCw className="animate-spin" size={20} /> : <RefreshCw size={20} />}
                                    一键智能优化
                                </button>
                                <button
                                    onClick={() => setShowExternalOptimize(true)}
                                    disabled={taskStatus.errors.length === 0}
                                    className="flex items-center justify-center gap-2 bg-orange-600 hover:bg-orange-500 disabled:opacity-50 px-4 rounded-xl font-medium transition-colors"
                                >
                                    <Copy size={20} /> 外部优化
                                </button>
                                <button
                                    onClick={() => window.open(`${API_BASE}/tasks/${taskStatus.id}/export`)}
                                    className="flex items-center justify-center gap-2 bg-white/5 hover:bg-white/10 border border-white/10 px-4 rounded-xl font-medium transition-colors"
                                >
                                    <Download size={20} /> 导出
                                </button>
                            </div>

                            {/* 外部优化面板 */}
                            {showExternalOptimize && (
                                <div className="p-4 bg-orange-500/10 border border-orange-500/20 rounded-xl space-y-3">
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-2">
                                            <Copy size={16} className="text-orange-400" />
                                            <span className="text-sm font-bold text-orange-400">外部模型优化</span>
                                        </div>
                                        <button onClick={() => setShowExternalOptimize(false)} className="text-slate-400 hover:text-white">
                                            <X size={16} />
                                        </button>
                                    </div>

                                    <div className="text-xs text-slate-400">
                                        1. 点击"复制上下文"将优化请求复制到剪贴板<br />
                                        2. 去外部模型（如ChatGPT、Claude等）粘贴并获取优化结果<br />
                                        3. 将优化后的提示词粘贴到下方输入框并应用
                                    </div>

                                    <button
                                        onClick={onCopyOptimizeContext}
                                        className="w-full flex items-center justify-center gap-2 bg-orange-600 hover:bg-orange-500 py-2 rounded-lg text-sm font-medium transition-colors"
                                    >
                                        <Copy size={16} /> 复制优化上下文
                                    </button>

                                    <textarea
                                        value={externalPrompt}
                                        onChange={e => setExternalPrompt(e.target.value)}
                                        placeholder="在此粘贴外部模型优化后的提示词..."
                                        className="w-full h-32 bg-white/5 border border-white/10 rounded-lg p-3 text-sm resize-none focus:outline-none focus:border-orange-500"
                                    />

                                    <button
                                        onClick={onApplyExternalOptimize}
                                        disabled={!externalPrompt.trim()}
                                        className="w-full flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 py-2 rounded-lg text-sm font-medium transition-colors"
                                    >
                                        <ClipboardPaste size={16} /> 应用优化结果
                                    </button>
                                </div>
                            )}
                        </div>
                    )}

                    {/* 错误信息展示区域 */}
                    {taskStatus.errors?.length > 0 && (
                        <div className="mt-4 p-4 bg-red-500/10 border border-red-500/20 rounded-xl">
                            <div className="flex items-center gap-2 mb-3">
                                <AlertCircle size={18} className="text-red-500" />
                                <span className="font-medium text-red-400">
                                    错误信息 ({taskStatus.errors.length} 条)
                                </span>
                            </div>
                            <div className="space-y-2 max-h-48 overflow-y-auto custom-scrollbar">
                                {taskStatus.errors.slice(0, 10).map((err: any, idx: number) => (
                                    <div key={idx} className="text-xs bg-black/20 rounded-lg p-3">
                                        <div className="flex justify-between items-start mb-1">
                                            <span className="text-red-400 font-medium">#{err.index + 1}</span>
                                            <span className="text-slate-500 text-[10px]">Query: {err.query?.substring(0, 30)}...</span>
                                        </div>
                                        <div className="text-slate-400">
                                            <span className="text-slate-500">预期: </span>{err.target}
                                            <span className="mx-2 text-slate-600">→</span>
                                            <span className="text-slate-500">实际: </span>
                                            <span className="text-red-300">{err.output}</span>
                                        </div>
                                    </div>
                                ))}
                                {taskStatus.errors.length > 10 && (
                                    <p className="text-center text-slate-500 text-xs pt-2">
                                        还有 {taskStatus.errors.length - 10} 条错误，请导出查看完整列表
                                    </p>
                                )}
                            </div>
                        </div>
                    )}
                </div>
            )}
        </section>
    );
}
