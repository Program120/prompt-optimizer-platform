"use client";

import { useState, useEffect, useRef } from "react";
import { useParams } from "next/navigation";
import axios from "axios";
import { motion } from "framer-motion";
import ModelConfig from "@/app/components/ModelConfig";

import ProjectHeader from "./_components/ProjectHeader";
import PromptEditor from "./_components/PromptEditor";
import ExecutionPanel from "./_components/ExecutionPanel";
import HistoryPanel from "./_components/HistoryPanel";
import LogDetailModal from "./_components/LogDetailModal";
import IterationDetailModal from "./_components/IterationDetailModal";

// 统一使用相对路径
const API_BASE = "/api";

export default function ProjectDetail() {
    const { id } = useParams();
    const [project, setProject] = useState<any>(null);
    const [fileInfo, setFileInfo] = useState<any>(null);
    const [config, setConfig] = useState({ query_col: "", target_col: "" });
    const [taskStatus, setTaskStatus] = useState<any>(null);
    const [isOptimizing, setIsOptimizing] = useState(false);
    const [showConfig, setShowConfig] = useState(false);
    const [extractField, setExtractField] = useState("");
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

    // Auto-iterate config
    const [autoIterateConfig, setAutoIterateConfig] = useState({ enabled: false, maxRounds: 5, targetAccuracy: 95 });
    const [autoIterateStatus, setAutoIterateStatus] = useState<any>(null);

    const [showExternalOptimize, setShowExternalOptimize] = useState(false);
    const [externalPrompt, setExternalPrompt] = useState("");
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
    useEffect(() => {
        if (!project) return;

        const timer = setTimeout(() => {
            saveProject(true);
        }, 1000);

        return () => clearTimeout(timer);
    }, [config, fileInfo, extractField, project?.current_prompt]);

    const fetchProject = async () => {
        try {
            const res = await axios.get(`${API_BASE}/projects/${id}`);
            setProject(res.data);

            // 恢复项目配置
            if (res.data.config) {
                setConfig({
                    query_col: res.data.config.query_col || "",
                    target_col: res.data.config.target_col || ""
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
            }

            // 获取任务历史并恢复最近任务状态
            const tasksRes = await axios.get(`${API_BASE}/projects/${id}/tasks`);
            setTaskHistory(tasksRes.data.tasks || []);

            // 如果有历史任务，恢复最近一个的状态
            if (tasksRes.data.tasks?.length > 0) {
                const latestTaskId = tasksRes.data.tasks[0].id;
                try {
                    const taskRes = await axios.get(`${API_BASE}/tasks/${latestTaskId}`);
                    setTaskStatus(taskRes.data);
                } catch (e) { console.log("无法恢复任务状态"); }
            }
        } catch (e) { console.error(e); }
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
            } catch (e) {
                console.error(e);
                isPollingRef.current = false;
            }
        };
        poll();
    };

    const fetchTaskStatus = async () => {
        if (!taskStatus?.id) return;
        try {
            const res = await axios.get(`${API_BASE}/tasks/${taskStatus.id}`);
            setTaskStatus(res.data);
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
        } catch (e) { alert("上传失败"); }
    };

    const startTask = async () => {
        if (!fileInfo || !config.query_col || !config.target_col) return;

        // 校验模型配置
        if (!project.model_config || !project.model_config.api_key) {
            showToast("请先在右上角【模型配置】中设置 API Key", "error");
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
        formData.append("prompt", project.current_prompt);
        if (extractField) formData.append("extract_field", extractField);

        try {
            const res = await axios.post(`${API_BASE}/tasks/start`, formData);
            setTaskStatus({ id: res.data.task_id, status: "running" });
        } catch (e) { alert("启动失败"); }
    };

    const controlTask = async (action: string) => {
        try {
            await axios.post(`${API_BASE}/tasks/${taskStatus.id}/${action}`);
            // 如果是停止操作且自动迭代正在运行，同时停止自动迭代
            if (action === "stop" && autoIterateStatus?.status === "running") {
                await axios.post(`${API_BASE}/projects/${id}/auto-iterate/stop`);
                setAutoIterateStatus({ ...autoIterateStatus, status: "stopped", message: "已手动停止" });
            }
            fetchTaskStatus();
        } catch (e) { console.error(e); }
    };

    const handleOptimize = async () => {
        if (!taskStatus?.id) return;

        // 校验模型配置
        if (!project.model_config || !project.model_config.api_key) {
            showToast("请先配置模型参数(API Key)", "error");
            return;
        }

        setIsOptimizing(true);
        try {
            const res = await axios.post(`${API_BASE}/projects/${id}/optimize?task_id=${taskStatus.id}`);
            showToast("提示词优化成功！", "success");
            fetchProject();
        } catch (e) { showToast("优化失败", "error"); }
        finally { setIsOptimizing(false); }
    };

    const startAutoIterate = async () => {
        if (!fileInfo || !config.query_col || !config.target_col) {
            alert("请先上传文件并配置列映射");
            return;
        }

        // 先保存项目
        await saveProject(true);

        const formData = new FormData();
        formData.append("file_id", fileInfo.file_id);
        formData.append("query_col", config.query_col);
        formData.append("target_col", config.target_col);
        formData.append("prompt", project.current_prompt);
        formData.append("max_rounds", autoIterateConfig.maxRounds.toString());
        formData.append("target_accuracy", (autoIterateConfig.targetAccuracy / 100).toString());
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

    const generateOptimizeContext = () => {
        if (!taskStatus?.errors?.length) return "";

        let errorSamples = "| 用户输入 | 预期输出 | 模型实际输出 |\n| :--- | :--- | :--- |\n";
        taskStatus.errors.slice(0, 10).forEach((err: any) => {
            const query = (err.query || "").toString().replace(/\n/g, " ").replace(/\|/g, "\\|");
            const target = (err.target || "").toString().replace(/\n/g, " ").replace(/\|/g, "\\|");
            const output = (err.output || "").toString().replace(/\n/g, " ").replace(/\|/g, "\\|");
            errorSamples += `| ${query} | ${target} | ${output} |\n`;
        });

        return `你是一个专业的AI提示词工程专家。请优化以下系统提示词。

        ## 当前使用的系统提示词：
        \`\`\`
        ${project.current_prompt}
        \`\`\`

        ## 模型执行时出现的错误样例（共${taskStatus.errors.length}个错误）：
        ${errorSamples}

        ## 任务：
        请输出优化后的【完整系统提示词】（直接输出提示词内容，不要添加任何其他说明）：`;
    };

    const copyOptimizeContext = async () => {
        const context = generateOptimizeContext();
        try {
            await navigator.clipboard.writeText(context);
            showToast("优化上下文已复制到剪贴板！", "success");
        } catch (e) {
            showToast("复制失败，请手动复制", "error");
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
            formData.append("extract_field", extractField);
            // 保存文件信息
            if (fileInfo) {
                formData.append("file_info", JSON.stringify(fileInfo));
            }
            // 保存项目名称
            formData.append("name", project.name);
            // 保存自动迭代配置
            formData.append("auto_iterate_config", JSON.stringify(autoIterateConfig));

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
                    className={`fixed top-6 left-1/2 z-50 px-6 py-3 rounded-xl shadow-lg ${toast.type === "success"
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
                onOpenConfig={() => setShowConfig(true)}
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
                        isOptimizing={isOptimizing}
                        showExternalOptimize={showExternalOptimize}
                        setShowExternalOptimize={setShowExternalOptimize}
                        externalPrompt={externalPrompt}
                        setExternalPrompt={setExternalPrompt}
                        onCopyOptimizeContext={copyOptimizeContext}
                        onApplyExternalOptimize={applyExternalOptimize}
                    />
                </div>

                {/* Right: History & Info */}
                <div className="space-y-6">
                    <HistoryPanel
                        taskStatus={taskStatus}
                        project={project}
                        onSelectLog={setSelectedLog}
                        onSelectIteration={setSelectedIteration}
                    />
                </div>
            </div>

            {showConfig && <ModelConfig onClose={() => setShowConfig(false)} projectId={id as string} />}

            <LogDetailModal
                selectedLog={selectedLog}
                onClose={() => setSelectedLog(null)}
            />

            <IterationDetailModal
                selectedIteration={selectedIteration}
                onClose={() => setSelectedIteration(null)}
                onApply={(newPrompt) => setProject({ ...project, current_prompt: newPrompt })}
            />
        </div>
    );
}
