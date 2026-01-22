// @ts-nocheck
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
    // Load .env* from the frontend directory for local dev, and also allow Docker/CI env vars.
    const fileEnv = loadEnv(mode, process.cwd(), '')
    const env = { ...process.env, ...fileEnv } as Record<string, string | undefined>

    const frontendInternalPort = parseInt(env.FRONTEND_INTERNAL_PORT || '5173', 10)
    const backendTarget =
        env.BACKEND_URL || `http://localhost:${env.BACKEND_PORT || '8000'}`

    return {
        plugins: [react()],
        server: {
            host: true,
            port: frontendInternalPort,
            watch: {
                usePolling: true
            },
            proxy: {
                '/api': {
                    target: backendTarget,
                    changeOrigin: true,
                    secure: false,
                    ws: true,
                    configure: (proxy, _options) => {
                        proxy.on('error', (err, _req, _res) => {
                            console.log('Proxy error:', err);
                        });
                        proxy.on('proxyReq', (proxyReq, req, _res) => {
                            console.log('Proxying:', req.method, req.url, '->', proxyReq.path);
                        });
                        proxy.on('proxyRes', (proxyRes, req, _res) => {
                            console.log('Proxy response:', req.url, '->', proxyRes.statusCode);
                        });
                    }
                }
            }
        }
    }
})
