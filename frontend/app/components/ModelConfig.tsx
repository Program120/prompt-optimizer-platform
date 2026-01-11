"use client";
import { useState, useEffect } from "react";
import axios from "axios";
import { Settings, Save } from "lucide-react";
import { motion } from "framer-motion";

const API_BASE = "http://127.0.0.1:8000";

export default function ModelConfig({ onClose, projectId }: { onClose: () => void; projectId?: string }) {
    const [activeTab, setActiveTab] = useState<"verification" | "optimization">("verification");
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

    const handleSave = async () => {
        // 验证优化提示词
        if (activeTab === "optimization" && optPrompt) {
            if (!optPrompt.includes("{old_prompt}") || !optPrompt.includes("{error_samples}")) {
                alert("提示词优化模板必须包含 {old_prompt} 和 {error_samples} 占位符");
                return;
            }
        }

        if (projectId) {
            // 保存到项目
            const formData = new FormData();
            formData.append("model_cfg", JSON.stringify(config));
            formData.append("optimization_model_config", JSON.stringify(optConfig));
            formData.append("optimization_prompt", optPrompt);
            formData.append("current_prompt", ""); // 此时不修改当前提示词，但后端接口定义了必传，发空字符串或获取当前的

            // 为了安全，我们通常还是获取一下当前 prompt 或者让后端接口兼容
            // 由于后端 router 定义了 current_prompt = Form(...)，我们需要传一下
            try {
                const projectRes = await axios.get(`${API_BASE}/projects/${projectId}`);
                formData.set("current_prompt", projectRes.data.current_prompt);

                await axios.put(`${API_BASE}/projects/${projectId}`, formData);
                alert("项目配置已保存");
                onClose();
            } catch (e) { alert("保存失败"); }
        } else {
            // 保存全局 (保留后备逻辑)
            const formData = new FormData();
            formData.append("base_url", config.base_url);
            formData.append("api_key", config.api_key);
            formData.append("max_tokens", String(config.max_tokens));
            formData.append("timeout", String(config.timeout));
            formData.append("model_name", config.model_name);
            formData.append("concurrency", String(config.concurrency));
            formData.append("temperature", String(config.temperature));
            try {
                await axios.post(`${API_BASE}/config`, formData);
                alert("全局配置已保存");
                onClose();
            } catch (e) { alert("保存失败"); }
        }
    };

    const handleTest = async () => {
        const targetConfig = activeTab === "verification" ? config : optConfig;
        const formData = new FormData();
        formData.append("base_url", targetConfig.base_url);
        formData.append("api_key", targetConfig.api_key);
        formData.append("model_name", targetConfig.model_name);

        try {
            const res = await axios.post(`${API_BASE}/config/test`, formData);
            alert(res.data.message);
        } catch (e) { alert("测试请求失败"); }
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
                            <label className="block text-sm font-medium text-slate-400 mb-2">优化提示词模板 (System Prompt)</label>
                            <textarea
                                value={optPrompt}
                                onChange={e => setOptPrompt(e.target.value)}
                                className="flex-1 w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors text-sm font-mono"
                                placeholder="输入优化提示词模板..."
                            />
                            <div className="mt-2 text-xs text-slate-500 space-y-1">
                                <p>必须包含：<code className="text-blue-400">{`{old_prompt}`}</code> 和 <code className="text-blue-400">{`{error_samples}`}</code></p>
                                <p>提示：系统会默认提供一份，留空则使用默认值。</p>
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
                        className="px-6 py-3 rounded-xl bg-purple-500/10 hover:bg-purple-500/20 text-purple-400 transition-colors font-medium border border-purple-500/20"
                    >
                        测试连接
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
                        className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 px-10 py-3 rounded-xl font-medium transition-colors shadow-lg shadow-blue-900/20"
                    >
                        <Save size={18} />
                        保存配置
                    </button>
                </div>
            </motion.div>
        </div>
    );
}

