import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import axios from "axios";
import {
    Play, Pause, Square, Upload, RefreshCw, Download,
    CheckCircle2, AlertCircle, ChevronDown, ChevronUp,
    History, Rocket, XCircle, Copy, X, ClipboardPaste, Settings
} from "lucide-react";
import MultiRoundConfig, { RoundConfig } from "../multi-round/_components/MultiRoundConfig";

const API_BASE = "/api";

interface FileInfo {
    file_id: string;
    filename: string;
    row_count: number;
    columns: string[];
}

interface TaskStatus {
    id: string;
    status: "pending" | "running" | "paused" | "completed" | "stopped";
    current_round: number;
    total_rounds: number;
    current_index: number;
    total_count: number;
    round_results?: RoundResult[];
    results?: any[];
    errors?: any[];
    results_count?: number;
    errors_count?: number;
}

interface RoundResult {
    round: number;
    total: number;
    correct: number;
    accuracy: number;
    results: any[];
}

interface MultiRoundExecutionPanelProps {
    projectId: string;
    project: any;
    prompt: string;
    onProjectUpdate: () => void;
    showToast: (message: string, type?: "success" | "error") => void;
    // 多轮配置变化回调
    onMultiRoundConfigChange?: (config: {
        roundsConfig: RoundConfig[];
        intentExtractField: string;
        responseExtractField: string;
        validationLimit: number | "";
        fileInfo: FileInfo | null;
    }) => void;
    // 优化相关
    onOptimize: () => void;
    onStopOptimize?: () => void;
    isOptimizing: boolean;
    optimizationStatus: any;
    onCopyOptimizeContext: () => void;
    // 自动迭代
    autoIterateConfig: { enabled: boolean; maxRounds: number | ""; targetAccuracy: number | ""; strategy: "simple" | "multi" };
    setAutoIterateConfig: (config: any) => void;
    autoIterateStatus: any;
    isAutoIterating: boolean;
    onStartAutoIterate: () => void;
    onStopAutoIterate: () => void;
    // 任务状态（外部管理）
    taskStatus: TaskStatus | null;
    setTaskStatus: (status: TaskStatus | null) => void;
}

export default function MultiRoundExecutionPanel({
    projectId,
    project,
    prompt,
    onProjectUpdate,
    showToast,
    onMultiRoundConfigChange,
    onOptimize,
    onStopOptimize,
    isOptimizing,
    optimizationStatus,
    onCopyOptimizeContext,
    autoIterateConfig,
    setAutoIterateConfig,
    autoIterateStatus,
    isAutoIterating,
    onStartAutoIterate,
    onStopAutoIterate,
    taskStatus,
    setTaskStatus
}: MultiRoundExecutionPanelProps) {
    // 文件信息
    const [fileInfo, setFileInfo] = useState<FileInfo | null>(null);

    // 轮次配置
    const [roundsConfig, setRoundsConfig] = useState<RoundConfig[]>([
        { round: 1, query_col: "", target_col: "" },
        { round: 2, query_col: "", target_col: "" }
    ]);
    const [isDetecting, setIsDetecting] = useState(false);

    // 提取配置
    const [intentExtractField, setIntentExtractField] = useState("");
    const [responseExtractField, setResponseExtractField] = useState("");

    // 验证配置
    const [validationLimit, setValidationLimit] = useState<number | "">("");
    // 保存上次的 Top N 值，用于切换时恢复
    const [lastTopNValue, setLastTopNValue] = useState<number>(50);

    // 结果
    const [roundResults, setRoundResults] = useState<RoundResult[]>([]);
    const pollingRef = useRef<NodeJS.Timeout | null>(null);

    // UI 状态
    const [expandedRounds, setExpandedRounds] = useState<Set<number>>(new Set([1]));
    const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
    const [showExternalOptimize, setShowExternalOptimize] = useState(false);
    const [externalPrompt, setExternalPrompt] = useState("");
    const [strategy, setStrategy] = useState<"simple" | "multi">("multi");

    // 从项目配置恢复状态
    useEffect(() => {
        if (project?.config) {
            const config = project.config;
            if (config.multi_round_config) {
                const mrc = config.multi_round_config;
                if (mrc.rounds_config) setRoundsConfig(mrc.rounds_config);
                if (mrc.intent_extract_field) setIntentExtractField(mrc.intent_extract_field);
                if (mrc.response_extract_field) setResponseExtractField(mrc.response_extract_field);
                if (mrc.validation_limit !== undefined && mrc.validation_limit !== "") {
                    setValidationLimit(mrc.validation_limit);
                    // 同时保存到 lastTopNValue，用于切换时恢复
                    setLastTopNValue(mrc.validation_limit);
                }
            }
            if (config.multi_round_file_info) {
                setFileInfo(config.multi_round_file_info);
            }
        }
    }, [project?.config]);

    // 配置变化时通知父组件
    useEffect(() => {
        if (onMultiRoundConfigChange) {
            onMultiRoundConfigChange({
                roundsConfig,
                intentExtractField,
                responseExtractField,
                validationLimit,
                fileInfo
            });
        }
    }, [roundsConfig, intentExtractField, responseExtractField, validationLimit, fileInfo]);

    // 轮询任务状态
    useEffect(() => {
        if (taskStatus?.status === "running" || taskStatus?.status === "paused") {
            pollingRef.current = setInterval(async () => {
                try {
                    const res = await axios.get(`${API_BASE}/tasks/${taskStatus.id}?include_results=true`);
                    const data = res.data;

                    setTaskStatus({
                        id: data.id,
                        status: data.status,
                        current_round: data.current_round || 1,
                        total_rounds: data.total_rounds || roundsConfig.length,
                        current_index: data.current_index || 0,
                        total_count: data.total_count || 0,
                        results: data.results,
                        errors: data.errors,
                        results_count: data.results_count,
                        errors_count: data.errors_count
                    });

                    if (data.round_results) {
                        setRoundResults(data.round_results);
                    }

                    if (data.status === "completed" || data.status === "stopped") {
                        if (pollingRef.current) {
                            clearInterval(pollingRef.current);
                            pollingRef.current = null;
                        }
                    }
                } catch (err) {
                    console.error("轮询任务状态失败:", err);
                }
            }, 2000);
        }

        return () => {
            if (pollingRef.current) {
                clearInterval(pollingRef.current);
                pollingRef.current = null;
            }
        };
    }, [taskStatus?.id, taskStatus?.status]);

    // 文件上传
    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        const formData = new FormData();
        formData.append("file", file);

        try {
            const res = await axios.post(`${API_BASE}/upload`, formData);
            setFileInfo(res.data);
            showToast(`文件上传成功: ${res.data.row_count} 行数据`);
            await saveConfig({ multi_round_file_info: res.data });
        } catch (err) {
            console.error("文件上传失败:", err);
            showToast("文件上传失败", "error");
        }
    };

    // 自动检测多轮列
    const handleAutoDetect = async () => {
        if (!fileInfo) return;

        setIsDetecting(true);
        try {
            const formData = new FormData();
            formData.append("file_id", fileInfo.file_id);

            const res = await axios.post(`${API_BASE}/upload/detect-multi-round`, formData);

            if (res.data.detected) {
                const newConfig: RoundConfig[] = res.data.rounds_config.map((cfg: any) => ({
                    round: cfg.round,
                    query_col: cfg.query_col || "",
                    target_col: cfg.target_col || ""
                }));
                setRoundsConfig(newConfig);
                showToast(`检测到 ${res.data.max_rounds} 轮配置`);
                await saveConfigWithRounds(newConfig);
            } else {
                showToast("正则匹配未检测到，正在使用 AI 智能分析...");

                const llmFormData = new FormData();
                llmFormData.append("file_id", fileInfo.file_id);
                llmFormData.append("project_id", projectId);

                const llmRes = await axios.post(`${API_BASE}/upload/detect-multi-round-llm`, llmFormData);

                if (llmRes.data.detected) {
                    const newConfig: RoundConfig[] = llmRes.data.rounds_config.map((cfg: any) => ({
                        round: cfg.round,
                        query_col: cfg.query_col || "",
                        target_col: cfg.target_col || ""
                    }));
                    setRoundsConfig(newConfig);
                    showToast(`AI 检测到 ${llmRes.data.max_rounds} 轮配置`);
                    await saveConfigWithRounds(newConfig);
                } else {
                    const reason = llmRes.data.reasoning || llmRes.data.error || "无法识别多轮对话结构";
                    showToast(`未检测到多轮列配置: ${reason}`, "error");
                }
            }
        } catch (err) {
            console.error("自动检测失败:", err);
            showToast("自动检测失败", "error");
        } finally {
            setIsDetecting(false);
        }
    };

    // 保存配置
    const saveConfig = async (extraConfig: any = {}) => {
        try {
            const currentConfig = project?.config || {};
            await axios.put(`${API_BASE}/projects/${projectId}`, {
                current_prompt: prompt,
                config: {
                    ...currentConfig,
                    multi_round_config: {
                        rounds_config: roundsConfig,
                        intent_extract_field: intentExtractField,
                        response_extract_field: responseExtractField,
                        validation_limit: validationLimit
                    },
                    ...extraConfig
                }
            });
        } catch (err) {
            console.error("保存配置失败:", err);
        }
    };

    const saveConfigWithRounds = async (rounds: RoundConfig[], extraConfig: any = {}) => {
        try {
            const currentConfig = project?.config || {};
            await axios.put(`${API_BASE}/projects/${projectId}`, {
                current_prompt: prompt,
                config: {
                    ...currentConfig,
                    multi_round_config: {
                        rounds_config: rounds,
                        intent_extract_field: intentExtractField,
                        response_extract_field: responseExtractField,
                        validation_limit: validationLimit
                    },
                    ...extraConfig
                }
            });
        } catch (err) {
            console.error("保存配置失败:", err);
        }
    };

    // 启动任务
    const handleStartTask = async () => {
        if (!fileInfo) {
            showToast("请先上传数据文件", "error");
            return;
        }

        for (const cfg of roundsConfig) {
            if (!cfg.query_col || !cfg.target_col) {
                showToast(`请配置第 ${cfg.round} 轮的 Query 列和 Target 列`, "error");
                return;
            }
        }

        if (!intentExtractField) {
            showToast("请配置意图提取路径", "error");
            return;
        }

        if (!responseExtractField) {
            showToast("请配置回复内容提取路径", "error");
            return;
        }

        // 验证项目配置中的接口配置
        const modelConfig = project?.model_config;
        if (!modelConfig?.base_url) {
            showToast("请先在【项目配置】-【验证配置】中设置 API 地址", "error");
            return;
        }

        if (!modelConfig?.interface_code) {
            showToast("请先在【项目配置】-【验证配置】中设置参数转换脚本", "error");
            return;
        }

        // 如果启用了自动迭代，调用自动迭代
        if (autoIterateConfig.enabled) {
            await saveConfig();
            onStartAutoIterate();
            return;
        }

        try {
            const formData = new FormData();
            formData.append("project_id", projectId);
            formData.append("file_id", fileInfo.file_id);
            formData.append("prompt", prompt);
            formData.append("rounds_config", JSON.stringify(roundsConfig));
            formData.append("intent_extract_field", intentExtractField);
            formData.append("response_extract_field", responseExtractField);
            if (fileInfo.filename) formData.append("original_filename", fileInfo.filename);
            if (validationLimit) formData.append("validation_limit", validationLimit.toString());

            // 构建 api_config 从项目的 model_config 中提取
            const apiConfig = {
                api_url: modelConfig.base_url,
                api_headers: modelConfig.api_headers || "{}",
                api_timeout: modelConfig.timeout || 60,
                request_template: modelConfig.interface_code || "{}",
                concurrency: modelConfig.concurrency || 5
            };
            formData.append("api_config", JSON.stringify(apiConfig));

            const res = await axios.post(`${API_BASE}/tasks/start-multi-round`, formData);

            const rowCount = validationLimit ? Math.min(Number(validationLimit), fileInfo.row_count) : fileInfo.row_count;
            setTaskStatus({
                id: res.data.task_id,
                status: "running",
                current_round: 1,
                total_rounds: roundsConfig.length,
                current_index: 0,
                total_count: rowCount * roundsConfig.length
            });
            setRoundResults([]);
            showToast("多轮验证任务已启动");
            await saveConfig();
        } catch (err: any) {
            console.error("启动任务失败:", err);
            showToast(err.response?.data?.detail || "启动任务失败", "error");
        }
    };

    // 控制任务
    const handleControlTask = async (action: "pause" | "resume" | "stop") => {
        if (!taskStatus?.id) return;

        try {
            await axios.post(`${API_BASE}/tasks/${taskStatus.id}/${action}`);
            setTaskStatus({
                ...taskStatus,
                status: action === "pause" ? "paused" : action === "resume" ? "running" : "stopped"
            });
            const actionText = action === "pause" ? "暂停" : action === "resume" ? "继续" : "停止";
            showToast(`任务已${actionText}`);
        } catch (err) {
            console.error(`${action}任务失败:`, err);
            showToast(`${action}任务失败`, "error");
        }
    };

    // 导出结果
    const handleExport = () => {
        if (!taskStatus?.id) return;
        window.open(`${API_BASE}/tasks/${taskStatus.id}/export`);
    };

    // 计算总体准确率
    const totalAccuracy = roundResults.length > 0 ? (() => {
        const totalCorrect = roundResults.reduce((sum, r) => sum + r.correct, 0);
        const totalCount = roundResults.reduce((sum, r) => sum + r.total, 0);
        if (totalCount === 0) return 0;
        return (totalCorrect / totalCount * 100).toFixed(1);
    })() : 0;

    // 切换展开
    const toggleRoundExpand = (round: number) => {
        const newExpanded = new Set(expandedRounds);
        if (newExpanded.has(round)) {
            newExpanded.delete(round);
        } else {
            newExpanded.add(round);
        }
        setExpandedRounds(newExpanded);
    };

    const toggleRowExpand = (key: string) => {
        const newExpanded = new Set(expandedRows);
        if (newExpanded.has(key)) {
            newExpanded.delete(key);
        } else {
            newExpanded.add(key);
        }
        setExpandedRows(newExpanded);
    };

    // 获取错误数量
    const errorsCount = taskStatus?.errors_count ?? taskStatus?.errors?.length ?? 0;

    return (
        <section className="glass p-6 rounded-2xl">
            {/* 标题和控制按钮 */}
            <div className="flex justify-between items-center mb-6">
                <h2 className="text-lg font-semibold flex items-center gap-2">
                    <Rocket size={20} className="text-purple-400" />
                    多轮验证执行
                </h2>
                <div className="flex gap-2">
                    {taskStatus?.status === "running" && !isAutoIterating && (
                        <button onClick={() => handleControlTask("pause")} className="flex items-center gap-2 bg-amber-500/10 text-amber-500 hover:bg-amber-500/20 px-4 py-2 rounded-lg font-medium transition-colors">
                            <Pause size={18} /> 暂停
                        </button>
                    )}
                    {taskStatus?.status === "paused" && !isAutoIterating && (
                        <button onClick={() => handleControlTask("resume")} className="flex items-center gap-2 bg-blue-500/10 text-blue-500 hover:bg-blue-500/20 px-4 py-2 rounded-lg font-medium transition-colors">
                            <Play size={18} /> 继续
                        </button>
                    )}
                    {(isAutoIterating || taskStatus?.status === "running" || taskStatus?.status === "paused") && (
                        <button
                            onClick={() => isAutoIterating ? onStopAutoIterate() : handleControlTask("stop")}
                            className="flex items-center gap-2 bg-red-500/10 text-red-500 hover:bg-red-500/20 px-4 py-2 rounded-lg font-medium transition-colors"
                        >
                            <Square size={18} /> 终止任务
                        </button>
                    )}
                    {(!taskStatus || taskStatus.status === "completed" || taskStatus.status === "stopped") && !isOptimizing && (
                        <button
                            onClick={handleStartTask}
                            disabled={!fileInfo}
                            className="flex items-center gap-2 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 px-6 py-2 rounded-lg font-medium transition-colors"
                        >
                            <Play size={18} /> {autoIterateConfig.enabled ? "启动自动迭代" : "启动验证"}
                        </button>
                    )}
                </div>
            </div>

            {/* 第一行：数据导入 + 轮次配置 */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
                {/* 数据导入卡片 */}
                <div className="bg-slate-800/40 border border-white/5 rounded-xl p-4">
                    <label className="block text-sm font-medium text-slate-400 mb-3">数据导入</label>
                    <div className="relative group">
                        <input
                            type="file"
                            onChange={handleFileUpload}
                            onClick={(e) => { (e.target as HTMLInputElement).value = ""; }}
                            className="absolute inset-0 opacity-0 cursor-pointer"
                            accept=".xlsx,.csv"
                        />
                        <div className="border-2 border-dashed border-white/10 group-hover:border-purple-500/50 rounded-xl p-4 flex flex-col items-center justify-center gap-2 transition-all min-h-[80px]">
                            <Upload size={20} className="text-slate-500 group-hover:text-purple-400" />
                            <span className="text-sm text-slate-400 group-hover:text-slate-300 text-center">
                                {fileInfo ? `${fileInfo.filename} (${fileInfo.row_count} 行)` : "点击上传 Excel/CSV"}
                            </span>
                        </div>
                    </div>
                </div>

                {/* 验证配置卡片 */}
                <div className="bg-slate-800/40 border border-white/5 rounded-xl p-4">
                    <label className="block text-sm font-medium text-slate-400 mb-3">验证配置</label>
                    <div className="space-y-4">
                        {/* 模式切换 */}
                        <div className="flex items-center justify-between">
                            <span className="text-xs text-slate-500">数据范围（每轮行数）</span>
                            <div className="flex bg-black/20 p-1 rounded-lg">
                                <button
                                    onClick={() => {
                                        // 切换到全部数据前，保存当前的 Top N 值
                                        if (validationLimit !== "") {
                                            setLastTopNValue(validationLimit as number);
                                        }
                                        setValidationLimit("");
                                    }}
                                    className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${validationLimit === "" ? "bg-slate-600 text-white shadow" : "text-slate-400 hover:text-slate-300"}`}
                                >
                                    全部数据
                                </button>
                                <button
                                    onClick={() => {
                                        // 切换到 Top N 时，恢复之前保存的值
                                        if (validationLimit === "") {
                                            setValidationLimit(lastTopNValue);
                                        }
                                    }}
                                    className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${validationLimit !== "" ? "bg-purple-600 text-white shadow" : "text-slate-400 hover:text-slate-300"}`}
                                >
                                    Top N
                                </button>
                            </div>
                        </div>

                        {/* Slider & Input Config */}
                        {validationLimit !== "" && (
                            <motion.div
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: "auto" }}
                                className="space-y-2"
                            >
                                <div className="flex items-center gap-3">
                                    <input
                                        type="range"
                                        min="1"
                                        max={fileInfo?.row_count || 100}
                                        step="1"
                                        value={validationLimit || 50}
                                        onChange={(e) => {
                                            const val = parseInt(e.target.value);
                                            setValidationLimit(val);
                                            setLastTopNValue(val);
                                        }}
                                        className="flex-1 accent-purple-500 h-1.5 bg-white/10 rounded-lg appearance-none cursor-pointer"
                                    />
                                    <input
                                        type="number"
                                        min="1"
                                        max={fileInfo?.row_count || 9999}
                                        value={validationLimit}
                                        onChange={(e) => {
                                            const val = parseInt(e.target.value);
                                            const newVal = isNaN(val) ? 1 : val;
                                            setValidationLimit(newVal);
                                            setLastTopNValue(newVal);
                                        }}
                                        className="w-16 bg-slate-900 border border-white/10 rounded-lg px-2 py-1 text-sm text-center focus:border-purple-500 outline-none"
                                    />
                                </div>
                                <div className="flex justify-between text-[10px] text-slate-600 px-1 font-mono">
                                    <span>1</span>
                                    <span>{fileInfo?.row_count || "?"}</span>
                                </div>
                            </motion.div>
                        )}
                        {validationLimit === "" && (
                            <p className="text-[10px] text-slate-500 leading-relaxed">
                                使用文件中所有数据进行多轮验证。<br />
                                <span className="text-slate-600">每条数据将执行 {roundsConfig.length} 轮对话。</span>
                            </p>
                        )}
                    </div>
                </div>
            </div>

            {/* 轮次配置 + 提取配置 */}
            <div className="mb-4">
                <MultiRoundConfig
                    roundsConfig={roundsConfig}
                    onRoundsConfigChange={setRoundsConfig}
                    availableColumns={fileInfo?.columns || []}
                    onAutoDetect={handleAutoDetect}
                    isDetecting={isDetecting}
                    intentExtractField={intentExtractField}
                    onIntentExtractFieldChange={setIntentExtractField}
                    responseExtractField={responseExtractField}
                    onResponseExtractFieldChange={setResponseExtractField}
                    projectId={projectId}
                    showToast={showToast}
                />
            </div>

            {/* 自动迭代配置 */}
            <div className="bg-purple-500/10 border border-purple-500/20 rounded-xl p-4 mb-4">
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
                                    value={autoIterateConfig.maxRounds}
                                    onChange={e => {
                                        const val = parseInt(e.target.value);
                                        setAutoIterateConfig({ ...autoIterateConfig, maxRounds: isNaN(val) ? "" : val });
                                    }}
                                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm"
                                />
                            </div>
                            <div>
                                <label className="block text-xs text-slate-400 mb-1">目标准确率 (%)</label>
                                <input
                                    type="number"
                                    min={1}
                                    max={100}
                                    value={autoIterateConfig.targetAccuracy}
                                    onChange={e => {
                                        const val = parseInt(e.target.value);
                                        setAutoIterateConfig({ ...autoIterateConfig, targetAccuracy: isNaN(val) ? "" : val });
                                    }}
                                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm"
                                />
                            </div>
                        </div>

                        {autoIterateStatus?.status === "running" && (
                            <div className="mt-3 text-xs text-purple-300 bg-purple-500/20 p-2 rounded">
                                {autoIterateStatus.message}
                            </div>
                        )}
                    </>
                )}
            </div>

            {/* 实时进度 */}
            {taskStatus && (
                <div className="space-y-4 border-t border-white/10 pt-6">
                    <div className="flex justify-between items-center mb-3">
                        <span className="text-sm font-medium text-slate-400">执行进度</span>
                        <div className="flex items-center gap-2">
                            {taskStatus.status === "running" && (
                                <RefreshCw size={16} className="text-purple-400 animate-spin" />
                            )}
                            <span className={`text-sm px-2 py-0.5 rounded ${
                                taskStatus.status === "completed" ? "bg-emerald-500/20 text-emerald-400" :
                                taskStatus.status === "running" ? "bg-purple-500/20 text-purple-400" :
                                taskStatus.status === "paused" ? "bg-amber-500/20 text-amber-400" :
                                "bg-slate-500/20 text-slate-400"
                            }`}>
                                {taskStatus.status === "completed" ? "已完成" :
                                 taskStatus.status === "running" ? `第 ${taskStatus.current_round}/${taskStatus.total_rounds} 轮` :
                                 taskStatus.status === "paused" ? "已暂停" : "已停止"}
                            </span>
                        </div>
                    </div>

                    {/* 进度条 */}
                    <div className="h-3 bg-white/5 rounded-full overflow-hidden">
                        <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: `${taskStatus.total_count > 0 ? (taskStatus.current_index / taskStatus.total_count * 100) : 0}%` }}
                            className="h-full bg-gradient-to-r from-purple-500 to-blue-500"
                        />
                    </div>

                    {/* 统计信息 */}
                    <div className="grid grid-cols-3 gap-4 text-center">
                        <div>
                            <div className="text-2xl font-bold text-white">
                                {taskStatus.current_index}/{taskStatus.total_count}
                            </div>
                            <div className="text-xs text-slate-500">总验证次数</div>
                        </div>
                        <div>
                            <div className="text-2xl font-bold text-emerald-400">{totalAccuracy}%</div>
                            <div className="text-xs text-slate-500">总体准确率</div>
                        </div>
                        <div>
                            <div className="text-2xl font-bold text-purple-400">
                                {taskStatus.current_round}/{taskStatus.total_rounds}
                            </div>
                            <div className="text-xs text-slate-500">当前轮次</div>
                        </div>
                    </div>

                    {/* 任务完成后的操作按钮 */}
                    {(taskStatus.status === "completed" || taskStatus.status === "stopped") && (
                        <div className="space-y-3 pt-4 border-t border-white/10">
                            <div className="flex gap-4">
                                {isOptimizing ? (
                                    <button
                                        onClick={onStopOptimize}
                                        className="flex-1 flex items-center justify-center gap-2 bg-red-600 hover:bg-red-500 py-3 rounded-xl font-medium transition-colors"
                                    >
                                        <XCircle size={20} />
                                        停止优化
                                    </button>
                                ) : (
                                    <button
                                        onClick={onOptimize}
                                        disabled={errorsCount === 0 || isAutoIterating}
                                        className="flex-1 flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed py-3 rounded-xl font-medium transition-colors"
                                    >
                                        <RefreshCw size={20} />
                                        一键智能优化
                                    </button>
                                )}

                                <button
                                    onClick={() => {
                                        setShowExternalOptimize(true);
                                        onCopyOptimizeContext();
                                    }}
                                    disabled={errorsCount === 0 || isAutoIterating}
                                    className="flex items-center justify-center gap-2 bg-orange-600 hover:bg-orange-500 disabled:opacity-50 disabled:cursor-not-allowed px-4 rounded-xl font-medium transition-colors"
                                >
                                    <Copy size={20} /> 外部优化
                                </button>

                                <button
                                    onClick={handleExport}
                                    className="flex items-center justify-center gap-2 bg-white/5 hover:bg-white/10 border border-white/10 px-4 rounded-xl font-medium transition-colors"
                                >
                                    <Download size={20} /> 导出
                                </button>
                            </div>

                            {isOptimizing && optimizationStatus?.message && (
                                <div className="text-xs text-blue-300 bg-blue-500/20 p-2 rounded-lg flex items-center gap-2">
                                    <RefreshCw size={14} className="animate-spin" />
                                    {optimizationStatus.message}
                                </div>
                            )}
                        </div>
                    )}
                </div>
            )}

            {/* 每轮结果 */}
            {roundResults.length > 0 && (
                <div className="space-y-3 mt-6 border-t border-white/10 pt-6">
                    <h3 className="text-sm font-medium text-slate-400 mb-3">轮次结果</h3>
                    {roundResults.map((roundResult) => (
                        <div key={roundResult.round} className="bg-slate-800/40 rounded-xl overflow-hidden">
                            <button
                                onClick={() => toggleRoundExpand(roundResult.round)}
                                className="w-full p-4 flex justify-between items-center hover:bg-white/5 transition-colors"
                            >
                                <div className="flex items-center gap-3">
                                    <span className="text-sm font-medium">第 {roundResult.round} 轮</span>
                                    <span className={`text-xs px-2 py-0.5 rounded ${
                                        roundResult.accuracy >= 90 ? "bg-emerald-500/20 text-emerald-400" :
                                        roundResult.accuracy >= 70 ? "bg-amber-500/20 text-amber-400" :
                                        "bg-red-500/20 text-red-400"
                                    }`}>
                                        {roundResult.accuracy.toFixed(1)}%
                                    </span>
                                    <span className="text-xs text-slate-500">
                                        {roundResult.correct}/{roundResult.total}
                                    </span>
                                </div>
                                {expandedRounds.has(roundResult.round) ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                            </button>

                            {expandedRounds.has(roundResult.round) && (
                                <div className="border-t border-white/5 p-3 space-y-2 max-h-[300px] overflow-y-auto">
                                    {roundResult.results.length === 0 ? (
                                        <div className="text-center py-4 text-emerald-400 text-sm">
                                            <CheckCircle2 size={20} className="mx-auto mb-2" />
                                            本轮全部正确
                                        </div>
                                    ) : (
                                        <>
                                            <div className="text-xs text-slate-500 mb-2">
                                                错误数据 ({roundResult.results.length} 条)
                                            </div>
                                            {roundResult.results.map((result, idx) => {
                                                const rowKey = `${roundResult.round}-${idx}`;
                                                return (
                                                    <div
                                                        key={rowKey}
                                                        className="p-2 rounded-lg border bg-red-500/5 border-red-500/20"
                                                    >
                                                        <div
                                                            className="flex items-start gap-2 cursor-pointer"
                                                            onClick={() => toggleRowExpand(rowKey)}
                                                        >
                                                            <AlertCircle size={14} className="text-red-400 mt-0.5 flex-shrink-0" />
                                                            <div className="flex-1 min-w-0">
                                                                <div className="text-xs text-white truncate">{result.query}</div>
                                                            </div>
                                                            {expandedRows.has(rowKey) ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                                                        </div>

                                                        {expandedRows.has(rowKey) && (
                                                            <div className="mt-2 pt-2 border-t border-white/5 space-y-1 text-xs">
                                                                <div>
                                                                    <span className="text-slate-500">期望意图:</span>
                                                                    <span className="ml-2 text-emerald-400">{result.target}</span>
                                                                </div>
                                                                <div>
                                                                    <span className="text-slate-500">识别意图:</span>
                                                                    <span className="ml-2 text-red-400">
                                                                        {result.extracted_intent || "N/A"}
                                                                    </span>
                                                                </div>
                                                                <div>
                                                                    <span className="text-slate-500">回复内容:</span>
                                                                    <span className="ml-2 text-slate-400">
                                                                        {result.extracted_response?.slice(0, 100) || "N/A"}
                                                                        {result.extracted_response?.length > 100 ? "..." : ""}
                                                                    </span>
                                                                </div>
                                                                <div className="text-slate-500">
                                                                    耗时: {result.latency_ms}ms
                                                                </div>
                                                            </div>
                                                        )}
                                                    </div>
                                                );
                                            })}
                                        </>
                                    )}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}

            {/* 空状态 */}
            {!taskStatus && (
                <div className="text-center py-8 border-t border-white/10 mt-6">
                    <History size={48} className="mx-auto text-slate-600 mb-4" />
                    <p className="text-slate-500">上传数据文件并配置轮次后，点击启动开始多轮验证</p>
                    <p className="text-xs text-slate-600 mt-2">
                        数据格式: query1, target1, query2, target2, ...
                    </p>
                </div>
            )}
        </section>
    );
}
