import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/session': 'http://localhost:8766',
      '/event': 'http://localhost:8766',
      '/health': 'http://localhost:8766',
    },
  },
})
