/**
 * API 代理路由
 * 
 * 解决 Next.js rewrites 的默认超时限制问题
 * 通过 API Route 代理请求到后端，可以自定义更长的超时时间
 */

import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = 'http://127.0.0.1:8000';

// 设置运行时为 nodejs（支持更长超时）
export const runtime = 'nodejs';

// 设置最大执行时间为 5 分钟 (300 秒)
export const maxDuration = 300;

async function proxyRequest(request: NextRequest, path: string[]) {
    const targetPath = path.join('/');
    const url = new URL(request.url);
    const searchParams = url.searchParams.toString();
    const targetUrl = `${BACKEND_URL}/${targetPath}${searchParams ? `?${searchParams}` : ''}`;

    try {
        // 构建请求 headers - 保留原始 headers
        const headers: Record<string, string> = {};
        request.headers.forEach((value, key) => {
            // 排除 host 和 connection，但保留 content-type（包括 boundary）
            if (!['host', 'connection'].includes(key.toLowerCase())) {
                headers[key] = value;
            }
        });

        // 获取请求体 - 直接传递原始数据，不解析
        let body: BodyInit | null = null;
        if (request.method !== 'GET' && request.method !== 'HEAD') {
            // 直接传递原始请求体，保持 boundary 不变
            body = await request.arrayBuffer();
        }

        // 代理请求到后端，设置长超时
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 300000); // 5 分钟超时

        const response = await fetch(targetUrl, {
            method: request.method,
            headers,
            body,
            signal: controller.signal,
        });

        clearTimeout(timeoutId);

        // 构建响应 headers
        const responseHeaders = new Headers();
        response.headers.forEach((value, key) => {
            if (!['content-encoding', 'transfer-encoding'].includes(key.toLowerCase())) {
                responseHeaders.set(key, value);
            }
        });

        // 返回响应
        const responseBody = await response.arrayBuffer();
        return new NextResponse(responseBody, {
            status: response.status,
            statusText: response.statusText,
            headers: responseHeaders,
        });
    } catch (error: any) {
        console.error('Proxy request failed:', error);

        if (error.name === 'AbortError') {
            return NextResponse.json(
                { error: '请求超时', detail: '后端处理时间过长，请稍后重试' },
                { status: 504 }
            );
        }

        return NextResponse.json(
            { error: '代理请求失败', detail: error.message },
            { status: 502 }
        );
    }
}

export async function GET(
    request: NextRequest,
    { params }: { params: Promise<{ path: string[] }> }
) {
    const { path } = await params;
    return proxyRequest(request, path);
}

export async function POST(
    request: NextRequest,
    { params }: { params: Promise<{ path: string[] }> }
) {
    const { path } = await params;
    return proxyRequest(request, path);
}

export async function PUT(
    request: NextRequest,
    { params }: { params: Promise<{ path: string[] }> }
) {
    const { path } = await params;
    return proxyRequest(request, path);
}

export async function DELETE(
    request: NextRequest,
    { params }: { params: Promise<{ path: string[] }> }
) {
    const { path } = await params;
    return proxyRequest(request, path);
}

export async function PATCH(
    request: NextRequest,
    { params }: { params: Promise<{ path: string[] }> }
) {
    const { path } = await params;
    return proxyRequest(request, path);
}
