import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  base: '/static/',
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:5000'
    }
  },
  build: {
    outDir: '../static',
    emptyOutDir: true
  }
})
