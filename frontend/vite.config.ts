import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    assetsDir: 'static',
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:2080',
        changeOrigin: true,
      },
    },
  },
})
