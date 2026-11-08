import { defineConfig, loadEnv, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'

const LOCAL_API_BASE = 'http://127.0.0.1:8000/api'
const DEV_API_BASE = '/api'

function apiBaseRewrite(apiBase: string): Plugin {
  return {
    name: 'emberwriter-api-base',
    enforce: 'pre',
    transform(code, id) {
      // Vite plugin ids use Windows backslashes on some installations.
      // A platform-specific check silently skips the same-origin API rewrite
      // in Pinokio's production build and leaks requests to port 8000.
      if (!id.replace(/\\/g, '/').includes('/src/') || !code.includes(LOCAL_API_BASE)) return null
      return {
        code: code.split(LOCAL_API_BASE).join(apiBase),
        map: null,
      }
    },
  }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const defaultApiBase = mode === 'development' ? DEV_API_BASE : LOCAL_API_BASE
  const apiBase = (env.VITE_API_BASE_URL || defaultApiBase).replace(/\/$/, '')

  return {
    plugins: [apiBaseRewrite(apiBase), react()],
    server: {
      host: '127.0.0.1',
      port: 5173,
      strictPort: true,
      proxy: {
        '/api': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: false,
        },
      },
    },
  }
})
