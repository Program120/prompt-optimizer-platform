/**
 * 统一测试结果弹窗组件
 * 用于 RunLogTab 和 IntentInterventionTab 共用
 */
import { useRef, useEffect, useState } from "react";
import { CheckCircle2, AlertCircle, X, FlaskConical, Clock, Copy, Check } from "lucide-react";

/**
 * 测试结果数据接口
 */
export interface TestResultData {
    query: string;
    is_correct: boolean;
    output: string;
    reason?: string;
    target: string;
    latency_ms?: number;
    request_id?: string;
}

/**
 * 测试结果弹窗组件属性
 */
interface TestResultModalProps {
    testResult: TestResultData;
    onClose: () => void;
}

/**
 * 测试结果弹窗组件
 * 
 * @param testResult - 测试结果数据
 * @param onClose - 关闭弹窗回调
 */
export default function TestResultModal({ testResult, onClose }: TestResultModalProps) {
    const modalRef = useRef<HTMLDivElement>(null);
    const [copied, setCopied] = useState(false);

    // 点击外部关闭
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (modalRef.current && !modalRef.current.contains(event.target as Node)) {
                onClose();
            }
        };

        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [onClose]);

    // 复制 RequestId
    const handleCopyRequestId = () => {
        if (testResult.request_id) {
            navigator.clipboard.writeText(testResult.request_id);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        }
    };

    return (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div
                ref={modalRef}
                className="bg-slate-900 border border-slate-700 rounded-xl w-full max-w-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in duration-200 flex flex-col max-h-[85vh]"
            >
                {/* 头部 */}
                <div className="px-4 py-3 border-b border-slate-800 flex justify-between items-center bg-slate-900/50 shrink-0">
                    <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                        <FlaskConical size={14} className="text-indigo-400" /> 测试结果
                    </h3>
                    <button
                        onClick={onClose}
                        className="text-slate-500 hover:text-white transition-colors"
                    >
                        <X size={16} />
                    </button>
                </div>

                <div className="p-0 overflow-y-auto custom-scrollbar flex-1">
                    {/* 状态横幅 */}
                    <div className={`p-4 flex items-center gap-3 border-b border-slate-800 ${testResult.is_correct ? 'bg-emerald-500/10' : 'bg-rose-500/10'}`}>
                        <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${testResult.is_correct ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}`}>
                            {testResult.is_correct ? <CheckCircle2 size={20} /> : <AlertCircle size={20} />}
                        </div>
                        <div className="flex-1">
                            <h4 className={`text-base font-bold ${testResult.is_correct ? 'text-emerald-400' : 'text-rose-400'}`}>
                                {testResult.is_correct ? '验证通过' : '验证不通过'}
                            </h4>
                            <p className="text-xs text-slate-400 mt-0.5">
                                Query: <span className="font-mono text-slate-300">{testResult.query}</span>
                            </p>
                        </div>
                        {/* 耗时和 RequestId */}
                        <div className="flex flex-col items-end gap-1 shrink-0">
                            {testResult.latency_ms !== undefined && (
                                <span className="text-xs text-emerald-400 flex items-center gap-1">
                                    <Clock size={12} />
                                    {testResult.latency_ms}ms
                                </span>
                            )}
                        </div>
                    </div>

                    {/* RequestId 显示行 */}
                    {testResult.request_id && (
                        <div
                            className="px-4 py-2 border-b border-slate-800 bg-slate-800/30 flex items-center gap-2 cursor-pointer hover:bg-slate-800/50 transition-colors"
                            onClick={handleCopyRequestId}
                            title="点击复制 Request ID"
                        >
                            {copied ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} className="text-blue-400" />}
                            <span className="text-xs text-blue-400 font-mono">
                                RequestId: {testResult.request_id}
                            </span>
                        </div>
                    )}

                    <div className="p-4 space-y-4">
                        {/* 对比区域 */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {/* 预期结果 */}
                            <div className="space-y-1.5 overflow-hidden">
                                <label className="text-xs font-medium text-slate-500 flex items-center gap-1">
                                    <CheckCircle2 size={10} className="text-emerald-500" /> 预期结果 (Target)
                                </label>
                                <div className="bg-emerald-950/30 border border-emerald-500/20 rounded-lg p-3 text-xs text-emerald-100/90 font-mono min-h-[100px] whitespace-pre-wrap break-all overflow-hidden">
                                    {testResult.target || <span className="text-slate-600 italic">未设置</span>}
                                </div>
                            </div>

                            {/* 实际输出 */}
                            <div className="space-y-1.5 overflow-hidden">
                                <label className="text-xs font-medium text-slate-500 flex items-center gap-1">
                                    <AlertCircle size={10} className="text-indigo-500" /> 实际输出 (Actual)
                                </label>
                                <div className={`bg-slate-950/50 border rounded-lg p-3 text-xs font-mono min-h-[100px] whitespace-pre-wrap break-all overflow-hidden ${testResult.is_correct ? 'border-emerald-500/20 text-emerald-100/90' : 'border-rose-500/20 text-rose-100/90'}`}>
                                    {testResult.output}
                                </div>
                            </div>
                        </div>

                        {/* 原因/分析 */}
                        {testResult.reason && (
                            <div className="space-y-1.5">
                                <label className="text-xs font-medium text-slate-500">分析/原因 (Reason)</label>
                                <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-3 text-xs text-slate-300">
                                    {testResult.reason}
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {/* 底部操作栏 */}
                <div className="p-3 border-t border-slate-800 bg-slate-900/50 flex justify-end">
                    <button
                        onClick={onClose}
                        className="px-4 py-1.5 rounded-lg bg-slate-800 text-slate-300 text-xs hover:bg-slate-700 transition-colors"
                    >
                        关闭
                    </button>
                </div>
            </div>
        </div>
    );
}
