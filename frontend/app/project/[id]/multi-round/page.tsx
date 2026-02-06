"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";

/**
 * 多轮验证旧路由重定向页面
 *
 * 多轮验证功能已集成到项目详情页中，
 * 此页面仅用于向后兼容，自动重定向到主项目页面。
 */
export default function MultiRoundRedirect() {
    const { id } = useParams();
    const router = useRouter();

    useEffect(() => {
        // 重定向到主项目页面
        router.replace(`/project/${id}`);
    }, [id, router]);

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white flex items-center justify-center">
            <div className="text-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-500 mx-auto mb-4"></div>
                <p className="text-slate-400">正在跳转到项目页面...</p>
            </div>
        </div>
    );
}
