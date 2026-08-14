import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/health': 'http://127.0.0.1:8123',
      '/extract': 'http://127.0.0.1:8123',
      '/patch-profile': 'http://127.0.0.1:8123',
      '/match': 'http://127.0.0.1:8123',
      '/screen': 'http://127.0.0.1:8123',
      '/compose': 'http://127.0.0.1:8123',
      '/trial-access-links': 'http://127.0.0.1:8123',
    },
  },
})
