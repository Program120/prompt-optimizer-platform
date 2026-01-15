"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { AlertTriangle, RotateCcw, Activity } from "lucide-react";

/**
 * 重置项目确认弹窗属性
 */
interface ResetProjectModalProps {
    /** 项目名称 */
    projectName: string;
    /** 关闭弹窗回调 */
    onClose: () => void;
    /** 确认重置回调 */
    onConfirm: () => Promise<void>;
}

/**
 * 重置项目确认弹窗组件
 * 
 * 显示警告信息，让用户确认是否重置项目
 * 重置操作将：
 * - 恢复提示词到最初版本
 * - 清空所有运行记录
 * - 清空迭代记录
 * - 清空优化分析记录
 */
export default function ResetProjectModal({
    projectName,
    onClose,
    onConfirm
}: ResetProjectModalProps) {
    // 加载状态
    const [isLoading, setIsLoading] = useState<boolean>(false);

    /**
     * 处理确认操作
     */
    const handleConfirm = async () => {
        setIsLoading(true);
        try {
            await onConfirm();
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
            <motion.div
                initial={{ scale: 0.9, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                className="glass w-full max-w-md p-8 rounded-3xl"
            >
                {/* 标题 */}
                <div className="flex items-center gap-3 mb-4">
                    <div className="p-3 bg-orange-500/20 rounded-xl">
                        <AlertTriangle className="text-orange-400" size={24} />
                    </div>
                    <h2 className="text-2xl font-bold text-orange-400">重置项目</h2>
                </div>

                {/* 项目名称 */}
                <p className="text-slate-300 mb-4">
                    确定要重置项目 <span className="font-semibold text-white">"{projectName}"</span> 吗？
                </p>

                {/* 警告描述 */}
                <div className="bg-orange-500/10 border border-orange-500/30 rounded-xl p-4 mb-6">
                    <p className="text-orange-300 text-sm mb-2 font-medium">此操作将：</p>
                    <ul className="text-orange-200/80 text-sm space-y-1.5 list-disc list-inside">
                        <li>将提示词恢复到<span className="text-white font-medium">最初版本</span></li>
                        <li>清空所有<span className="text-white font-medium">运行记录</span></li>
                        <li>清空所有<span className="text-white font-medium">迭代记录</span></li>
                        <li>清空所有<span className="text-white font-medium">优化分析</span></li>
                    </ul>
                    <p className="text-orange-400/80 text-xs mt-3 flex items-center gap-1">
                        <AlertTriangle size={12} />
                        此操作不可恢复
                    </p>
                </div>

                {/* 按钮区域 */}
                <div className="flex gap-4">
                    <button
                        onClick={onClose}
                        disabled={isLoading}
                        className="flex-1 px-6 py-3 rounded-xl bg-white/5 hover:bg-white/10 transition-colors font-medium border border-white/10 disabled:opacity-50"
                    >
                        取消
                    </button>
                    <button
                        onClick={handleConfirm}
                        disabled={isLoading}
                        className="flex-1 flex items-center justify-center gap-2 bg-orange-600 hover:bg-orange-500 px-6 py-3 rounded-xl font-medium transition-colors shadow-lg shadow-orange-900/20 disabled:opacity-50"
                    >
                        {isLoading ? (
                            <>
                                <Activity className="animate-spin" size={18} />
                                重置中...
                            </>
                        ) : (
                            <>
                                <RotateCcw size={18} />
                                确认重置
                            </>
                        )}
                    </button>
                </div>
            </motion.div>
        </div>
    );
}
