import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      'react-is': path.resolve(__dirname, 'src/lib/react-is-shim.ts'),
    },
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
  },
})
