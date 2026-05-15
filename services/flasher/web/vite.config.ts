import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/flash/',
  build: {
    outDir: '../app/static',
    emptyOutDir: true,
  },
})
