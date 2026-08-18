import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          const normalizedId = id.replace(/\\/g, '/')
          if (!normalizedId.includes('/node_modules/')) {
            return undefined
          }

          if (normalizedId.includes('/react/') || normalizedId.includes('/react-dom/') || normalizedId.includes('/react-router')) {
            return 'vendor-react'
          }

          if (normalizedId.includes('/ai/') || normalizedId.includes('/@ai-sdk/')) {
            return 'vendor-ai'
          }

          if (normalizedId.includes('/@supabase/')) {
            return 'vendor-supabase'
          }

          return 'vendor-core'
        },
      },
    },
  },
})
