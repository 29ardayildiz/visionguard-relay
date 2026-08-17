// PWA ikon setini src/icons/pwa/*.svg kaynaklarından üretir (public/ altına).
// `npm run generate-icons` ile manuel çalıştırılır — kaynak SVG'ler
// değişmediği sürece tekrar çalıştırmaya gerek yoktur, üretilen PNG'ler
// git'e commit edilir (build sırasında yeniden üretilmiyor).

import { mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import sharp from 'sharp'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ICONS_SRC = join(__dirname, '..', 'src', 'icons', 'pwa')
const PUBLIC_DIR = join(__dirname, '..', 'public')

mkdirSync(PUBLIC_DIR, { recursive: true })

const tasks = [
  { src: 'app-icon.svg', out: 'pwa-192x192.png', size: 192 },
  { src: 'app-icon.svg', out: 'pwa-512x512.png', size: 512 },
  { src: 'app-icon.svg', out: 'apple-touch-icon.png', size: 180 },
  { src: 'maskable-icon.svg', out: 'maskable-icon-512x512.png', size: 512 },
  { src: 'favicon.svg', out: 'favicon-32x32.png', size: 32 },
]

for (const task of tasks) {
  const srcPath = join(ICONS_SRC, task.src)
  const outPath = join(PUBLIC_DIR, task.out)
  await sharp(srcPath, { density: 384 }).resize(task.size, task.size).png().toFile(outPath)
  console.log(`generated ${task.out} (${task.size}x${task.size}) from ${task.src}`)
}

// ── iOS splash screen'leri (apple-touch-startup-image) ──────────────────────
// iOS, PWA açılışında bu görselleri piksel-hassas media query'lerle eşler
// (index.html'deki link etiketleri). Koyu OLED zemin + ortalanmış marka ikonu.
// Kapsanan cihazlar (portrait): iPhone SE/8, 14/13/12, 15/14 Pro, Pro Max.
const SPLASH_BG = '#090a0a'
const splashes = [
  { w: 750, h: 1334 },  // 375x667 @2x — iPhone SE3 / 8
  { w: 1170, h: 2532 }, // 390x844 @3x — iPhone 14 / 13 / 12
  { w: 1179, h: 2556 }, // 393x852 @3x — iPhone 15 / 14 Pro
  { w: 1290, h: 2796 }, // 430x932 @3x — iPhone 15 Plus / Pro Max
]

for (const { w, h } of splashes) {
  const iconSize = Math.round(w * 0.3)
  const icon = await sharp(join(ICONS_SRC, 'app-icon.svg'), { density: 384 })
    .resize(iconSize, iconSize)
    .png()
    .toBuffer()
  const out = `apple-splash-${w}x${h}.png`
  await sharp({
    create: { width: w, height: h, channels: 4, background: SPLASH_BG },
  })
    .composite([{ input: icon, gravity: 'center' }])
    .png()
    .toFile(join(PUBLIC_DIR, out))
  console.log(`generated ${out}`)
}
