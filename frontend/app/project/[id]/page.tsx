"use client";

import { useState, useEffect, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import axios from "axios";
import { motion } from "framer-motion";
import ModelConfig from "@/app/components/ModelConfig";

import ProjectHeader from "./_components/ProjectHeader";
import PromptEditor from "./_components/PromptEditor";
import ExecutionPanel from "./_components/ExecutionPanel";
import HistoryPanel from "./_components/HistoryPanel";
import LogDetailModal from "./_components/LogDetailModal";
import IterationDetailModal from "./_components/IterationDetailModal";
import KnowledgeDetailModal from "./_components/KnowledgeDetailModal";
import TestOutputModal from "@/app/components/TestOutputModal";

// 统一使用相对路径
const API_BASE = "/api";

export default function ProjectDetail() {
    const { id } = useParams();
    const [project, setProject] = useState<any>(null);
    const [fileInfo, setFileInfo] = useState<any>(null);
    const [config, setConfig] = useState<{ query_col: string; target_col: string; reason_col?: string }>({ query_col: "", target_col: "", reason_col: "" });
    const [taskStatus, setTaskStatus] = useState<any>(null);
    const [isOptimizing, setIsOptimizing] = useState(false);
    const [showConfig, setShowConfig] = useState(false);
    const [configTab, setConfigTab] = useState<"verification" | "optimization">("verification");
    const [extractField, setExtractField] = useState("");
    const [showTestModal, setShowTestModal] = useState(false);
    const [selectedLog, setSelectedLog] = useState<any>(null);
    const [isSaving, setIsSaving] = useState(false);
    // taskHistory is fetched but not used in the render? Ah, it was used to "restore recent task".
    // Wait, the original code had `setTaskHistory(tasksRes.data.tasks || []);` but didn't render it.
    // Ah, HistoryPanel uses `project.iterations`. The `taskHistory` might be redundant or I missed where it was used.
    // Looking at original code: `const [taskHistory, setTaskHistory] = useState<any[]>([]);`
    // It was never used in the JSX. `activeTab === "history"` used `project.iterations`.
    // So I can probably remove `taskHistory` state or keep it if I want to be safe. I'll keep the fetch but maybe not the state if it's unused.
    // Actually, let's keep it to be safe.
    const [taskHistory, setTaskHistory] = useState<any[]>([]);
    const [selectedIteration, setSelectedIteration] = useState<any>(null);
    const [validationLimit, setValidationLimit] = useState<number | "">("");

    // Auto-iterate config
    const [autoIterateConfig, setAutoIterateConfig] = useState<{
        enabled: boolean;
        maxRounds: number | "";
        targetAccuracy: number | "";
        strategy: "simple" | "multi";
    }>({
        enabled: false,
        maxRounds: 5,
        targetAccuracy: 95,
        strategy: "multi"
    });
    const [autoIterateStatus, setAutoIterateStatus] = useState<any>(null);

    // 知识库状态
    const [knowledgeRecords, setKnowledgeRecords] = useState<any[]>([]);
    const [selectedKnowledge, setSelectedKnowledge] = useState<any>(null);

    const [showExternalOptimize, setShowExternalOptimize] = useState(false);
    const [externalPrompt, setExternalPrompt] = useState("");
    // 存储从后端获取的优化上下文
    const [optimizeContext, setOptimizeContext] = useState<string>("");
    const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);

    const showToast = (message: string, type: "success" | "error" = "success") => {
        setToast({ message, type });
        setTimeout(() => setToast(null), 3000);
    };

    useEffect(() => {
        fetchProject();
        pollAutoIterateStatus();
    }, [id]);

    useEffect(() => {
        let timer: any;
        // Only poll independent task status if NOT auto-iterating (auto-iterate poller handles it)
        if (taskStatus?.status === "running" && autoIterateStatus?.status !== "running") {
            timer = setInterval(fetchTaskStatus, 1000);
        }
        return () => clearInterval(timer);
    }, [taskStatus?.id, taskStatus?.status, autoIterateStatus?.status]);

    // 自动保存配置 (Debounce 1s)
    // 在自动迭代或优化中时，不触发自动保存，避免重复保存
    useEffect(() => {
        if (!project) return;
        // 如果正在自动迭代 或 正在优化，跳过自动保存
        if (autoIterateStatus?.status === "running" || isOptimizing) return;

        const timer = setTimeout(() => {
            saveProject(true);
        }, 1000);

        return () => clearTimeout(timer);
    }, [config, fileInfo, extractField, project?.current_prompt, autoIterateStatus?.status, isOptimizing, validationLimit]);

    const router = useRouter();

    const fetchTaskHistory = async () => {
        try {
            const tasksRes = await axios.get(`${API_BASE}/projects/${id}/tasks`);
            setTaskHistory(tasksRes.data.tasks || []);
        } catch (e) {
            console.error("Failed to fetch task history", e);
        }
    };

    const fetchKnowledgeBase = async () => {
        try {
            const res = await axios.get(`${API_BASE}/projects/${id}/knowledge-base`);
            setKnowledgeRecords(res.data.records || []);
        } catch (e) {
            console.error("Failed to fetch knowledge base", e);
        }
    };

    const fetchProject = async () => {
        try {
            const res = await axios.get(`${API_BASE}/projects/${id}`);
            if (!res.data) {
                // 如果返回数据为空，视为不存在
                router.push("/");
                return;
            }
            setProject(res.data);

            // 恢复项目配置
            if (res.data.config) {
                setConfig({
                    query_col: res.data.config.query_col || "",
                    target_col: res.data.config.target_col || "",
                    reason_col: res.data.config.reason_col || ""
                });
                setExtractField(res.data.config.extract_field || "");

                // 恢复文件信息
                if (res.data.config.file_info) {
                    setFileInfo(res.data.config.file_info);
                }

                // 恢复自动迭代配置
                if (res.data.config.auto_iterate_config) {
                    setAutoIterateConfig(res.data.config.auto_iterate_config);
                }

                // 恢复验证配置
                const limit = res.data.config.validation_limit;
                const parsedLimit = parseInt(limit);
                if (!isNaN(parsedLimit) && parsedLimit > 0) {
                    setValidationLimit(parsedLimit);
                } else {
                    setValidationLimit("");
                }
            }

            // 获取任务历史
            await fetchTaskHistory();
            // 获取知识库记录
            await fetchKnowledgeBase();

            // 如果有历史任务，恢复最近一个的状态 (这里我们要小心，因为 fetchTaskHistory 是异步的，
            // 但我们需要 taskHistory 里的数据。await fetchTaskHistory() 会设置 state，
            // 但 state 更新是异步的。所以我们最好在 fetchTaskHistory 里返回数据，或者在这里重新请求/从 state 拿不到最新)
            // 简单起见，这里再次请求一下或者让 fetchTaskHistory 返回数据
            // 为了避免冲突，我们手动在这里请求一次用于恢复状态，或者直接信任 fetchTaskHistory 的副作用
            // 但由于 React state update batching，这里拿不到 updated taskHistory。
            // 所以保留原来的逻辑用于恢复状态，但使用 fetchTaskHistory 来设置 history list。

            const tasksRes = await axios.get(`${API_BASE}/projects/${id}/tasks`);
            // setTaskHistory 已经在 fetchTaskHistory 做过了，但也无妨

            // 恢复最近一个的状态
            if (tasksRes.data.tasks?.length > 0) {
                const latestTaskId = tasksRes.data.tasks[0].id;
                try {
                    const taskRes = await axios.get(`${API_BASE}/tasks/${latestTaskId}`);
                    setTaskStatus(taskRes.data);
                } catch (e) { console.log("无法恢复任务状态"); }
            }
        } catch (e: any) {
            console.error(e);
            // 只有 404 时跳转回主页
            if (e.response && e.response.status === 404) {
                router.push("/");
            } else {
                // 其他错误仅提示，不跳转
                console.error("Fetch project failed", e);
            }
        }
    };

    const isAutoIterating = autoIterateStatus?.status === "running";
    // 轮询Ref防止重复
    const isPollingRef = useRef(false);

    const pollAutoIterateStatus = () => {
        if (isPollingRef.current) return;
        isPollingRef.current = true;

        const poll = async () => {
            try {
                const res = await axios.get(`${API_BASE}/projects/${id}/auto-iterate/status`);
                setAutoIterateStatus(res.data);

                // 如果仍在运行，继续轮询
                if (res.data.status === "running") {
                    // 同时获取并同步任务状态
                    if (res.data.task_id) {
                        try {
                            const taskRes = await axios.get(`${API_BASE}/tasks/${res.data.task_id}`);
                            setTaskStatus(taskRes.data);
                        } catch (e) { console.error("Error fetching sub-task status", e); }
                    }
                    // 刷新项目信息以更新迭代历史和提示词
                    fetchProject();

                    setTimeout(poll, 1000);
                } else {
                    isPollingRef.current = false;
                    // 完成后刷新项目以获取最新 prompt 和 iterations
                    fetchProject();
                }
            } catch (e: any) {
                console.error("Auto-iterate polling error:", e);

                // 如果是网络错误（后端可能重启），尝试重试几次
                // 如果持续失败，则标记状态为错误
                if (e.code === "ERR_NETWORK" || e.message?.includes("Network Error")) {
                    // 网络错误，等待后重试一次
                    setTimeout(async () => {
                        try {
                            const retryRes = await axios.get(`${API_BASE}/projects/${id}/auto-iterate/status`);
                            setAutoIterateStatus(retryRes.data);
                            // 如果重试成功且仍在运行，继续轮询
                            if (retryRes.data.status === "running") {
                                isPollingRef.current = false;
                                pollAutoIterateStatus();
                            } else {
                                isPollingRef.current = false;
                            }
                        } catch {
                            // 重试也失败，标记为中断
                            setAutoIterateStatus({
                                status: "error",
                                message: "连接中断，请刷新页面重试"
                            });
                            isPollingRef.current = false;
                        }
                    }, 2000);
                } else {
                    // 其他错误，直接标记为中断
                    setAutoIterateStatus({
                        status: "error",
                        message: "状态获取失败，请刷新页面"
                    });
                    isPollingRef.current = false;
                }
            }
        };
        poll();
    };

    const fetchTaskStatus = async () => {
        if (!taskStatus?.id) return;
        try {
            const res = await axios.get(`${API_BASE}/tasks/${taskStatus.id}`);
            const newData = res.data;
            setTaskStatus(newData);

            // 如果任务状态变为完成/停止，刷新历史列表
            // 注意：这里利用闭包中的 taskStatus (它是 running) 来判断状态变化
            if (taskStatus.status === "running" && ["completed", "stopped", "failed"].includes(newData.status)) {
                fetchTaskHistory();
            }
        } catch (e) { console.error(e); }
    };

    const handleFileUpload = async (e: any) => {
        const file = e.target.files[0];
        if (!file) return;
        const formData = new FormData();
        formData.append("file", file);
        try {
            const res = await axios.post(`${API_BASE}/upload`, formData);
            setFileInfo(res.data);
            if (res.data.columns.length >= 2) {
                setConfig({ query_col: res.data.columns[0], target_col: res.data.columns[1] });
            }
            showToast(`文件 ${file.name} 上传并解析成功`, "success");
        } catch (e: any) {
            console.error(e);
            const errorMsg = e.response?.data?.detail || "上传失败";
            showToast(`上传失败: ${errorMsg}`, "error");
        }
    };

    const startTask = async () => {
        if (!fileInfo) {
            showToast("请先上传测试数据文件", "error");
            return;
        }
        if (!config.query_col || !config.target_col) {
            showToast("请配置数据列映射", "error");
            return;
        }

        // 校验模型配置
        // 如果是接口验证模式，不需要校验 API Key
        const isInterfaceMode = project.model_config?.validation_mode === "interface";
        if (!isInterfaceMode && (!project.model_config || !project.model_config.api_key)) {
            showToast("请先在右上角【项目配置】中设置 API Key", "error");
            setShowConfig(true);
            return;
        }

        // 启动前先保存项目配置（静默保存）
        await saveProject(true);

        // 如果开启了自动迭代，调用自动迭代API
        if (autoIterateConfig.enabled) {
            startAutoIterate();
            return;
        }

        // 否则启动普通任务
        const formData = new FormData();
        formData.append("project_id", id as string);
        formData.append("file_id", fileInfo.file_id);
        formData.append("query_col", config.query_col);
        formData.append("target_col", config.target_col);
        if (config.reason_col) formData.append("reason_col", config.reason_col);
        formData.append("prompt", project.current_prompt);
        if (extractField) formData.append("extract_field", extractField);
        if (validationLimit) formData.append("validation_limit", validationLimit.toString());
        // 传递原始文件名
        if (fileInfo.filename) formData.append("original_filename", fileInfo.filename);

        try {
            const res = await axios.post(`${API_BASE}/tasks/start`, formData);
            setTaskStatus({ id: res.data.task_id, status: "running" });
            showToast("任务启动成功", "success");
            // 刷新历史列表，显示当前正在运行的任务
            fetchTaskHistory();
        } catch (e: any) {
            console.error("Start task failed:", e);
            const errorMsg = e.response?.data?.detail || e.message || "任务启动失败";
            showToast(`启动失败: ${errorMsg}`, "error");
        }
    };

    const controlTask = async (action: string) => {
        try {
            await axios.post(`${API_BASE}/tasks/${taskStatus.id}/${action}`);
            if (action === "stop" && autoIterateStatus?.status === "running") {
                await axios.post(`${API_BASE}/projects/${id}/auto-iterate/stop`);
                setAutoIterateStatus({ ...autoIterateStatus, status: "stopped", message: "已手动停止" });
            }
            fetchTaskStatus();
            // 刷新历史列表状态
            fetchTaskHistory();
        } catch (e) { console.error(e); }
    };

    const [strategy, setStrategy] = useState<"multi" | "simple">("multi");

    // 优化状态轮询
    const isOptimizePollingRef = useRef(false);

    const pollOptimizationStatus = () => {
        if (isOptimizePollingRef.current) return;
        isOptimizePollingRef.current = true;
        setIsOptimizing(true);

        const poll = async () => {
            try {
                const res = await axios.get(`${API_BASE}/projects/${id}/optimize/status`);
                const status = res.data;

                if (status.status === "completed") {
                    setIsOptimizing(false);
                    isOptimizePollingRef.current = false;
                    showToast("提示词优化成功！", "success");
                    fetchProject();
                    fetchKnowledgeBase();
                } else if (status.status === "failed") {
                    setIsOptimizing(false);
                    isOptimizePollingRef.current = false;
                    showToast(`优化失败: ${status.message}`, "error");
                } else if (status.status === "stopped") {
                    // 检测到停止状态，立即更新 UI
                    setIsOptimizing(false);
                    isOptimizePollingRef.current = false;
                    showToast("优化任务已停止", "success");
                    fetchProject();
                } else if (status.status === "idle") {
                    setIsOptimizing(false);
                    isOptimizePollingRef.current = false;
                } else {
                    // Running... continue polling
                    setTimeout(poll, 1000);
                }
            } catch (e) {
                console.error(e);
                setIsOptimizing(false);
                isOptimizePollingRef.current = false;
            }
        };
        poll();
    };

    // 页面加载时检查是否有正在进行的优化任务
    useEffect(() => {
        if (id) {
            // 简单检查一下状态
            axios.get(`${API_BASE}/projects/${id}/optimize/status`).then(res => {
                if (res.data.status === "running") {
                    pollOptimizationStatus();
                }
            }).catch(console.error);
        }
    }, [id]);

    const handleOptimize = async () => {
        if (!taskStatus?.id) return;

        // 校验模型配置 (验证模型)
        if (!project.model_config || !project.model_config.api_key) {
            showToast("请先在【项目配置】中设置验证模型的 API Key", "error");
            return;
        }

        // 校验优化模型配置
        // optimization_model_config 可能为空，或者 api_key 为空
        if (!project.optimization_model_config || !project.optimization_model_config.api_key) {
            showToast("请先在【项目配置】-【优化配置】中设置 API Key", "error");
            setConfigTab("optimization");
            setShowConfig(true);
            return;
        }

        try {
            // 启动优化任务
            await axios.post(`${API_BASE}/projects/${id}/optimize?task_id=${taskStatus.id}&strategy=${strategy}`);
            showToast("优化任务已启动，正在后台运行...", "success");
            // 开始轮询
            pollOptimizationStatus();
        } catch (e) {
            showToast("启动优化任务失败", "error");
            console.error(e);
        }
    };

    const handleStopOptimize = async () => {
        try {
            await axios.post(`${API_BASE}/projects/${id}/optimize/stop`);
            showToast("正在停止优化任务...", "success");
            // 轮询会检测到 stopped 状态并更新 UI
        } catch (e) {
            console.error("Stop failed", e);
            showToast("停止请求失败", "error");
        }
    };

    const startAutoIterate = async () => {
        if (!fileInfo || !config.query_col || !config.target_col) {
            alert("请先上传文件并配置列映射");
            return;
        }

        // 校验优化模型配置
        if (!project.optimization_model_config || !project.optimization_model_config.api_key) {
            showToast("请先在【项目配置】-【优化配置】中配置模型参数(API Key)", "error");
            setConfigTab("optimization");
            setShowConfig(true);
            return;
        }

        // 先保存项目
        await saveProject(true);

        const formData = new FormData();
        formData.append("file_id", fileInfo.file_id);
        formData.append("query_col", config.query_col);
        formData.append("target_col", config.target_col);
        formData.append("prompt", project.current_prompt);
        formData.append("max_rounds", (autoIterateConfig.maxRounds || 5).toString());
        formData.append("target_accuracy", ((Number(autoIterateConfig.targetAccuracy) || 95) / 100).toString());
        formData.append("strategy", autoIterateConfig.strategy || "multi");
        if (validationLimit) formData.append("validation_limit", validationLimit.toString());
        if (extractField) formData.append("extract_field", extractField);

        try {
            await axios.post(`${API_BASE}/projects/${id}/auto-iterate`, formData);
            // 开始轮询状态
            pollAutoIterateStatus();
        } catch (e) {
            alert("启动自动迭代失败");
        }
    };

    const stopAutoIterate = async () => {
        try {
            await axios.post(`${API_BASE}/projects/${id}/auto-iterate/stop`);
        } catch (e) { console.error(e); }
    };

    /**
     * 从后端获取优化上下文
     * @returns 优化上下文字符串
     */
    const fetchOptimizeContext = async (): Promise<string> => {
        if (!taskStatus?.id || !taskStatus?.errors?.length) {
            return "";
        }
        try {
            const res = await axios.get(
                `${API_BASE}/projects/${id}/optimize-context?task_id=${taskStatus.id}`
            );
            return res.data.context || "";
        } catch (e: any) {
            console.error("Failed to fetch optimize context:", e);
            throw new Error(e.response?.data?.detail || "获取优化上下文失败");
        }
    };

    /**
     * 复制优化上下文到剪贴板
     */
    const copyOptimizeContext = async () => {
        try {
            const context: string = await fetchOptimizeContext();
            if (!context) {
                showToast("没有可用的优化上下文", "error");
                return;
            }
            // 更新状态，方便在面板中显示供手动复制
            setOptimizeContext(context);
            await navigator.clipboard.writeText(context);
            showToast("优化上下文已复制到剪贴板！", "success");
        } catch (e: any) {
            console.error("Clipboard write failed:", e);
            // 即使复制失败，也尝试更新状态以便手动复制
            try {
                const context: string = await fetchOptimizeContext();
                setOptimizeContext(context);
            } catch { }
            showToast(`复制失败, 请手动复制, 原因: ${e.message}`, "error");
        }
    };

    const applyExternalOptimize = async () => {
        if (!externalPrompt.trim()) {
            alert("请粘贴优化后的提示词");
            return;
        }

        // 保存迭代记录
        const accuracy = taskStatus?.results?.length
            ? (taskStatus.results.length - taskStatus.errors.length) / taskStatus.results.length
            : 0;

        try {
            // 手动添加迭代记录
            const res = await axios.get(`${API_BASE}/projects/${id}`);
            const proj = res.data;
            proj.iterations = proj.iterations || [];
            proj.iterations.push({
                old_prompt: project.current_prompt,
                new_prompt: externalPrompt.trim(),
                task_id: taskStatus?.id || "external",
                accuracy: accuracy,
                source: "external",
                created_at: new Date().toISOString()
            });
            proj.current_prompt = externalPrompt.trim();

            // 更新项目
            const formData = new FormData();
            formData.append("current_prompt", externalPrompt.trim());
            formData.append("query_col", config.query_col);
            formData.append("target_col", config.target_col);
            formData.append("extract_field", extractField);
            // 这里必须要传iterations，否则后端不会更新历史记录
            formData.append("iterations", JSON.stringify(proj.iterations));
            await axios.put(`${API_BASE}/projects/${id}`, formData);

            // 更新本地状态
            setProject({ ...project, current_prompt: externalPrompt.trim(), iterations: proj.iterations });
            setExternalPrompt("");
            setShowExternalOptimize(false);
            showToast("外部优化结果已应用！", "success");
            fetchProject();
        } catch (e) {
            showToast("应用失败", "error");
            console.error(e);
        }
    };

    const saveProject = async (silent: boolean = false) => {
        setIsSaving(true);
        try {
            const formData = new FormData();
            formData.append("current_prompt", project.current_prompt);
            formData.append("query_col", config.query_col);
            formData.append("target_col", config.target_col);
            // 确保 reason_col 也被保存 (如果 config 中存在)
            if (config.reason_col) {
                formData.append("reason_col", config.reason_col);
            }
            formData.append("extract_field", extractField);
            // 保存文件信息
            if (fileInfo) {
                formData.append("file_info", JSON.stringify(fileInfo));
            }
            // 保存项目名称
            formData.append("name", project.name);
            // 保存自动迭代配置
            formData.append("auto_iterate_config", JSON.stringify(autoIterateConfig));
            // 保存验证配置
            formData.append("validation_limit", validationLimit === "" ? "" : validationLimit.toString());

            await axios.put(`${API_BASE}/projects/${id}`, formData);
            if (!silent) showToast("项目保存成功！", "success");
        } catch (e) {
            showToast("保存失败", "error");
            console.error(e);
        } finally {
            setIsSaving(false);
        }
    };

    if (!project) return <div className="p-10 text-center">加载中...</div>;

    return (
        <div className="space-y-8">
            {/* Toast 提示 */}
            {toast && (
                <motion.div
                    initial={{ opacity: 0, y: -50, x: "-50%" }}
                    animate={{ opacity: 1, y: 0, x: "-50%" }}
                    exit={{ opacity: 0, y: -50 }}
                    className={`fixed top-6 left-1/2 z-[100] px-6 py-3 rounded-xl shadow-lg ${toast.type === "success"
                        ? "bg-emerald-600 text-white"
                        : "bg-red-600 text-white"
                        }`}
                >
                    {toast.message}
                </motion.div>
            )}

            <ProjectHeader
                projectName={project.name}
                onNameChange={(name) => setProject({ ...project, name })}
                isSaving={isSaving}
                onSave={() => saveProject(false)}
                onOpenConfig={() => {
                    setConfigTab("verification");
                    setShowConfig(true);
                }}
                onTest={() => setShowTestModal(true)}
            />

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Left: Configuration & Task */}
                <div className="lg:col-span-2 space-y-6">
                    <PromptEditor
                        currentPrompt={project.current_prompt}
                        onPromptChange={(prompt) => setProject({ ...project, current_prompt: prompt })}
                        isAutoIterating={isAutoIterating}
                    />

                    <ExecutionPanel
                        taskStatus={taskStatus}
                        fileInfo={fileInfo}
                        config={config}
                        setConfig={setConfig}
                        extractField={extractField}
                        setExtractField={setExtractField}
                        autoIterateConfig={autoIterateConfig}
                        setAutoIterateConfig={setAutoIterateConfig}
                        autoIterateStatus={autoIterateStatus}
                        isAutoIterating={isAutoIterating}
                        onFileUpload={handleFileUpload}
                        onStartTask={startTask}
                        onControlTask={controlTask}
                        onStopAutoIterate={stopAutoIterate}
                        onOptimize={handleOptimize}
                        onStopOptimize={handleStopOptimize}
                        isOptimizing={isOptimizing}
                        showExternalOptimize={showExternalOptimize}
                        setShowExternalOptimize={setShowExternalOptimize}
                        externalPrompt={externalPrompt}
                        setExternalPrompt={setExternalPrompt}
                        onCopyOptimizeContext={copyOptimizeContext}
                        onApplyExternalOptimize={applyExternalOptimize}
                        optimizeContext={optimizeContext}
                        strategy={strategy}
                        setStrategy={setStrategy}
                        validationLimit={validationLimit}
                        setValidationLimit={setValidationLimit}
                    />
                </div>

                {/* Right: History & Info */}
                <div className="space-y-6">
                    <HistoryPanel
                        taskStatus={taskStatus}
                        project={project}
                        runHistory={taskHistory}
                        onSelectLog={setSelectedLog}
                        onSelectIteration={setSelectedIteration}
                        knowledgeRecords={knowledgeRecords}
                        onSelectKnowledge={setSelectedKnowledge}
                        onDeleteTask={async (task) => {
                            try {
                                await axios.delete(`${API_BASE}/tasks/${task.id}`);
                                showToast("运行记录已删除", "success");
                                fetchTaskHistory();
                            } catch (e) {
                                showToast("删除记录失败", "error");
                            }
                        }}
                        onDeleteIteration={async (iteration) => {
                            try {
                                await axios.delete(`${API_BASE}/projects/${id}/iterations?timestamp=${iteration.created_at}`);
                                showToast("迭代记录已删除", "success");
                                fetchProject();
                            } catch (e) {
                                showToast("删除记录失败", "error");
                            }
                        }}
                        onDeleteKnowledge={async (record) => {
                            try {
                                await axios.delete(`${API_BASE}/projects/${id}/knowledge-base/${record.version}`);
                                showToast("优化分析记录已删除", "success");
                                fetchKnowledgeBase();
                            } catch (e) {
                                showToast("删除记录失败", "error");
                            }
                        }}
                    />
                </div>
            </div>

            {showConfig && <ModelConfig onClose={() => setShowConfig(false)} projectId={id as string} onSave={fetchProject} defaultTab={configTab} />}

            <LogDetailModal
                selectedLog={selectedLog}
                onClose={() => setSelectedLog(null)}
            />

            <IterationDetailModal
                selectedIteration={selectedIteration}
                onClose={() => setSelectedIteration(null)}
                onApply={(newPrompt, msg) => {
                    setProject({ ...project, current_prompt: newPrompt });
                    if (msg) showToast(msg, "success");
                }}
            />

            <KnowledgeDetailModal
                record={selectedKnowledge}
                projectId={id as string}
                onClose={() => setSelectedKnowledge(null)}
                onUpdate={fetchKnowledgeBase}
                showToast={showToast}
            />

            {showTestModal && (
                <TestOutputModal
                    initialPrompt={project.current_prompt}
                    initialModelConfig={project.model_config} // Pass verification model config
                    onClose={() => setShowTestModal(false)}
                />
            )}
        </div>
    );
}
