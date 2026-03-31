import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: true,
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws/feed': {
        target: 'http://localhost:8000',
        ws: true,
        changeOrigin: true,
      },
      '/auth': 'http://localhost:8000',
    }
  },
  build: { outDir: 'dist', sourcemap: false }
})
