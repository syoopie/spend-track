import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// VITE_DEV_PORT / VITE_API_PROXY_TARGET let a second instance run
// side-by-side with the normal dev servers (see scripts/start-test.*) -
// e.g. for an agent driving the UI against a scratch database without
// touching whatever's already running on 5173/8000. Both default to the
// original hardcoded values, so a plain `npm run dev` is unaffected.
const devPort = Number(process.env.VITE_DEV_PORT) || 5173
const apiProxyTarget = process.env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: devPort,
    proxy: {
      '/api': {
        target: apiProxyTarget,
        changeOrigin: true,
      },
    },
  },
})
