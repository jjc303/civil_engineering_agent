import { fileURLToPath, URL } from 'node:url'
import zlib from 'node:zlib'
import type { IncomingMessage, ServerResponse } from 'node:http'
import { defineConfig, loadEnv, type Plugin } from 'vite'
import vue from '@vitejs/plugin-vue'

const COMPRESSIBLE_RE = /\.(?:js|mjs|ts|vue|css|html|svg|json)(?:\?.*)?$/i

function attachGzipMiddleware(middlewares: { use: (fn: (req: IncomingMessage, res: ServerResponse, next: () => void) => void) => void }) {
  middlewares.use((req, res, next) => {
    const url = req.url || ''
    if (url.includes('/api/') || url.includes('/media/')) {
      next()
      return
    }
    const acceptEncoding = String(req.headers['accept-encoding'] || '')
    const canGzip = acceptEncoding.includes('gzip')
    const isViteDep = url.includes('/node_modules/.vite/deps/')

    if (!canGzip && !isViteDep) {
      next()
      return
    }

    const origWrite = res.write.bind(res)
    const origEnd = res.end.bind(res)
    const chunks: Buffer[] = []

    res.write = ((chunk: unknown, encoding?: BufferEncoding | ((error: Error | null | undefined) => void), cb?: (error: Error | null | undefined) => void) => {
      if (chunk) {
        chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(String(chunk), typeof encoding === 'string' ? encoding : 'utf8'))
      }
      if (typeof encoding === 'function') encoding(null)
      else if (typeof cb === 'function') cb(null)
      return true
    }) as typeof res.write

    res.end = ((chunk?: unknown, encoding?: BufferEncoding | (() => void), cb?: () => void) => {
      if (chunk && typeof chunk !== 'function') {
        chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(String(chunk), typeof encoding === 'string' ? encoding : 'utf8'))
      }
      let body = Buffer.concat(chunks)
      const contentType = String(res.getHeader('content-type') || '')
      const isCompressible =
        COMPRESSIBLE_RE.test(url) ||
        /javascript|text\/css|text\/html|application\/json|image\/svg/i.test(contentType)

      // Strip multi-megabyte inline base64 source maps from pre-bundled Vite deps
      if (isViteDep && body.length > 32768) {
        const marker = Buffer.from('//# sourceMappingURL=data:')
        const idx = body.lastIndexOf(marker)
        if (idx !== -1) {
          body = body.subarray(0, idx)
        }
      }

      if (canGzip && isCompressible && !res.getHeader('content-encoding') && body.length >= 1024) {
        body = zlib.gzipSync(body, { level: 6 })
        res.setHeader('Content-Encoding', 'gzip')
        res.setHeader('Vary', 'Accept-Encoding')
      }

      if (!res.headersSent) {
        res.setHeader('Content-Length', body.length)
      }
      res.write = origWrite
      res.end = origEnd
      if (typeof chunk === 'function') return origEnd(body, chunk as () => void)
      if (typeof encoding === 'function') return origEnd(body, encoding)
      return origEnd(body, cb)
    }) as typeof res.end

    next()
  })
}

function gzipTransferPlugin(): Plugin {
  return {
    name: 'vite-gzip-transfer',
    configureServer(server) {
      attachGzipMiddleware(server.middlewares)
    },
    configurePreviewServer(server) {
      attachGzipMiddleware(server.middlewares)
    },
  }
}

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const rootDir = fileURLToPath(new URL('..', import.meta.url))
  const env = { ...loadEnv(mode, rootDir, ''), ...loadEnv(mode, process.cwd(), '') }
  const rawBase = env.VITE_APP_BASE_PATH || env.APP_BASE_PATH || '/'
  const base = rawBase.endsWith('/') ? rawBase : `${rawBase}/`
  const basePrefix = base.replace(/\/$/, '')
  const apiTarget = process.env.VITE_DEV_API_TARGET || env.VITE_DEV_API_TARGET || 'http://127.0.0.1:8000'
  const proxyRules = {
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
  }

  return {
    base,
    plugins: [gzipTransferPlugin(), vue()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    build: {
      sourcemap: false,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (id.includes('node_modules/echarts') || id.includes('node_modules/zrender') || id.includes('node_modules/vue-echarts')) {
              return 'vendor-echarts'
            }
            if (id.includes('node_modules/element-plus') || id.includes('node_modules/@element-plus')) {
              return 'vendor-element'
            }
            if (id.includes('node_modules/vue') || id.includes('node_modules/pinia') || id.includes('node_modules/@vue')) {
              return 'vendor-vue'
            }
          },
        },
      },
    },
    server: {
      port: 5173,
      host: '0.0.0.0',
      allowedHosts: true,
      proxy: proxyRules,
    },
    preview: {
      port: 5173,
      host: '0.0.0.0',
      allowedHosts: true,
      proxy: proxyRules,
    },
  }
})
