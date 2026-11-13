import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'SMSES — نظام المبيعات والهندسة الطبية',
        short_name: 'SMSES',
        lang: 'ar',
        dir: 'rtl',
        theme_color: '#0b2447',
        background_color: '#ffffff',
        display: 'standalone',
        start_url: '/',
        icons: [{ src: 'favicon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any' }],
      },
      workbox: {
        // App shell is cached; API responses are never cached, so financial/stock data is never stale (ADR-016).
        navigateFallbackDenylist: [/^\/api\//],
        runtimeCaching: [],
      },
    }),
  ],
  server: { port: 5173, proxy: { '/api': 'http://localhost:8000' } },
  test: { environment: 'jsdom', globals: true, setupFiles: './src/test-setup.ts' },
})
