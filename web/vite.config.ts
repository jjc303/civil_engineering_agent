import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const rootDir = fileURLToPath(new URL('..', import.meta.url))
  const env = { ...loadEnv(mode, rootDir, ''), ...loadEnv(mode, process.cwd(), '') }
  const rawBase = env.VITE_APP_BASE_PATH || env.APP_BASE_PATH || '/'
  const base = rawBase.endsWith('/') ? rawBase : `${rawBase}/`
  const basePrefix = base.replace(/\/$/, '')
  const apiTarget = process.env.VITE_DEV_API_TARGET || env.VITE_DEV_API_TARGET || ''
  return {
  base,
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    host: '0.0.0.0',
    allowedHosts: true,
    proxy: {
      ...(basePrefix
        ? {
            [`${basePrefix}/api`]: {
              target: apiTarget,
              changeOrigin: true,
              rewrite: (path: string) => path.slice(basePrefix.length),
            },
            [`${basePrefix}/media`]: {
              target: apiTarget,
              changeOrigin: true,
              rewrite: (path: string) => path.slice(basePrefix.length),
            },
          }
        : {}),
      '/api': {
        target: apiTarget,
        changeOrigin: true,
      },
      '/media': {
        target: apiTarget,
        changeOrigin: true,
      },
    },
  },
  }
})
