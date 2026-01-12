/** @type {import('next').NextConfig} */
const nextConfig = {
    async rewrites() {
        return [
            {
                // 将所有 /api 路径的请求转发到后端
                source: '/api/:path*',
                destination: 'http://127.0.0.1:8000/:path*',
            },
        ];
    },
};

export default nextConfig;
