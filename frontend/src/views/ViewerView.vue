<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import AppIcon from '../components/AppIcon.vue'
import cameraOfflineUrl from '../icons/status/camera-offline.svg'
import actionLogoutSvg from '../icons/actions/action-logout.svg?raw'
import actionSettingsSvg from '../icons/actions/action-settings.svg?raw'
import loaderWakingUrl from '../icons/status/loader-waking.svg'
import { useAuthGuard } from '../lib/auth'
import { useConnectionStore } from '../stores/connection'

const PULL_THRESHOLD = 70

const router = useRouter()
const guard = useAuthGuard()
const connection = useConnectionStore()

const streamImg = ref<HTMLImageElement | null>(null)
const streamCacheBust = ref(Date.now())
const streamUrl = computed(() => `/stream?t=${streamCacheBust.value}`)
const isFullscreen = ref(false)

const pulling = ref(false)
const pullDistance = ref(0)
let touchStartY = 0

const statusMeta = computed(() => {
  switch (connection.status) {
    case 'live':
      return { label: 'Canlı', dotClass: 'bg-status-live' }
    case 'offline':
      return { label: 'Kamera çevrimdışı', dotClass: 'bg-status-offline' }
    default:
      return { label: 'Sunucu uyanıyor', dotClass: 'bg-status-waking' }
  }
})

onMounted(async () => {
  if (await guard()) {
    connection.start()
  }
})

function vibrate(): void {
  if ('vibrate' in navigator) navigator.vibrate(10)
}

function goAdmin(): void {
  // Viewer <-> Admin bu uygulamanın tek "sekme çifti" — push kullanmak her
  // geçişte geçmişe yeni kayıt ekleyip swipe-back'in web sitesi gibi tek tek
  // "geri sarılmasına" yol açıyordu. replace ile tek kayıt, sekmesi değişiyor.
  router.replace({ name: 'admin' })
}

function logout(): void {
  window.location.href = '/logout'
}

function toggleFullscreen(): void {
  isFullscreen.value = !isFullscreen.value
}

function reconnect(): void {
  vibrate()
  connection.reconnectNow()
  streamCacheBust.value = Date.now()
}

function onTouchStart(event: TouchEvent): void {
  if (window.scrollY > 0) return
  touchStartY = event.touches[0]!.clientY
  pulling.value = true
}

function onTouchMove(event: TouchEvent): void {
  if (!pulling.value) return
  const delta = event.touches[0]!.clientY - touchStartY
  if (delta > 0) pullDistance.value = Math.min(delta, 120)
}

function onTouchEnd(): void {
  if (pulling.value && pullDistance.value > PULL_THRESHOLD) {
    reconnect()
  }
  pulling.value = false
  pullDistance.value = 0
}

function downloadSnapshot(): void {
  const img = streamImg.value
  if (!img) return
  const canvas = document.createElement('canvas')
  canvas.width = img.naturalWidth
  canvas.height = img.naturalHeight
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.drawImage(img, 0, 0)
  canvas.toBlob(
    (blob) => {
      if (!blob) return
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `visionguard-${Date.now()}.jpg`
      // Anchor'ın DOM'a eklenmesi gerekiyor — bazı tarayıcılar/otomasyon
      // ortamları detached bir elemanda click()'i indirme olarak saymıyor.
      document.body.appendChild(a)
      a.click()
      a.remove()
      // revoke'u hemen çağırmak, indirme henüz blob'u okumaya başlamadan
      // URL'yi geçersiz kılabilir; bir sonraki tick'e erteliyoruz.
      setTimeout(() => URL.revokeObjectURL(url), 0)
    },
    'image/jpeg',
    0.92,
  )
  vibrate()
}
</script>

<template>
  <main class="relative h-full bg-guard-bg">
    <!-- Üst durum katmanı -->
    <header
      class="fixed inset-x-0 top-0 z-20 flex items-center justify-between p-4"
      :style="{ paddingTop: 'calc(var(--sat) + 1rem)' }"
    >
      <div
        class="flex items-center gap-2 rounded-full border border-guard-border bg-guard-surface/80 px-3 py-1.5 text-xs text-guard-secondary backdrop-blur-md"
      >
        <span
          class="h-2 w-2 rounded-full"
          :class="[statusMeta.dotClass, connection.status === 'live' && 'animate-pulse']"
        />
        <span>{{ statusMeta.label }}</span>
        <span v-if="connection.status === 'live'" class="font-mono text-guard-primary tabular-nums">
          {{ connection.fps.toFixed(1) }} FPS
        </span>
      </div>

      <button
        type="button"
        class="flex h-9 w-9 items-center justify-center rounded-full border border-guard-border bg-guard-surface/80 text-guard-secondary backdrop-blur-md transition-colors hover:text-brand active:scale-95"
        @click="goAdmin"
      >
        <AppIcon :svg="actionSettingsSvg" class="h-4 w-4" />
      </button>
    </header>

    <!-- Pull-to-reconnect göstergesi -->
    <div
      v-if="pullDistance > 0"
      class="fixed inset-x-0 top-0 z-10 flex justify-center text-xs text-guard-secondary"
      :style="{ paddingTop: `calc(var(--sat) + ${pullDistance}px)`, opacity: Math.min(pullDistance / PULL_THRESHOLD, 1) }"
    >
      {{ pullDistance > PULL_THRESHOLD ? 'Bırakınca yenilenir' : 'Yenilemek için çekin' }}
    </div>

    <!-- Stream alanı -->
    <div
      :class="[
        'flex h-full items-center justify-center overflow-hidden',
        isFullscreen ? 'fixed inset-0 z-30 bg-black' : 'p-4',
      ]"
      @touchstart="onTouchStart"
      @touchmove="onTouchMove"
      @touchend="onTouchEnd"
      @dblclick="toggleFullscreen"
    >
      <img
        v-if="connection.status === 'live'"
        ref="streamImg"
        :src="streamUrl"
        alt="Canlı yayın"
        class="max-h-full max-w-full object-contain"
        :class="isFullscreen ? 'rounded-none' : 'rounded-2xl'"
      />
      <div v-else class="flex flex-col items-center gap-3 px-4 text-center">
        <img
          :src="connection.status === 'waking' ? loaderWakingUrl : cameraOfflineUrl"
          alt=""
          class="h-16 w-16"
          :class="connection.status === 'waking' && 'animate-spin-slow'"
        />
        <p class="text-sm text-guard-secondary">
          {{
            connection.status === 'waking' ? 'Sunucu uyanıyor, lütfen bekleyin...' : 'Kamera çevrimdışı'
          }}
        </p>
      </div>
    </div>

    <!-- Alt aksiyon çubuğu -->
    <footer
      v-if="!isFullscreen"
      class="fixed inset-x-0 bottom-0 z-20 flex justify-center p-4"
      :style="{ paddingBottom: 'calc(var(--sab) + 1rem)' }"
    >
      <div
        class="flex items-center gap-1 rounded-full border border-guard-border bg-guard-surface/80 p-1.5 backdrop-blur-md"
      >
        <button
          type="button"
          class="flex items-center gap-1.5 rounded-full px-4 py-2 text-xs font-medium text-guard-secondary transition-colors hover:bg-guard-elevated hover:text-guard-primary active:scale-95"
          @click="logout"
        >
          <AppIcon :svg="actionLogoutSvg" class="h-4 w-4" />
          Çıkış
        </button>
        <button
          type="button"
          class="flex items-center gap-1.5 rounded-full px-4 py-2 text-xs font-medium text-guard-secondary transition-colors hover:bg-guard-elevated hover:text-guard-primary active:scale-95"
          @click="toggleFullscreen"
        >
          Tam Ekran
        </button>
        <button
          type="button"
          :disabled="connection.status !== 'live'"
          class="flex items-center gap-1.5 rounded-full px-4 py-2 text-xs font-medium text-guard-secondary transition-colors hover:bg-guard-elevated hover:text-guard-primary active:scale-95 disabled:pointer-events-none disabled:opacity-40"
          @click="downloadSnapshot"
        >
          Snapshot
        </button>
      </div>
    </footer>
  </main>
</template>
