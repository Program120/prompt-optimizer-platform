"use client";

import { useState, useEffect } from "react";
import axios from "axios";
import { Settings, Plus, Trash2, Edit2, Save, X, Loader2, Check, Copy, AlertTriangle } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useToast } from "./ui/Toast";

/**
 * API基础路径
 */
const API_BASE: string = "/api";

/**
 * 公共模型配置接口定义
 */
interface GlobalModel {
    id: string;
    name: string;
    base_url: string;
    api_key: string;
    model_name: string;
    protocol: string;
    max_tokens: number;
    temperature: number;
    timeout: number;
    do_sample: boolean;
    extra_body?: Record<string, any> | null;
    default_headers?: Record<string, any> | null;
    created_at: string;
    updated_at: string;
}

/**
 * 组件属性接口
 */
interface GlobalModelsConfigProps {
    onClose: () => void;
}

/**
 * 公共模型配置管理组件
 * 用于管理全局共享的模型配置
 */
export default function GlobalModelsConfig({ onClose }: GlobalModelsConfigProps) {
    const { success, error } = useToast();

    // 模型列表
    const [models, setModels] = useState<GlobalModel[]>([]);
    // 加载状态
    const [loading, setLoading] = useState<boolean>(true);
    // 当前编辑的模型ID（null表示新建）
    const [editingId, setEditingId] = useState<string | null>(null);
    // 是否处于新建模式
    const [isCreating, setIsCreating] = useState<boolean>(false);
    // 保存中状态
    const [saving, setSaving] = useState<boolean>(false);
    // 测试连接状态
    const [testing, setTesting] = useState<string | null>(null);
    // 是否显示退出确认弹窗
    const [showExitConfirm, setShowExitConfirm] = useState<boolean>(false);

    // 编辑表单数据
    // 数值字段使用字符串存储，便于用户清空后重新输入
    const [formData, setFormData] = useState({
        name: "",
        base_url: "",
        api_key: "",
        model_name: "gpt-3.5-turbo",
        protocol: "openai",
        max_tokens: "2000",
        temperature: "0",
        timeout: "60",
        do_sample: false,
        extra_body: "",
        default_headers: ""
    });

    /**
     * 组件挂载时获取模型列表
     */
    useEffect(() => {
        fetchModels();
    }, []);

    /**
     * 获取所有公共模型配置
     */
    const fetchModels = async (): Promise<void> => {
        try {
            const res = await axios.get(`${API_BASE}/global-models`);
            setModels(res.data);
        } catch (e) {
            console.error("获取公共模型失败", e);
            error("获取公共模型失败");
        } finally {
            setLoading(false);
        }
    };

    /**
     * 开始新建模型
     */
    const startCreate = (): void => {
        setIsCreating(true);
        setEditingId(null);
        setFormData({
            name: "",
            base_url: "",
            api_key: "",
            model_name: "gpt-3.5-turbo",
            protocol: "openai",
            max_tokens: "2000",
            temperature: "0",
            timeout: "60",
            do_sample: false,
            extra_body: "",
            default_headers: ""
        });
    };

    /**
     * 开始编辑模型
     * @param model 要编辑的模型
     */
    const startEdit = (model: GlobalModel): void => {
        setEditingId(model.id);
        setIsCreating(false);
        setFormData({
            name: model.name,
            base_url: model.base_url,
            api_key: model.api_key,
            model_name: model.model_name,
            protocol: model.protocol || "openai",
            max_tokens: String(model.max_tokens),
            temperature: String(model.temperature),
            timeout: String(model.timeout),
            do_sample: model.do_sample ?? false,
            extra_body: model.extra_body ? JSON.stringify(model.extra_body, null, 2) : "",
            default_headers: model.default_headers ? JSON.stringify(model.default_headers, null, 2) : ""
        });
    };

    /**
     * 取消编辑/新建
     */
    const cancelEdit = (): void => {
        setEditingId(null);
        setIsCreating(false);
    };

    /**
     * 保存模型配置
     * @returns 是否保存成功
     */
    const handleSave = async (): Promise<boolean> => {
        if (!formData.name.trim()) {
            error("请输入模型名称");
            return false;
        }
        if (!formData.base_url.trim()) {
            error("请输入 Base URL");
            return false;
        }

        setSaving(true);

        try {
            // 处理 extra_body 和 default_headers
            let extraBody: Record<string, any> | null = null;
            let defaultHeaders: Record<string, any> | null = null;

            if (formData.extra_body.trim()) {
                try {
                    extraBody = JSON.parse(formData.extra_body);
                } catch {
                    error("Extra Body 格式错误，请输入有效的 JSON");
                    setSaving(false);
                    return false;
                }
            }

            if (formData.default_headers.trim()) {
                try {
                    defaultHeaders = JSON.parse(formData.default_headers);
                } catch {
                    error("Default Headers 格式错误，请输入有效的 JSON");
                    setSaving(false);
                    return false;
                }
            }

            // 将字符串转换为数字，空值使用默认值
            const maxTokensValue: number = formData.max_tokens.trim() === "" ? 2000 : parseInt(formData.max_tokens);
            const temperatureValue: number = formData.temperature.trim() === "" ? 0 : parseFloat(formData.temperature);
            const timeoutValue: number = formData.timeout.trim() === "" ? 60 : parseInt(formData.timeout);

            const payload = {
                name: formData.name,
                base_url: formData.base_url,
                api_key: formData.api_key,
                model_name: formData.model_name,
                protocol: formData.protocol,
                max_tokens: isNaN(maxTokensValue) ? 2000 : maxTokensValue,
                temperature: isNaN(temperatureValue) ? 0 : temperatureValue,
                timeout: isNaN(timeoutValue) ? 60 : timeoutValue,
                do_sample: formData.do_sample,
                extra_body: extraBody,
                default_headers: defaultHeaders
            };

            if (isCreating) {
                // 新建
                await axios.post(`${API_BASE}/global-models`, payload);
                success("模型配置已创建");
            } else if (editingId) {
                // 更新
                await axios.put(`${API_BASE}/global-models/${editingId}`, payload);
                success("模型配置已更新");
            }

            await fetchModels();
            cancelEdit();
            return true;
        } catch (e) {
            console.error("保存失败", e);
            error("保存失败");
            return false;
        } finally {
            setSaving(false);
        }
    };

    /**
     * 删除模型配置
     * @param modelId 模型ID
     */
    const handleDelete = async (modelId: string): Promise<void> => {
        if (!confirm("确定要删除这个模型配置吗？")) {
            return;
        }

        try {
            await axios.delete(`${API_BASE}/global-models/${modelId}`);
            success("模型配置已删除");
            await fetchModels();
        } catch (e) {
            console.error("删除失败", e);
            error("删除失败");
        }
    };

    /**
     * 复制模型配置
     * @param model 要复制的模型
     */
    const handleCopy = async (model: GlobalModel): Promise<void> => {
        setSaving(true);
        try {
            // 生成新名称：名称 - 复制
            const newName = `${model.name} - 复制`;

            const payload = {
                name: newName,
                base_url: model.base_url,
                api_key: model.api_key,
                model_name: model.model_name,
                protocol: model.protocol || "openai",
                max_tokens: model.max_tokens,
                temperature: model.temperature,
                timeout: model.timeout,
                do_sample: model.do_sample,
                extra_body: model.extra_body,
                default_headers: model.default_headers
            };

            await axios.post(`${API_BASE}/global-models`, payload);
            success("模型配置已复制");
            await fetchModels();
        } catch (e) {
            console.error("复制失败", e);
            error("复制失败");
        } finally {
            setSaving(false);
        }
    };

    /**
     * 测试模型连接
     * @param model 要测试的模型
     */
    const handleTest = async (model: GlobalModel): Promise<void> => {
        setTesting(model.id);

        const testFormData = new FormData();
        testFormData.append("base_url", model.base_url);
        testFormData.append("api_key", model.api_key);
        testFormData.append("model_name", model.model_name);
        testFormData.append("protocol", model.protocol || "openai");
        testFormData.append("max_tokens", "5");
        testFormData.append("temperature", String(model.temperature));

        if (model.extra_body) {
            testFormData.append("extra_body", JSON.stringify(model.extra_body));
        }
        if (model.default_headers) {
            testFormData.append("default_headers", JSON.stringify(model.default_headers));
        }

        try {
            const res = await axios.post(`${API_BASE}/config/test`, testFormData);
            if (res.data.status === "success") {
                success(res.data.message || "连接成功");
            } else {
                error(res.data.message || "连接失败");
            }
        } catch (e) {
            error("测试请求失败");
        } finally {
            setTesting(null);
        }
    };

    /**
     * 处理关闭请求
     * 如果有未保存的内容，显示确认弹窗
     */
    const handleCloseRequest = () => {
        if (isCreating || editingId) {
            setShowExitConfirm(true);
        } else {
            onClose();
        }
    };

    /**
     * 退出并保存
     */
    const handleSaveAndExit = async () => {
        const result = await handleSave();
        if (result) {
            setShowExitConfirm(false);
            onClose();
        }
    };

    /**
     * 直接退出（不保存）
     */
    const handleForceExit = () => {
        setShowExitConfirm(false);
        onClose();
    };

    /**
     * 渲染编辑表单
     */
    const renderForm = () => (
        <div className="space-y-4 p-4 bg-white/5 rounded-xl border border-white/10">
            <div className="grid grid-cols-2 gap-4">
                {/* 协议选择 */}
                <div>
                    <label className="block text-sm font-medium text-slate-400 mb-2">协议类型</label>
                    <select
                        value={formData.protocol}
                        onChange={e => setFormData({ ...formData, protocol: e.target.value })}
                        className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2 focus:outline-none focus:border-blue-500 text-sm appearance-none cursor-pointer"
                    >
                        <option value="openai" className="bg-slate-800">OpenAI (及兼容)</option>
                        <option value="anthropic" className="bg-slate-800">Anthropic</option>
                        <option value="gemini" className="bg-slate-800">Google Gemini</option>
                    </select>
                </div>
                {/* 配置名称 */}
                <div>
                    <label className="block text-sm font-medium text-slate-400 mb-2">配置名称</label>
                    <input
                        type="text"
                        value={formData.name}
                        onChange={e => setFormData({ ...formData, name: e.target.value })}
                        className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2 focus:outline-none focus:border-blue-500 text-sm"
                        placeholder="例如：GPT-4 生产环境"
                    />
                </div>
                {/* 模型名称 */}
                <div>
                    <label className="block text-sm font-medium text-slate-400 mb-2">模型名称</label>
                    <input
                        type="text"
                        value={formData.model_name}
                        onChange={e => setFormData({ ...formData, model_name: e.target.value })}
                        className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2 focus:outline-none focus:border-blue-500 text-sm"
                        placeholder="gpt-3.5-turbo"
                    />
                </div>
            </div>

            {/* Base URL */}
            <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">Base URL</label>
                <input
                    type="text"
                    value={formData.base_url}
                    onChange={e => setFormData({ ...formData, base_url: e.target.value })}
                    className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2 focus:outline-none focus:border-blue-500 text-sm"
                    placeholder="https://api.openai.com/v1"
                />
            </div>

            {/* API Key */}
            <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">API Key</label>
                <input
                    type="password"
                    value={formData.api_key}
                    onChange={e => setFormData({ ...formData, api_key: e.target.value })}
                    className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2 focus:outline-none focus:border-blue-500 text-sm"
                    placeholder="sk-..."
                />
            </div>

            {/* 其他参数 */}
            <div className="grid grid-cols-3 gap-4">
                <div>
                    <label className="block text-sm font-medium text-slate-400 mb-2">Max Tokens</label>
                    <input
                        type="number"
                        value={formData.max_tokens}
                        onChange={e => setFormData({ ...formData, max_tokens: e.target.value })}
                        className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2 focus:outline-none focus:border-blue-500 text-sm"
                        placeholder="2000"
                    />
                </div>
                <div>
                    <label className="block text-sm font-medium text-slate-400 mb-2">Temperature</label>
                    <input
                        type="text"
                        inputMode="decimal"
                        value={formData.temperature}
                        onChange={e => {
                            const val = e.target.value;
                            // 允许输入小数点和数字
                            if (val === '' || /^[0-9]*\.?[0-9]*$/.test(val)) {
                                setFormData({ ...formData, temperature: val });
                            }
                        }}
                        onBlur={e => {
                            const val = parseFloat(e.target.value);
                            // 限制范围 0-2，默认 0
                            const finalVal = isNaN(val) ? 0 : Math.min(Math.max(val, 0), 2);
                            setFormData({ ...formData, temperature: String(finalVal) });
                        }}
                        className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2 focus:outline-none focus:border-blue-500 text-sm"
                        placeholder="0"
                    />
                </div>
                <div>
                    <label className="block text-sm font-medium text-slate-400 mb-2">Timeout (秒)</label>
                    <input
                        type="number"
                        value={formData.timeout}
                        onChange={e => setFormData({ ...formData, timeout: e.target.value })}
                        className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2 focus:outline-none focus:border-blue-500 text-sm"
                        placeholder="60"
                    />
                </div>
            </div>

            {/* 高级设置（可折叠） */}
            <details className="group">
                <summary className="text-xs font-semibold text-slate-500 uppercase tracking-wider cursor-pointer hover:text-slate-400 transition-colors flex items-center gap-2 mb-3">
                    <span className="transform group-open:rotate-90 transition-transform">▶</span>
                    高级设置
                </summary>
                <div className="space-y-4 pl-4 border-l-2 border-white/10">
                    {/* Do Sample 开关 */}
                    <div className="flex items-center justify-between p-3 bg-white/5 rounded-xl border border-white/10">
                        <div>
                            <div className="flex items-center gap-2">
                                <label className="block text-sm font-medium text-slate-300">Do Sample</label>
                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400 border border-amber-500/30">
                                    部分模型可用
                                </span>
                            </div>
                            <p className="text-xs text-slate-500 mt-0.5">是否启用采样模式</p>
                        </div>
                        <button
                            onClick={() => setFormData({ ...formData, do_sample: !formData.do_sample })}
                            className={`relative w-11 h-6 rounded-full transition-colors flex-shrink-0 ${formData.do_sample ? "bg-blue-600" : "bg-slate-600"}`}
                        >
                            <span className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full transition-transform ${formData.do_sample ? "translate-x-5" : "translate-x-0"}`} />
                        </button>
                    </div>

                    {/* Extra Body */}
                    <div>
                        <label className="block text-sm font-medium text-slate-400 mb-2">Extra Body (JSON)</label>
                        <textarea
                            value={formData.extra_body}
                            onChange={e => setFormData({ ...formData, extra_body: e.target.value })}
                            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2 focus:outline-none focus:border-blue-500 text-sm font-mono h-20"
                            placeholder='{"top_k": 40}'
                        />
                    </div>

                    {/* Default Headers */}
                    <div>
                        <label className="block text-sm font-medium text-slate-400 mb-2">Default Headers (JSON)</label>
                        <textarea
                            value={formData.default_headers}
                            onChange={e => setFormData({ ...formData, default_headers: e.target.value })}
                            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2 focus:outline-none focus:border-blue-500 text-sm font-mono h-20"
                            placeholder='{"X-Custom-Header": "value"}'
                        />
                    </div>
                </div>
            </details>

            {/* 操作按钮 */}
            <div className="flex gap-3 pt-2">
                <button
                    onClick={cancelEdit}
                    className="px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-slate-400 text-sm transition-colors"
                >
                    取消
                </button>
                <button
                    onClick={() => handleSave()}
                    disabled={saving}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm transition-colors disabled:opacity-50"
                >
                    {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                    {isCreating ? "创建" : "保存"}
                </button>
            </div>
        </div>
    );

    return (
        <div
            className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50"
            onClick={handleCloseRequest}
        >
            <motion.div
                initial={{ scale: 0.9, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                className="glass w-full max-w-3xl p-8 rounded-3xl max-h-[85vh] overflow-hidden flex flex-col relative"
                onClick={(e) => e.stopPropagation()}
            >
                {/* 标题栏 */}
                <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center gap-3">
                        <Settings className="text-blue-400" />
                        <h2 className="text-2xl font-bold">公共模型配置</h2>
                    </div>
                    <button
                        onClick={handleCloseRequest}
                        className="p-2 hover:bg-white/10 rounded-lg transition-colors"
                    >
                        <X size={20} className="text-slate-400" />
                    </button>
                </div>

                {/* 内容区域 */}
                <div className="flex-1 overflow-y-auto space-y-4">
                    {loading ? (
                        <div className="flex justify-center py-12">
                            <Loader2 className="animate-spin text-blue-500" size={32} />
                        </div>
                    ) : (
                        <>
                            {/* 新建/编辑表单 */}
                            {(isCreating || editingId) && renderForm()}

                            {/* 模型列表 */}
                            <AnimatePresence>
                                {models.map(model => (
                                    <motion.div
                                        key={model.id}
                                        initial={{ opacity: 0, y: 10 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        exit={{ opacity: 0, y: -10 }}
                                        className={`p-4 rounded-xl border transition-colors ${editingId === model.id
                                            ? "border-blue-500/50 bg-blue-500/10"
                                            : "border-white/10 bg-white/5 hover:border-white/20"
                                            }`}
                                    >
                                        {editingId === model.id ? (
                                            renderForm()
                                        ) : (
                                            <div className="flex items-center justify-between gap-4">
                                                {/* 添加 min-w-0 和 overflow-hidden 确保 flex 子项可以正确收缩 */}
                                                <div className="flex-1 min-w-0 overflow-hidden">
                                                    <div className="flex items-center gap-3 mb-1">
                                                        {/* 配置名称：最大宽度50%并截断 */}
                                                        <h3 className="font-semibold text-lg truncate max-w-[50%]" title={model.name}>
                                                            {model.name}
                                                        </h3>
                                                        {/* 模型名称：使用 flex-shrink-0 防止过度收缩，但添加 max-w 限制 */}
                                                        <span className="text-xs px-2 py-0.5 bg-slate-700 rounded-full text-slate-300 truncate max-w-[40%] flex-shrink-0" title={model.model_name}>
                                                            {model.model_name}
                                                        </span>
                                                        <span className="text-xs px-2 py-0.5 bg-blue-500/20 text-blue-300 rounded-full truncate flex-shrink-0">
                                                            {model.protocol || "openai"}
                                                        </span>
                                                    </div>
                                                    {/* URL 截断显示 */}
                                                    <p className="text-sm text-slate-400 truncate" title={model.base_url}>
                                                        {model.base_url}
                                                    </p>
                                                </div>
                                                {/* 操作按钮：不收缩 */}
                                                <div className="flex items-center gap-2 flex-shrink-0">
                                                    <button
                                                        onClick={() => handleTest(model)}
                                                        disabled={testing === model.id}
                                                        className="p-2 hover:bg-white/10 rounded-lg transition-colors text-emerald-400 disabled:opacity-50"
                                                        title="测试连接"
                                                    >
                                                        {testing === model.id ? (
                                                            <Loader2 size={16} className="animate-spin" />
                                                        ) : (
                                                            <Check size={16} />
                                                        )}
                                                    </button>
                                                    <button
                                                        onClick={() => handleCopy(model)}
                                                        className="p-2 hover:bg-white/10 rounded-lg transition-colors text-slate-400"
                                                        title="复制配置"
                                                    >
                                                        <Copy size={16} />
                                                    </button>
                                                    <button
                                                        onClick={() => startEdit(model)}
                                                        className="p-2 hover:bg-white/10 rounded-lg transition-colors text-blue-400"
                                                        title="编辑"
                                                    >
                                                        <Edit2 size={16} />
                                                    </button>
                                                    <button
                                                        onClick={() => handleDelete(model.id)}
                                                        className="p-2 hover:bg-white/10 rounded-lg transition-colors text-red-400"
                                                        title="删除"
                                                    >
                                                        <Trash2 size={16} />
                                                    </button>
                                                </div>
                                            </div>
                                        )}
                                    </motion.div>
                                ))}
                            </AnimatePresence>

                            {/* 空状态 */}
                            {models.length === 0 && !isCreating && (
                                <div className="text-center py-12 text-slate-400">
                                    <Settings size={48} className="mx-auto mb-4 opacity-30" />
                                    <p>还没有公共模型配置</p>
                                    <p className="text-sm mt-1">点击下方按钮添加第一个配置</p>
                                </div>
                            )}
                        </>
                    )}
                </div>

                {/* 底部操作栏 */}
                <div className="flex justify-between items-center pt-6 mt-4 border-t border-white/10">
                    <button
                        onClick={startCreate}
                        disabled={isCreating || editingId !== null}
                        className="flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 transition-colors font-medium text-sm disabled:opacity-50"
                    >
                        <Plus size={16} />
                        添加模型配置
                    </button>
                    <button
                        onClick={handleCloseRequest}
                        className="px-6 py-2 rounded-xl bg-white/5 hover:bg-white/10 transition-colors font-medium text-sm border border-white/10"
                    >
                        关闭
                    </button>
                </div>

                {/* 退出的确认弹窗 */}
                {showExitConfirm && (
                    <div className="absolute inset-0 bg-black/80 backdrop-blur-md flex items-center justify-center p-8 z-50 rounded-3xl" onClick={(e) => e.stopPropagation()}>
                        <motion.div
                            initial={{ scale: 0.9, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            className="bg-slate-900 border border-white/10 p-6 rounded-2xl max-w-sm w-full shadow-2xl"
                        >
                            <div className="flex flex-col items-center text-center mb-6">
                                <div className="w-12 h-12 bg-yellow-500/20 rounded-full flex items-center justify-center text-yellow-500 mb-4">
                                    <AlertTriangle size={24} />
                                </div>
                                <h3 className="text-xl font-bold mb-2">确认退出？</h3>
                                <p className="text-slate-400 text-sm">
                                    您当前有未保存的编辑内容。如果直接退出，所有更改将丢失。
                                </p>
                            </div>
                            <div className="space-y-3">
                                <button
                                    onClick={handleSaveAndExit}
                                    className="w-full py-3 rounded-xl bg-blue-600 hover:bg-blue-500 font-medium transition-colors flex items-center justify-center gap-2"
                                >
                                    <Save size={16} />
                                    退出并保存
                                </button>
                                <button
                                    onClick={handleForceExit}
                                    className="w-full py-3 rounded-xl bg-red-500/10 hover:bg-red-500/20 text-red-500 font-medium transition-colors border border-red-500/20"
                                >
                                    退出（放弃更改）
                                </button>
                                <button
                                    onClick={() => setShowExitConfirm(false)}
                                    className="w-full py-3 rounded-xl bg-white/5 hover:bg-white/10 text-slate-400 font-medium transition-colors"
                                >
                                    取消
                                </button>
                            </div>
                        </motion.div>
                    </div>
                )}
            </motion.div>
        </div>
    );
}
