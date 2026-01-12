/** @type {import('next').NextConfig} */
const nextConfig = {
    // 注意: API 请求现在通过 app/api/[...path]/route.ts 代理
    // 这样可以设置更长的超时时间 (maxDuration: 300)
    // 解决了 rewrites 默认 30 秒超时的问题
};

export default nextConfig;
