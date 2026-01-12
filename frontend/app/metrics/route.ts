import { NextResponse } from 'next/server';

/**
 * 健康检查接口
 * @returns {Promise<NextResponse>} 返回包含状态和时间戳的 JSON 响应
 */
export async function GET(): Promise<NextResponse> {
    return NextResponse.json({
        status: 'ok',
        timestamp: new Date().toISOString(),
        service: 'prompt-optimizer-frontend'
    });
}
