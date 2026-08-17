<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
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

const STREAM_RETRY_MS = 3000

const streamImg = ref<HTMLImageElement | null>(null)
const streamCacheBust = ref(Date.now())
const streamUrl = computed(() => `/stream?t=${streamCacheBust.value}`)
const isFullscreen = ref(false)
let streamRetryTimer: ReturnType<typeof setTimeout> | null = null

// Stream yalnızca canlı VE uygulama öndeyken mount edilir — arka planda
// <img> DOM'dan kalkınca tarayıcı MJPEG bağlantısını kapatır (pil + veri).
const streamActive = computed(() => connection.status === 'live' && connection.appVisible)

const pulling = ref(false)
const pullDistance = ref(0)
let touchStartY = 0

const statusMeta = computed(() => {
  if (!connection.networkOnline) {
    return { label: 'İnternet bağlantısı yok', dotClass: 'bg-status-offline' }
  }
  switch (connection.status) {
    case 'live':
      return { label: 'Canlı', dotClass: 'bg-status-live' }
    case 'offline':
      return { label: 'Kamera çevrimdışı', dotClass: 'bg-status-offline' }
    default:
      return { label: 'Sunucu uyanıyor', dotClass: 'bg-status-waking' }
  }
})

const emptyStateMeta = computed(() => {
  if (!connection.networkOnline) {
    return { icon: cameraOfflineUrl, spin: false, text: 'İnternet bağlantısı yok' }
  }
  if (connection.status === 'waking') {
    return { icon: loaderWakingUrl, spin: true, text: 'Sunucu uyanıyor, lütfen bekleyin...' }
  }
  return { icon: cameraOfflineUrl, spin: false, text: 'Kamera çevrimdışı' }
})

onMounted(async () => {
  if (await guard()) {
    connection.start()
  }
})

onUnmounted(() => {
  if (streamRetryTimer) clearTimeout(streamRetryTimer)
  void releaseWakeLock()
})

// Uygulama öne dönünce (veya stream başka bir sebeple yeniden aktive olunca)
// her zaman taze bir MJPEG bağlantısı başlat — bayat/donmuş kare kalmasın.
watch(streamActive, (active) => {
  if (active) streamCacheBust.value = Date.now()
})

// Canlı izleme sırasında ekranın sönmesini engelle (native kamera izleme
// uygulamalarının standart davranışı). Tarayıcı sentinel'i sekme arka plana
// geçince kendisi bırakır; streamActive watch'ı öne dönüşte yeniden alır.
// Desteklenmeyen tarayıcılarda sessiz no-op.
let wakeLock: WakeLockSentinel | null = null

async function syncWakeLock(active: boolean): Promise<void> {
  if (active && !wakeLock && 'wakeLock' in navigator) {
    try {
      wakeLock = await navigator.wakeLock.request('screen')
      wakeLock.addEventListener('release', () => {
        wakeLock = null
      })
    } catch {
      // Düşük pil modu vb. — tarayıcı reddedebilir, kritik değil.
    }
  } else if (!active && wakeLock) {
    await releaseWakeLock()
  }
}

async function releaseWakeLock(): Promise<void> {
  try {
    await wakeLock?.release()
  } catch {
    // zaten bırakılmış olabilir
  }
  wakeLock = null
}

watch(streamActive, (active) => void syncWakeLock(active), { immediate: true })

// Donma tespiti: MJPEG bağlantısı sessizce ölürse (Render idle kesintisi, ağ
// geçişi) <img> error üretir — rozet "Canlı" kalsa bile görüntü son karede
// donardı. Kısa bir bekleme sonrası cache-bust ile otomatik yeniden bağlanır;
// hata sürüyorsa her deneme yeni bir error üretip döngüyü (3sn aralıkla)
// sürdürür, hızlı-döngüye giremez.
function onStreamError(): void {
  if (streamRetryTimer) clearTimeout(streamRetryTimer)
  streamRetryTimer = setTimeout(() => {
    streamRetryTimer = null
    if (streamActive.value) streamCacheBust.value = Date.now()
  }, STREAM_RETRY_MS)
}

function vibrate(): void {
  if ('vibrate' in navigator) navigator.vibrate(10)
}

function goAdmin(): void {
  // Viewer <-> Admin bu uygulamanın tek "sekme çifti" — push kullanmak her
  // geçişte geçmişe yeni kayıt ekleyip swipe-back'in web sitesi gibi tek tek
  // "geri sarılmasına" yol açıyordu. replace ile tek kayıt, sekmesi değişiyor.
  router.replace({ name: 'admin' })
}

async function logout(): Promise<void> {
  // SPA içinde kal: tam sayfa navigasyonu (window.location) app-shell'i
  // yeniden başlatıp kısa bir boş-ekran flaşı yaratıyordu. Cookie'yi fetch ile
  // sildirip route geçişini animasyonlu şekilde router'a bırakıyoruz.
  connection.stop()
  try {
    await fetch('/logout', { redirect: 'manual' })
  } catch {
    // Ağ yoksa bile lokal olarak login'e dön — cookie zaten sunucuda geçersiz
    // sayılana kadar başka istek atılmayacak.
  }
  router.replace({ name: 'login' })
}

function toggleFullscreen(): void {
  vibrate()
  isFullscreen.value = !isFullscreen.value
}

// Mobilde dblclick event'i gecikmeli/tutarsız — kendi double-tap algılayıcımız:
// iki touchend arası < 300ms ve arada çekme jesti yoksa tam ekran toggle.
// Ardından tarayıcının üretebileceği sentetik dblclick'i kısa süre bastırıyoruz
// ki toggle iki kez çalışıp eski durumuna geri dönmesin.
const DOUBLE_TAP_MS = 300
let lastTapAt = 0
let suppressDblclickUntil = 0

function onDblclick(): void {
  if (Date.now() < suppressDblclickUntil) return
  toggleFullscreen()
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
  const pulled = pullDistance.value
  if (pulling.value && pulled > PULL_THRESHOLD) {
    reconnect()
  }
  pulling.value = false
  pullDistance.value = 0

  // Double-tap tespiti — çekme jestiyle karışmasın diye yalnızca parmak
  // neredeyse hiç hareket etmediyse sayılır.
  if (pulled < 10) {
    const now = Date.now()
    if (now - lastTapAt < DOUBLE_TAP_MS) {
      lastTapAt = 0
      suppressDblclickUntil = now + 500
      toggleFullscreen()
    } else {
      lastTapAt = now
    }
  }
}

function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  // Anchor'ın DOM'a eklenmesi gerekiyor — bazı tarayıcılar/otomasyon
  // ortamları detached bir elemanda click()'i indirme olarak saymıyor.
  document.body.appendChild(a)
  a.click()
  a.remove()
  // revoke'u hemen çağırmak, indirme henüz blob'u okumaya başlamadan
  // URL'yi geçersiz kılabilir; bir sonraki tick'e erteliyoruz.
  setTimeout(() => URL.revokeObjectURL(url), 0)
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
      const filename = `visionguard-${Date.now()}.jpg`
      const file = new File([blob], filename, { type: 'image/jpeg' })
      // Telefonda native paylaşım menüsü (Fotoğraflar'a kaydet, mesajla gönder
      // vb.) indirmeye göre çok daha doğal — a.download iOS standalone
      // PWA'larda ayrıca güvenilmez. Desteklenmeyen yerde indirmeye düşülür.
      if (navigator.canShare?.({ files: [file] })) {
        navigator.share({ files: [file] }).catch(() => {
          // Kullanıcı paylaşım menüsünü iptal etti — sessizce yut.
        })
      } else {
        downloadBlob(blob, filename)
      }
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
      class="fixed inset-x-0 top-0 z-20 flex items-center justify-between gap-3 p-4"
      :style="{
        paddingTop: 'calc(var(--sat) + 1rem)',
        paddingLeft: 'calc(var(--sal) + 1rem)',
        paddingRight: 'calc(var(--sar) + 1rem)',
      }"
    >
      <div
        class="flex min-w-0 items-center gap-2 rounded-full border border-guard-border bg-guard-surface/80 px-3 py-1.5 text-sm text-guard-secondary backdrop-blur-md"
      >
        <span
          class="h-2 w-2 shrink-0 rounded-full"
          :class="[statusMeta.dotClass, connection.status === 'live' && 'animate-pulse']"
        />
        <span class="truncate">{{ statusMeta.label }}</span>
        <!-- fps > 0 koşulu: ESP32 bağlı ama henüz kare akmıyorken (ilk
        bağlanma anı, ya da bağlı-ama-sessiz kenar durumu) "0.0 FPS" gibi
        tuhaf bir gösterge yerine yalnızca durum etiketi görünür. -->
        <span
          v-if="connection.status === 'live' && connection.fps > 0"
          class="shrink-0 font-mono text-guard-primary tabular-nums"
        >
          {{ connection.fps.toFixed(1) }} FPS
        </span>
      </div>

      <button
        type="button"
        class="flex h-11 w-11 items-center justify-center rounded-full border border-guard-border bg-guard-surface/80 text-guard-secondary backdrop-blur-md transition-colors hover:text-brand active:scale-95"
        @click="goAdmin"
      >
        <AppIcon :svg="actionSettingsSvg" class="h-5 w-5" />
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
      @dblclick="onDblclick"
    >
      <img
        v-if="streamActive"
        ref="streamImg"
        :src="streamUrl"
        alt="Canlı yayın"
        draggable="false"
        class="max-h-full max-w-full object-contain"
        :class="isFullscreen ? 'rounded-none' : 'rounded-2xl'"
        @error="onStreamError"
      />
      <div v-else class="flex flex-col items-center gap-3 px-4 text-center">
        <img
          :src="emptyStateMeta.icon"
          alt=""
          class="h-16 w-16"
          :class="emptyStateMeta.spin && 'animate-spin-slow'"
        />
        <p class="text-sm text-guard-secondary">{{ emptyStateMeta.text }}</p>
      </div>
    </div>

    <!-- Alt aksiyon çubuğu -->
    <footer
      v-if="!isFullscreen"
      class="fixed inset-x-0 bottom-0 z-20 flex justify-center p-4"
      :style="{
        paddingBottom: 'calc(var(--sab) + 1rem)',
        paddingLeft: 'calc(var(--sal) + 1rem)',
        paddingRight: 'calc(var(--sar) + 1rem)',
      }"
    >
      <div
        class="flex items-center gap-1 rounded-full border border-guard-border bg-guard-surface/80 p-1.5 backdrop-blur-md"
      >
        <button
          type="button"
          class="flex min-h-11 items-center gap-2 rounded-full px-4 py-2.5 text-sm font-medium text-guard-secondary transition-colors hover:bg-guard-elevated hover:text-guard-primary active:scale-95"
          @click="logout"
        >
          <AppIcon :svg="actionLogoutSvg" class="h-5 w-5" />
          Çıkış
        </button>
        <button
          type="button"
          class="flex min-h-11 items-center gap-2 rounded-full px-4 py-2.5 text-sm font-medium text-guard-secondary transition-colors hover:bg-guard-elevated hover:text-guard-primary active:scale-95"
          @click="toggleFullscreen"
        >
          Tam Ekran
        </button>
        <button
          type="button"
          :disabled="connection.status !== 'live'"
          class="flex min-h-11 items-center gap-2 rounded-full px-4 py-2.5 text-sm font-medium text-guard-secondary transition-colors hover:bg-guard-elevated hover:text-guard-primary active:scale-95 disabled:pointer-events-none disabled:opacity-40"
          @click="downloadSnapshot"
        >
          Snapshot
        </button>
      </div>
    </footer>
  </main>
</template>
