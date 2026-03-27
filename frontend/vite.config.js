import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  base: './',
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8002'
    }
  },
  build: {
    outDir: '../static',
    emptyOutDir: true
  }
})
