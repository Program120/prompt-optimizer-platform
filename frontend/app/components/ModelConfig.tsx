"use client";
import { useState, useEffect } from "react";
import axios from "axios";
import { Settings, Save, Loader2 } from "lucide-react";
import { motion } from "framer-motion";
import { useToast } from "./ui/Toast";

// 统一使用相对路径
const API_BASE: string = "/api";

// 默认优化提示词（与后端 prompts.py 保持一致）
const DEFAULT_OPTIMIZATION_PROMPT: string = `你是一个专业的AI提示词工程专家。

你的任务是优化用户提供的【系统级提示词】。这个提示词是用来指导AI模型完成特定任务的指令。

## 你需要做的事情：
1. 分析【当前提示词】中可能导致错误的问题
2. 根据【错误样例】理解模型输出的问题所在
3. 输出一个【完整的、优化后的系统级提示词】

## 重要规则：
- 你输出的必须是完整的、可以直接使用的【系统提示词】
- 不要输出示例输出、不要输出解释
- 保持原有提示词的核心意图和输出格式要求
- 让指令更加清晰明确，避免歧义
- 可以添加更多限制条件和边界情况的处理说明

## 当前使用的系统提示词：
\`\`\`
{old_prompt}
\`\`\`

## 模型执行时出现的错误样例：
{error_samples}

## 任务：
请输出优化后的【完整系统提示词】（直接输出提示词内容，不要添加任何其他说明）：`;

export default function ModelConfig({ onClose, projectId, onSave }: { onClose: () => void; projectId?: string; onSave?: () => void }) {
    const { success, error, toast } = useToast();
    const [activeTab, setActiveTab] = useState<"verification" | "optimization">("verification");

    // 测试连接状态（不阻塞保存操作）
    const [isTesting, setIsTesting] = useState<boolean>(false);
    // 保存配置状态
    const [isSaving, setIsSaving] = useState<boolean>(false);

    const [config, setConfig] = useState({
        base_url: "",
        api_key: "",
        max_tokens: 2000,
        timeout: 60,
        model_name: "gpt-3.5-turbo",
        concurrency: 5,
        temperature: 0.0
    });
    const [optConfig, setOptConfig] = useState({
        base_url: "",
        api_key: "",
        max_tokens: 2000,
        timeout: 60,
        model_name: "gpt-3.5-turbo",
        temperature: 0.7
    });
    const [optPrompt, setOptPrompt] = useState("");

    useEffect(() => {
        if (projectId) {
            fetchProjectConfig();
        } else {
            fetchConfig();
        }
    }, [projectId]);

    const fetchProjectConfig = async () => {
        try {
            const res = await axios.get(`${API_BASE}/projects/${projectId}`);
            if (res.data.model_config) {
                setConfig(prev => ({ ...prev, ...res.data.model_config }));
            }
            if (res.data.optimization_model_config) {
                setOptConfig(prev => ({ ...prev, ...res.data.optimization_model_config }));
            }
            if (res.data.optimization_prompt) {
                setOptPrompt(res.data.optimization_prompt);
            }
        } catch (e) { console.error(e); }
    };

    const fetchConfig = async () => {
        try {
            const res = await axios.get(`${API_BASE}/config`);
            setConfig(prev => ({ ...prev, ...res.data }));
            // 全局配置目前只支持一套，可以共用
            setOptConfig(prev => ({ ...prev, ...res.data, temperature: 0.7 }));
        } catch (e) { console.error(e); }
    };

    /**
     * 保存配置处理函数
     * 此函数独立于测试连接，不会被测试阻塞
     */
    const handleSave = async (): Promise<void> => {
        // 如果正在保存，防止重复点击
        if (isSaving) {
            return;
        }

        // 验证优化提示词
        if (activeTab === "optimization" && optPrompt) {
            if (!optPrompt.includes("{old_prompt}") || !optPrompt.includes("{error_samples}")) {
                error("提示词优化模板必须包含 {old_prompt} 和 {error_samples} 占位符");
                return;
            }
        }

        setIsSaving(true);

        if (projectId) {
            // 保存到项目
            const formData: FormData = new FormData();
            formData.append("model_cfg", JSON.stringify(config));
            formData.append("optimization_model_config", JSON.stringify(optConfig));
            formData.append("optimization_prompt", optPrompt);
            formData.append("current_prompt", "");

            try {
                // 获取当前项目的 prompt
                const projectRes = await axios.get(`${API_BASE}/projects/${projectId}`);
                formData.set("current_prompt", projectRes.data.current_prompt);

                await axios.put(`${API_BASE}/projects/${projectId}`, formData);
                success("项目配置已保存");
                if (onSave) onSave(); // Call callback
                onClose();
            } catch (e) {
                error("保存失败");
            } finally {
                setIsSaving(false);
            }
        } else {
            // ... (global save logic, maybe call onSave there too? User asked for project context mainly but consistent is better)
            // The user scenario is specific to project config validation.
            // Let's add it to global too for completeness.
            const formData: FormData = new FormData();
            formData.append("base_url", config.base_url);
            formData.append("api_key", config.api_key);
            formData.append("max_tokens", String(config.max_tokens));
            formData.append("timeout", String(config.timeout));
            formData.append("model_name", config.model_name);
            formData.append("concurrency", String(config.concurrency));
            formData.append("temperature", String(config.temperature));
            try {
                await axios.post(`${API_BASE}/config`, formData);
                success("全局配置已保存");
                if (onSave) onSave();
                onClose();
            } catch (e) {
                error("保存失败");
            } finally {
                setIsSaving(false);
            }
        }
    };

    /**
     * 测试连接处理函数
     * 此函数独立于保存操作，在测试期间不会阻塞保存按钮
     */
    const handleTest = async (): Promise<void> => {
        // 如果正在测试，防止重复点击
        if (isTesting) {
            return;
        }

        setIsTesting(true);

        const targetConfig = activeTab === "verification" ? config : optConfig;
        const formData: FormData = new FormData();
        formData.append("base_url", targetConfig.base_url);
        formData.append("api_key", targetConfig.api_key);
        formData.append("model_name", targetConfig.model_name);

        try {
            const res = await axios.post(`${API_BASE}/config/test`, formData);
            if (res.data.success !== false) {
                success(res.data.message || "测试连接成功");
            } else {
                error(res.data.message || "测试连接失败");
            }
        } catch (e) {
            error("测试请求失败");
        } finally {
            setIsTesting(false);
        }
    };

    const renderConfigForm = (cfg: any, setCfg: any, isVerification: boolean) => (
        <div className="space-y-4">
            <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">Base URL</label>
                <input
                    type="text"
                    value={cfg.base_url}
                    onChange={e => setCfg({ ...cfg, base_url: e.target.value })}
                    className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2 focus:outline-none focus:border-blue-500 transition-colors text-sm"
                    placeholder="https://api.openai.com/v1"
                />
            </div>
            <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">API Key</label>
                <input
                    type="password"
                    value={cfg.api_key}
                    onChange={e => setCfg({ ...cfg, api_key: e.target.value })}
                    className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2 focus:outline-none focus:border-blue-500 transition-colors text-sm"
                    placeholder="sk-..."
                />
            </div>
            <div className="grid grid-cols-2 gap-4">
                <div>
                    <label className="block text-sm font-medium text-slate-400 mb-2">模型名称</label>
                    <input
                        type="text"
                        value={cfg.model_name}
                        onChange={e => setCfg({ ...cfg, model_name: e.target.value })}
                        className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2 focus:outline-none focus:border-blue-500 transition-colors text-sm"
                        placeholder="gpt-3.5-turbo"
                    />
                </div>
                <div>
                    <label className="block text-sm font-medium text-slate-400 mb-2">超时 (秒)</label>
                    <input
                        type="number"
                        value={cfg.timeout}
                        onChange={e => setCfg({ ...cfg, timeout: parseInt(e.target.value) || 60 })}
                        className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2 focus:outline-none focus:border-blue-500 transition-colors text-sm"
                    />
                </div>
            </div>

            {isVerification && (
                <div>
                    <label className="block text-sm font-medium text-slate-400 mb-2">并发度</label>
                    <input
                        type="number"
                        min={1}
                        max={50}
                        value={cfg.concurrency}
                        onChange={e => setCfg({ ...cfg, concurrency: parseInt(e.target.value) || 5 })}
                        className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2 focus:outline-none focus:border-blue-500 transition-colors text-sm"
                    />
                </div>
            )}

            <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">温度 (Temperature) - {cfg.temperature}</label>
                <div className="flex items-center gap-4">
                    <input
                        type="range"
                        min="0"
                        max="1"
                        step="0.1"
                        value={cfg.temperature}
                        onChange={e => setCfg({ ...cfg, temperature: parseFloat(e.target.value) })}
                        className="flex-1 accent-blue-500 h-2 bg-white/10 rounded-lg appearance-none cursor-pointer"
                    />
                    <input
                        type="number"
                        min="0"
                        max="1"
                        step="0.1"
                        value={cfg.temperature}
                        onChange={e => setCfg({ ...cfg, temperature: parseFloat(e.target.value) || 0 })}
                        className="w-16 bg-white/5 border border-white/10 rounded-xl px-2 py-1 text-center text-sm focus:outline-none focus:border-blue-500"
                    />
                </div>
            </div>
        </div>
    );

    return (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
            <motion.div
                initial={{ scale: 0.9, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                className="glass w-full max-w-2xl p-8 rounded-3xl"
            >
                <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center gap-3">
                        <Settings className="text-blue-400" />
                        <h2 className="text-2xl font-bold">{projectId ? "项目设置" : "全局设置"}</h2>
                    </div>
                </div>

                <div className="flex gap-1 bg-white/5 p-1 rounded-xl mb-6">
                    <button
                        onClick={() => setActiveTab("verification")}
                        className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${activeTab === "verification" ? "bg-blue-600 text-white" : "text-slate-400 hover:text-white"}`}
                    >
                        验证配置
                    </button>
                    <button
                        onClick={() => setActiveTab("optimization")}
                        className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${activeTab === "optimization" ? "bg-blue-600 text-white" : "text-slate-400 hover:text-white"}`}
                    >
                        优化配置
                    </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-8">
                    <div className="space-y-6">
                        <h3 className="text-lg font-semibold text-slate-200">
                            {activeTab === "verification" ? "提示词验证模型" : "提示词优化模型"}
                        </h3>
                        {activeTab === "verification"
                            ? renderConfigForm(config, setConfig, true)
                            : renderConfigForm(optConfig, setOptConfig, false)
                        }
                    </div>

                    {activeTab === "optimization" && (
                        <div className="flex flex-col h-full">
                            <div className="flex items-center justify-between mb-2">
                                <label className="block text-sm font-medium text-slate-400">优化提示词模板 (System Prompt)</label>
                                {optPrompt && (
                                    <button
                                        onClick={() => setOptPrompt("")}
                                        className="text-xs text-slate-500 hover:text-blue-400 transition-colors"
                                    >
                                        恢复默认
                                    </button>
                                )}
                            </div>
                            <textarea
                                value={optPrompt || DEFAULT_OPTIMIZATION_PROMPT}
                                onChange={e => setOptPrompt(e.target.value)}
                                className="flex-1 w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors text-sm font-mono min-h-[200px]"
                                placeholder="输入优化提示词模板..."
                            />
                            <div className="mt-2 text-xs text-slate-500 space-y-1">
                                <p>必须包含：<code className="text-blue-400">{`{old_prompt}`}</code> 和 <code className="text-blue-400">{`{error_samples}`}</code></p>
                                <p className="text-emerald-400/60">当前显示的是{optPrompt ? "自定义" : "默认"}提示词</p>
                            </div>
                        </div>
                    )}

                    {activeTab === "verification" && (
                        <div className="flex flex-col justify-center items-center p-8 bg-white/5 rounded-2xl border border-white/10">
                            <div className="text-slate-400 text-center text-sm">
                                <p className="mb-2">验证配置用于批量执行测试数据</p>
                                <p>建议将温度设置为 0 以获得稳定的结果</p>
                            </div>
                        </div>
                    )}
                </div>

                <div className="flex gap-4">
                    <button
                        onClick={handleTest}
                        disabled={isTesting}
                        className={`px-6 py-3 rounded-xl transition-colors font-medium border border-purple-500/20 flex items-center gap-2 ${isTesting
                            ? "bg-purple-500/5 text-purple-400/50 cursor-not-allowed"
                            : "bg-purple-500/10 hover:bg-purple-500/20 text-purple-400"
                            }`}
                    >
                        {isTesting && <Loader2 size={16} className="animate-spin" />}
                        {isTesting ? "测试中..." : "测试连接"}
                    </button>
                    <div className="flex-1" />
                    <button
                        onClick={onClose}
                        className="px-8 py-3 rounded-xl bg-white/5 hover:bg-white/10 transition-colors font-medium border border-white/10"
                    >
                        取消
                    </button>
                    <button
                        onClick={handleSave}
                        disabled={isSaving}
                        className={`flex items-center gap-2 px-10 py-3 rounded-xl font-medium transition-colors shadow-lg shadow-blue-900/20 ${isSaving
                            ? "bg-blue-600/50 cursor-not-allowed"
                            : "bg-blue-600 hover:bg-blue-500"
                            }`}
                    >
                        {isSaving ? <Loader2 size={18} className="animate-spin" /> : <Save size={18} />}
                        {isSaving ? "保存中..." : "保存配置"}
                    </button>
                </div>
            </motion.div>
        </div>
    );
}

