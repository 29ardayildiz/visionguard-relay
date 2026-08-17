import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    vueDevTools(),
    tailwindcss(),
    VitePWA({
      // 'prompt': yeni SW indirilse bile otomatik aktive edilmez/reload olmaz;
      // kullanıcı PwaUpdatePrompt kartından "Güncelle"ye basana kadar bekler.
      registerType: 'prompt',
      includeAssets: ['favicon.svg', 'favicon-32x32.png', 'apple-touch-icon.png'],
      manifest: {
        name: 'VisionGuard',
        short_name: 'VisionGuard',
        description: 'Garaj güvenlik kamerası — canlı izleme ve kamera kontrolü',
        lang: 'tr',
        start_url: '/',
        display: 'standalone',
        background_color: '#090a0a',
        theme_color: '#090a0a',
        icons: [
          { src: 'pwa-192x192.png', sizes: '192x192', type: 'image/png' },
          { src: 'pwa-512x512.png', sizes: '512x512', type: 'image/png' },
          { src: 'maskable-icon-512x512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      // Faz 8'de Lighthouse ile gözden geçirilecek; şimdilik tüm build
      // çıktısı (app-shell) precache ediliyor — MASTER.md §12: "anında açılış".
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,png,ico,woff2}'],
      },
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  // Sadece `npm run dev` içindir — backend (uvicorn) ve Vite dev server farklı
  // origin/port'ta çalıştığı için /login, /api, /ws vb. istekler backend'e
  // proxy'lenir. Production'da FastAPI tek origin'den serve ettiği için
  // (Faz 7 — Cutover) bu proxy hiç devreye girmez.
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      // /login çakışıyor: GET (sayfa yüklemesi) Vue Router'ın kendi rotası,
      // POST (form submit) ise backend'in auth action'ı. Sadece POST'u
      // proxy'liyoruz; GET bypass ile Vite'a (SPA fallback -> index.html)
      // bırakılıyor, aksi halde Vue hiç mount olmadan eski Jinja2 login.html
      // sessizce gösterilir.
      '/login': {
        target: 'http://127.0.0.1:8000',
        bypass(req) {
          if (req.method === 'GET') return req.url
        },
      },
      '/logout': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
      '/stream': 'http://127.0.0.1:8000',
      '/push': 'http://127.0.0.1:8000',
      '/ws': { target: 'ws://127.0.0.1:8000', ws: true },
      '/manifest.json': 'http://127.0.0.1:8000',
      '/icon.png': 'http://127.0.0.1:8000',
    },
  },
})
