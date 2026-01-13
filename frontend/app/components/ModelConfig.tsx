"use client";
import { useState, useEffect } from "react";
import axios from "axios";
import { Settings, Save, Loader2, ChevronDown } from "lucide-react";
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

// Helper to format JSON for display
const formatJSON = (obj: any): string => {
    if (!obj) return "";
    try {
        return JSON.stringify(obj, null, 2);
    } catch (e) {
        return "";
    }
};

export default function ModelConfig({ onClose, projectId, onSave, defaultTab = "verification" }: { onClose: () => void; projectId?: string; onSave?: () => void; defaultTab?: "verification" | "optimization" }) {
    const { success, error, toast } = useToast();
    const [activeTab, setActiveTab] = useState<"verification" | "optimization">(defaultTab);

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
        temperature: 0.0,
        extra_body: "",
        default_headers: ""
    });
    const [optConfig, setOptConfig] = useState({
        base_url: "",
        api_key: "",
        max_tokens: 2000,
        timeout: 180,  // 优化任务需要更长的超时时间
        model_name: "gpt-3.5-turbo",
        temperature: 0.7,
        extra_body: "",
        default_headers: ""
    });
    const [optPrompt, setOptPrompt] = useState("");

    // 公共模型列表
    const [globalModels, setGlobalModels] = useState<any[]>([]);
    // 当前选中的公共模型ID
    const [selectedVerifyModel, setSelectedVerifyModel] = useState<string>("");
    const [selectedOptModel, setSelectedOptModel] = useState<string>("");

    useEffect(() => {
        // 获取公共模型列表
        fetchGlobalModels();
        if (projectId) {
            fetchProjectConfig();
        } else {
            fetchConfig();
        }
    }, [projectId]);

    /**
     * 监听 ESC 键关闭弹窗
     */
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent): void => {
            if (e.key === "Escape") {
                onClose();
            }
        };
        document.addEventListener("keydown", handleKeyDown);
        return () => {
            document.removeEventListener("keydown", handleKeyDown);
        };
    }, [onClose]);

    /**
     * 弹窗打开时锁定 body 滚动，防止滚动穿透
     */
    useEffect(() => {
        // 保存原始的 overflow 样式
        const originalOverflow: string = document.body.style.overflow;
        // 锁定滚动
        document.body.style.overflow = "hidden";

        return () => {
            // 恢复原始样式
            document.body.style.overflow = originalOverflow;
        };
    }, []);

    /**
     * 获取公共模型列表
     */
    const fetchGlobalModels = async (): Promise<void> => {
        try {
            const res = await axios.get(`${API_BASE}/global-models`);
            setGlobalModels(res.data);
        } catch (e) {
            console.error("获取公共模型失败", e);
        }
    };

    /**
     * 应用公共模型配置到验证配置
     * @param modelId 公共模型ID
     */
    const applyGlobalModelToVerify = (modelId: string): void => {
        const model = globalModels.find(m => m.id === modelId);
        if (model) {
            setConfig(prev => ({
                ...prev,
                base_url: model.base_url,
                api_key: model.api_key,
                model_name: model.model_name,
                max_tokens: model.max_tokens,
                temperature: model.temperature,
                timeout: model.timeout,
                extra_body: model.extra_body ? JSON.stringify(model.extra_body, null, 2) : "",
                default_headers: model.default_headers ? JSON.stringify(model.default_headers, null, 2) : ""
            }));
            setSelectedVerifyModel(modelId);
            success(`已应用配置：${model.name}`);
        }
    };

    /**
     * 应用公共模型配置到优化配置
     * @param modelId 公共模型ID
     */
    const applyGlobalModelToOpt = (modelId: string): void => {
        const model = globalModels.find(m => m.id === modelId);
        if (model) {
            setOptConfig(prev => ({
                ...prev,
                base_url: model.base_url,
                api_key: model.api_key,
                model_name: model.model_name,
                max_tokens: model.max_tokens,
                temperature: model.temperature,
                timeout: model.timeout,
                extra_body: model.extra_body ? JSON.stringify(model.extra_body, null, 2) : "",
                default_headers: model.default_headers ? JSON.stringify(model.default_headers, null, 2) : ""
            }));
            setSelectedOptModel(modelId);
            success(`已应用配置：${model.name}`);
        }
    };

    const fetchProjectConfig = async () => {
        try {
            const res = await axios.get(`${API_BASE}/projects/${projectId}`);
            if (res.data.model_config) {
                const loadedConfig = { ...res.data.model_config };
                // Convert objects to string for textarea
                if (loadedConfig.extra_body && typeof loadedConfig.extra_body === 'object') {
                    loadedConfig.extra_body = formatJSON(loadedConfig.extra_body);
                }
                if (loadedConfig.default_headers && typeof loadedConfig.default_headers === 'object') {
                    loadedConfig.default_headers = formatJSON(loadedConfig.default_headers);
                }
                setConfig(prev => ({ ...prev, ...loadedConfig }));
            }
            if (res.data.optimization_model_config) {
                const loadedOptConfig = { ...res.data.optimization_model_config };
                // Convert objects to string for textarea
                if (loadedOptConfig.extra_body && typeof loadedOptConfig.extra_body === 'object') {
                    loadedOptConfig.extra_body = formatJSON(loadedOptConfig.extra_body);
                }
                if (loadedOptConfig.default_headers && typeof loadedOptConfig.default_headers === 'object') {
                    loadedOptConfig.default_headers = formatJSON(loadedOptConfig.default_headers);
                }
                setOptConfig(prev => ({ ...prev, ...loadedOptConfig }));
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

            // Process extra_body and default_headers
            const processConfig = (cfg: any) => {
                const newCfg = { ...cfg };
                if (newCfg.extra_body) {
                    try {
                        newCfg.extra_body = JSON.parse(newCfg.extra_body);
                    } catch (e) {
                        throw new Error("Extra Body 必须是合法的 JSON");
                    }
                } else {
                    delete newCfg.extra_body;
                }
                if (newCfg.default_headers) {
                    try {
                        newCfg.default_headers = JSON.parse(newCfg.default_headers);
                    } catch (e) {
                        throw new Error("Default Headers 必须是合法的 JSON");
                    }
                } else {
                    delete newCfg.default_headers;
                }
                return newCfg;
            };

            try {
                const finalConfig = processConfig(config);
                const finalOptConfig = processConfig(optConfig);

                formData.append("model_cfg", JSON.stringify(finalConfig));
                formData.append("optimization_model_config", JSON.stringify(finalOptConfig));
                formData.append("optimization_prompt", optPrompt);
                formData.append("current_prompt", "");

                // 获取当前项目的 prompt
                const projectRes = await axios.get(`${API_BASE}/projects/${projectId}`);
                formData.set("current_prompt", projectRes.data.current_prompt);

                await axios.put(`${API_BASE}/projects/${projectId}`, formData);
                success("项目配置已保存");
                if (onSave) onSave(); // Call callback
                onClose();
            } catch (e: any) {
                error(e.message || "保存失败");
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
        formData.append("max_tokens", String(targetConfig.max_tokens));
        formData.append("temperature", String(targetConfig.temperature));

        // Add extra params
        if (targetConfig.extra_body) {
            try {
                JSON.parse(targetConfig.extra_body); // validate
                formData.append("extra_body", targetConfig.extra_body); // send as string
            } catch (e) {
                error("Extra Body 格式错误");
                setIsTesting(false);
                return;
            }
        }
        if (targetConfig.default_headers) {
            try {
                JSON.parse(targetConfig.default_headers); // validate
                formData.append("default_headers", targetConfig.default_headers); // send as string
            } catch (e) {
                error("Default Headers 格式错误");
                setIsTesting(false);
                return;
            }
        }

        if (activeTab === "verification") {
            // @ts-ignore
            formData.append("validation_mode", targetConfig.validation_mode || "llm");
            // @ts-ignore
            formData.append("interface_code", targetConfig.interface_code || "");
        }

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

    /**
     * 渲染配置表单
     * 采用分组布局，更清晰地组织配置项
     * @param cfg 配置对象
     * @param setCfg 配置更新函数
     * @param isVerification 是否为验证配置
     */
    const renderConfigForm = (cfg: any, setCfg: any, isVerification: boolean) => (
        <div className="space-y-5">
            {/* 公共模型快速选择 */}
            {globalModels.length > 0 && (
                <div className="p-4 bg-gradient-to-r from-blue-500/10 to-purple-500/10 rounded-xl border border-blue-500/20">
                    <label className="block text-sm font-medium text-blue-300 mb-2">
                        ⚡ 快速选择公共模型
                    </label>
                    <div className="relative">
                        <select
                            value={isVerification ? selectedVerifyModel : selectedOptModel}
                            onChange={e => {
                                const modelId = e.target.value;
                                if (modelId) {
                                    if (isVerification) {
                                        applyGlobalModelToVerify(modelId);
                                    } else {
                                        applyGlobalModelToOpt(modelId);
                                    }
                                }
                            }}
                            className="w-full bg-slate-800 border border-white/10 rounded-lg px-4 py-2.5 focus:outline-none focus:border-blue-500 transition-colors text-sm appearance-none cursor-pointer hover:border-white/20 text-white"
                            style={{ colorScheme: 'dark' }}
                        >
                            <option value="" className="bg-slate-800 text-white">— 选择公共模型快速填充 —</option>
                            {globalModels.map(model => (
                                <option key={model.id} value={model.id} className="bg-slate-800 text-white">
                                    {model.name} ({model.model_name})
                                </option>
                            ))}
                        </select>
                        <ChevronDown size={16} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                    </div>
                    <p className="text-xs text-slate-500 mt-2">选择后自动填充配置项，您仍可手动调整</p>
                </div>
            )}

            {/* 验证模式切换（仅验证配置显示） */}
            {isVerification && (
                <div className="bg-white/5 p-1 rounded-lg flex">
                    <button
                        onClick={() => setCfg({ ...cfg, validation_mode: "llm" })}
                        className={`flex-1 py-2 rounded-md text-xs font-medium transition-colors ${!cfg.validation_mode || cfg.validation_mode === "llm" ? "bg-blue-600 text-white" : "text-slate-400 hover:text-white"}`}
                    >
                        模型直接验证 (LLM)
                    </button>
                    <button
                        onClick={() => setCfg({ ...cfg, validation_mode: "interface" })}
                        className={`flex-1 py-2 rounded-md text-xs font-medium transition-colors ${cfg.validation_mode === "interface" ? "bg-blue-600 text-white" : "text-slate-400 hover:text-white"}`}
                    >
                        接口调用验证 (Interface)
                    </button>
                </div>
            )}

            {/* 基础连接配置 */}
            <div className="space-y-3">
                <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">连接配置</h4>
                <div>
                    <label className="block text-sm font-medium text-slate-400 mb-1.5">
                        {cfg.validation_mode === "interface" ? "Interface URL" : "Base URL"}
                    </label>
                    <input
                        type="text"
                        value={cfg.base_url}
                        onChange={e => setCfg({ ...cfg, base_url: e.target.value })}
                        className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500 transition-colors text-sm"
                        placeholder={cfg.validation_mode === "interface" ? "https://api.example.com/check" : "https://api.openai.com/v1"}
                    />
                </div>
                {(!isVerification || cfg.validation_mode !== "interface") && (
                    <div>
                        <label className="block text-sm font-medium text-slate-400 mb-1.5">API Key</label>
                        <input
                            type="password"
                            value={cfg.api_key}
                            onChange={e => setCfg({ ...cfg, api_key: e.target.value })}
                            className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500 transition-colors text-sm"
                            placeholder="sk-..."
                        />
                    </div>
                )}
            </div>

            {/* LLM 模型参数 */}
            {(!cfg.validation_mode || cfg.validation_mode === "llm") && (
                <div className="space-y-3">
                    <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">模型参数</h4>
                    <div className="grid grid-cols-2 gap-3">
                        <div>
                            <label className="block text-sm font-medium text-slate-400 mb-1.5">模型名称</label>
                            <input
                                type="text"
                                value={cfg.model_name}
                                onChange={e => setCfg({ ...cfg, model_name: e.target.value })}
                                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500 transition-colors text-sm"
                                placeholder="gpt-3.5-turbo"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-slate-400 mb-1.5">温度</label>
                            <div className="flex items-center gap-2">
                                <input
                                    type="range"
                                    min="0"
                                    max="1"
                                    step="0.1"
                                    value={cfg.temperature}
                                    onChange={e => setCfg({ ...cfg, temperature: parseFloat(e.target.value) })}
                                    className="flex-1 accent-blue-500 h-1.5 bg-white/10 rounded-lg appearance-none cursor-pointer"
                                />
                                <span className="w-10 text-center text-sm text-slate-300 bg-white/5 rounded px-2 py-1">{cfg.temperature}</span>
                            </div>
                        </div>
                    </div>
                    <div className="grid grid-cols-3 gap-3">
                        <div>
                            <label className="block text-sm font-medium text-slate-400 mb-1.5">最大 Token</label>
                            <input
                                type="text"
                                inputMode="numeric"
                                value={cfg.max_tokens}
                                onChange={e => {
                                    const val = e.target.value;
                                    if (val === '' || /^\d*$/.test(val)) {
                                        setCfg({ ...cfg, max_tokens: val === '' ? '' : parseInt(val) });
                                    }
                                }}
                                onBlur={e => {
                                    const val = parseInt(e.target.value);
                                    setCfg({ ...cfg, max_tokens: isNaN(val) || val <= 0 ? 2000 : val });
                                }}
                                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500 transition-colors text-sm"
                                placeholder="2000"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-slate-400 mb-1.5">超时 (秒)</label>
                            <input
                                type="text"
                                inputMode="numeric"
                                value={cfg.timeout}
                                onChange={e => {
                                    const val = e.target.value;
                                    if (val === '' || /^\d*$/.test(val)) {
                                        setCfg({ ...cfg, timeout: val === '' ? '' : parseInt(val) });
                                    }
                                }}
                                onBlur={e => {
                                    const val = parseInt(e.target.value);
                                    setCfg({ ...cfg, timeout: isNaN(val) || val <= 0 ? 60 : val });
                                }}
                                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500 transition-colors text-sm"
                                placeholder="60"
                            />
                        </div>
                        {isVerification && (
                            <div>
                                <label className="block text-sm font-medium text-slate-400 mb-1.5">并发度</label>
                                <input
                                    type="text"
                                    inputMode="numeric"
                                    value={cfg.concurrency}
                                    onChange={e => {
                                        const val = e.target.value;
                                        if (val === '' || /^\d*$/.test(val)) {
                                            setCfg({ ...cfg, concurrency: val === '' ? '' : parseInt(val) });
                                        }
                                    }}
                                    onBlur={e => {
                                        const val = parseInt(e.target.value);
                                        const finalVal = isNaN(val) || val < 1 ? 5 : Math.min(val, 50);
                                        setCfg({ ...cfg, concurrency: finalVal });
                                    }}
                                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500 transition-colors text-sm"
                                    placeholder="5"
                                />
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* 接口模式配置 */}
            {cfg.validation_mode === "interface" && (
                <div className="space-y-3">
                    <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">接口配置</h4>
                    <div className="grid grid-cols-2 gap-3">
                        <div>
                            <label className="block text-sm font-medium text-slate-400 mb-1.5">超时 (秒)</label>
                            <input
                                type="text"
                                inputMode="numeric"
                                value={cfg.timeout}
                                onChange={e => {
                                    const val = e.target.value;
                                    if (val === '' || /^\d*$/.test(val)) {
                                        setCfg({ ...cfg, timeout: val === '' ? '' : parseInt(val) });
                                    }
                                }}
                                onBlur={e => {
                                    const val = parseInt(e.target.value);
                                    setCfg({ ...cfg, timeout: isNaN(val) || val <= 0 ? 60 : val });
                                }}
                                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500 transition-colors text-sm"
                                placeholder="60"
                            />
                        </div>
                        {isVerification && (
                            <div>
                                <label className="block text-sm font-medium text-slate-400 mb-1.5">并发度</label>
                                <input
                                    type="text"
                                    inputMode="numeric"
                                    value={cfg.concurrency}
                                    onChange={e => {
                                        const val = e.target.value;
                                        if (val === '' || /^\d*$/.test(val)) {
                                            setCfg({ ...cfg, concurrency: val === '' ? '' : parseInt(val) });
                                        }
                                    }}
                                    onBlur={e => {
                                        const val = parseInt(e.target.value);
                                        const finalVal = isNaN(val) || val < 1 ? 5 : Math.min(val, 50);
                                        setCfg({ ...cfg, concurrency: finalVal });
                                    }}
                                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500 transition-colors text-sm"
                                    placeholder="5"
                                />
                            </div>
                        )}
                    </div>
                    <div>
                        <div className="flex justify-between items-center mb-1.5">
                            <label className="block text-sm font-medium text-slate-400">参数转换脚本 (Python)</label>
                            <span className="text-xs text-slate-500">query/target/prompt → params</span>
                        </div>
                        <textarea
                            value={cfg.interface_code || ""}
                            onChange={e => setCfg({ ...cfg, interface_code: e.target.value })}
                            className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500 transition-colors text-sm font-mono h-[120px]"
                            placeholder={`# Available variables: query, target, prompt\nparams = {\n    "messages": [{"role": "user", "content": query}]\n}`}
                        />
                    </div>
                </div>
            )}

            {/* 高级配置（可折叠的JSON配置） */}
            {(!cfg.validation_mode || cfg.validation_mode === "llm") && (
                <details className="group">
                    <summary className="text-xs font-semibold text-slate-500 uppercase tracking-wider cursor-pointer hover:text-slate-400 transition-colors flex items-center gap-2">
                        <ChevronDown size={14} className="transform group-open:rotate-180 transition-transform" />
                        高级配置
                    </summary>
                    <div className="mt-3 grid grid-cols-2 gap-3">
                        <div>
                            <label className="block text-sm font-medium text-slate-400 mb-1.5">Extra Body (JSON)</label>
                            <textarea
                                value={cfg.extra_body || ""}
                                onChange={e => setCfg({ ...cfg, extra_body: e.target.value })}
                                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500 transition-colors text-sm font-mono h-[80px]"
                                placeholder={`{"top_k": 40}`}
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-slate-400 mb-1.5">Default Headers</label>
                            <textarea
                                value={cfg.default_headers || ""}
                                onChange={e => setCfg({ ...cfg, default_headers: e.target.value })}
                                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500 transition-colors text-sm font-mono h-[80px]"
                                placeholder={`{"X-Header": "value"}`}
                            />
                        </div>
                    </div>
                </details>
            )}
        </div>
    );

    return (
        <div
            className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50"
            onClick={(e) => {
                // 点击遮罩层关闭弹窗
                if (e.target === e.currentTarget) {
                    onClose();
                }
            }}
            onWheel={(e) => {
                // 阻止滚动事件穿透到外层
                e.stopPropagation();
            }}
        >
            <motion.div
                initial={{ scale: 0.9, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                className="glass w-full max-w-4xl rounded-2xl flex flex-col max-h-[90vh]"
                onWheel={(e) => {
                    // 阻止滚动事件穿透到外层
                    e.stopPropagation();
                }}
            >
                {/* 固定头部 */}
                <div className="flex items-center justify-between p-6 border-b border-white/10 flex-shrink-0">
                    <div className="flex items-center gap-3">
                        <Settings className="text-blue-400" />
                        <h2 className="text-xl font-bold">{projectId ? "项目配置" : "全局配置"}</h2>
                    </div>
                    {/* Tab 切换 */}
                    <div className="flex gap-1 bg-white/5 p-1 rounded-lg">
                        <button
                            onClick={() => setActiveTab("verification")}
                            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${activeTab === "verification" ? "bg-blue-600 text-white" : "text-slate-400 hover:text-white"}`}
                        >
                            验证配置
                        </button>
                        <button
                            onClick={() => setActiveTab("optimization")}
                            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${activeTab === "optimization" ? "bg-blue-600 text-white" : "text-slate-400 hover:text-white"}`}
                        >
                            优化配置
                        </button>
                    </div>
                </div>

                {/* 可滚动内容区域 */}
                <div className="flex-1 overflow-y-auto p-6 custom-scrollbar">
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        {/* 左侧：模型配置 */}
                        <div className="space-y-4">
                            <h3 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
                                <span className="w-1.5 h-1.5 bg-blue-500 rounded-full"></span>
                                {activeTab === "verification" ? "验证模型配置" : "优化模型配置"}
                            </h3>
                            {activeTab === "verification"
                                ? renderConfigForm(config, setConfig, true)
                                : renderConfigForm(optConfig, setOptConfig, false)
                            }
                        </div>

                        {/* 右侧：提示词模板 / 说明 */}
                        {activeTab === "optimization" ? (
                            <div className="space-y-4">
                                <div className="flex items-center justify-between">
                                    <h3 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
                                        <span className="w-1.5 h-1.5 bg-purple-500 rounded-full"></span>
                                        优化提示词模板
                                    </h3>
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
                                    className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors text-sm font-mono h-[350px] resize-none"
                                    placeholder="输入优化提示词模板..."
                                />
                                <div className="text-xs text-slate-500 space-y-1">
                                    <p>必须包含：<code className="text-blue-400 bg-blue-500/10 px-1 rounded">{`{old_prompt}`}</code> 和 <code className="text-blue-400 bg-blue-500/10 px-1 rounded">{`{error_samples}`}</code></p>
                                    <p className="text-emerald-400/60">当前显示的是{optPrompt ? "自定义" : "默认"}提示词</p>
                                </div>
                            </div>
                        ) : (
                            <div className="flex flex-col justify-center items-center p-8 bg-gradient-to-br from-blue-500/5 to-purple-500/5 rounded-xl border border-white/5">
                                <div className="text-center space-y-4">
                                    <div className="w-16 h-16 mx-auto bg-blue-500/10 rounded-full flex items-center justify-center">
                                        <Settings size={28} className="text-blue-400" />
                                    </div>
                                    <div className="text-slate-400 text-sm space-y-2">
                                        <p className="font-medium text-slate-300">验证配置说明</p>
                                        <p>用于批量执行测试数据验证</p>
                                        <p className="text-xs text-slate-500">建议将温度设置为 0 以获得稳定结果</p>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {/* 固定底部操作栏 */}
                <div className="flex gap-3 p-6 border-t border-white/10 flex-shrink-0 bg-black/20">
                    <button
                        onClick={handleTest}
                        disabled={isTesting}
                        className={`px-5 py-2.5 rounded-lg transition-colors font-medium border border-purple-500/20 flex items-center gap-2 text-sm ${isTesting
                            ? "bg-purple-500/5 text-purple-400/50 cursor-not-allowed"
                            : "bg-purple-500/10 hover:bg-purple-500/20 text-purple-400"
                            }`}
                    >
                        {isTesting && <Loader2 size={14} className="animate-spin" />}
                        {isTesting ? "测试中..." : "测试连接"}
                    </button>
                    <div className="flex-1" />
                    <button
                        onClick={onClose}
                        className="px-6 py-2.5 rounded-lg bg-white/5 hover:bg-white/10 transition-colors font-medium border border-white/10 text-sm"
                    >
                        取消
                    </button>
                    <button
                        onClick={handleSave}
                        disabled={isSaving}
                        className={`flex items-center gap-2 px-8 py-2.5 rounded-lg font-medium transition-colors shadow-lg shadow-blue-900/20 text-sm ${isSaving
                            ? "bg-blue-600/50 cursor-not-allowed"
                            : "bg-blue-600 hover:bg-blue-500"
                            }`}
                    >
                        {isSaving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
                        {isSaving ? "保存中..." : "保存配置"}
                    </button>
                </div>
            </motion.div>
        </div>
    );
}

