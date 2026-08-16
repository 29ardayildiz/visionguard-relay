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
