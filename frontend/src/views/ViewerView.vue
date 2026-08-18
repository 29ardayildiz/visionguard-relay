<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import AppIcon from '../components/AppIcon.vue'
import cameraOfflineUrl from '../icons/status/camera-offline.svg'
import actionLogoutSvg from '../icons/actions/action-logout.svg?raw'
import actionSettingsSvg from '../icons/actions/action-settings.svg?raw'
import loaderWakingUrl from '../icons/status/loader-waking.svg'
import { usePwaUpdate } from '../composables/usePwaUpdate'
import { sendBroadcast } from '../lib/broadcast'
import { useConnectionStore } from '../stores/connection'

const router = useRouter()
const connection = useConnectionStore()
// Destructure şart: usePwaUpdate düz obje döndürür (Pinia store değil) —
// ref ancak top-level değişken olarak template'te unwrap edilir.
const { updateAvailable } = usePwaUpdate()

const STREAM_RETRY_MS = 3000

const streamImg = ref<HTMLImageElement | null>(null)
const streamCacheBust = ref(Date.now())
const streamUrl = computed(() => `/stream?t=${streamCacheBust.value}`)
const isFullscreen = ref(false)
let streamRetryTimer: ReturnType<typeof setTimeout> | null = null

// Stream yalnızca canlı VE uygulama öndeyken mount edilir — arka planda
// <img> DOM'dan kalkınca tarayıcı MJPEG bağlantısını kapatır (pil + veri).
const streamActive = computed(() => connection.status === 'live' && connection.appVisible)

// ── Tam ekranda dijital zoom durumu ─────────────────────────────────────────
// transform sırası `translate(tx,ty) scale(s)` — translate ekran pikselinde
// uygulanır (soldaki dönüşüm parent koordinatında çalışır), pan matematiği
// scale'den bağımsız kalır.
const ZOOM_MIN = 1
const ZOOM_MAX = 4
const zoomScale = ref(1)
const zoomTx = ref(0)
const zoomTy = ref(0)
// Double-tap zoom'da yumuşak geçiş; pinch/pan sırasında transition kapalı
// olmalı yoksa parmak takibi lastikli/gecikmeli hissettirir.
const zoomAnimated = ref(false)
const isZoomed = computed(() => zoomScale.value > 1.01)

type Gesture = 'none' | 'pan' | 'pinch'
let gesture: Gesture = 'none'
let pinchStartDist = 0
let pinchStartScale = 1
let pinchStartTx = 0
let pinchStartTy = 0
let pinchFocalX = 0
let pinchFocalY = 0
let panStartX = 0
let panStartY = 0
let panStartTx = 0
let panStartTy = 0
let tapStartX = 0
let tapStartY = 0
let tapMoved = false

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

onMounted(() => {
  // Auth kontrolü router guard'ında (render'dan önce) yapılıyor.
  connection.start()
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
  sendBroadcast({ type: 'logout' })
  try {
    await fetch('/logout', { redirect: 'manual' })
  } catch {
    // Ağ yoksa bile lokal olarak login'e dön — cookie zaten sunucuda geçersiz
    // sayılana kadar başka istek atılmayacak.
  }
  router.replace({ name: 'login' })
}

function setFullscreen(value: boolean): void {
  vibrate()
  if (!value) resetZoom(false)
  if ('startViewTransition' in document && typeof document.startViewTransition === 'function') {
    document.startViewTransition(() => {
      isFullscreen.value = value
    })
  } else {
    isFullscreen.value = value
  }
}

function toggleFullscreen(): void {
  setFullscreen(!isFullscreen.value)
}

function exitFullscreen(): void {
  setFullscreen(false)
}

function resetZoom(animated: boolean): void {
  zoomAnimated.value = animated
  zoomScale.value = 1
  zoomTx.value = 0
  zoomTy.value = 0
}

// Pan sınırı: görüntü kenarı ekran kenarının içine "kaçamaz". Ölçeklenmiş
// görüntü konteynerden küçükse eksen için sınır 0'dır (ortalanmış kalır).
function clampPan(): void {
  const img = streamImg.value
  const container = img?.parentElement
  const s = zoomScale.value
  if (!img || !container || s <= 1) {
    zoomTx.value = 0
    zoomTy.value = 0
    return
  }
  const maxTx = Math.max(0, (img.clientWidth * s - container.clientWidth) / 2)
  const maxTy = Math.max(0, (img.clientHeight * s - container.clientHeight) / 2)
  zoomTx.value = Math.min(maxTx, Math.max(-maxTx, zoomTx.value))
  zoomTy.value = Math.min(maxTy, Math.max(-maxTy, zoomTy.value))
}

function touchDistance(event: TouchEvent): number {
  const a = event.touches[0]!
  const b = event.touches[1]!
  return Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY)
}

// Konteyner merkezine göre nokta (transform-origin center olduğu için tüm
// odak-noktalı zoom matematiği bu koordinatta yürür).
function pointFromCenter(clientX: number, clientY: number): { x: number; y: number } {
  const rect = streamImg.value?.parentElement?.getBoundingClientRect()
  if (!rect) return { x: 0, y: 0 }
  return { x: clientX - (rect.left + rect.width / 2), y: clientY - (rect.top + rect.height / 2) }
}

// Mobilde dblclick event'i gecikmeli/tutarsız — kendi double-tap algılayıcımız.
// Normal modda tam ekrana girer; tam ekranda dijital zoom'u aç/kapatır
// (native video oynatıcı davranışı). Tam ekrandan çıkış YALNIZCA ✕ butonuyla.
// Tarayıcının üretebileceği sentetik dblclick'i kısa süre bastırıyoruz.
const DOUBLE_TAP_MS = 300
let lastTapAt = 0
let suppressDblclickUntil = 0

function handleDoubleTap(clientX: number, clientY: number): void {
  if (!isFullscreen.value) {
    setFullscreen(true)
    return
  }
  vibrate()
  if (isZoomed.value) {
    resetZoom(true)
  } else {
    // Dokunulan noktayı merkeze taşıyarak 2x zoom: s0=1, t0=0 için
    // t1 = f - s1*f = -f (odak-noktası formülünün özel hali).
    const focal = pointFromCenter(clientX, clientY)
    zoomAnimated.value = true
    zoomScale.value = 2
    zoomTx.value = -focal.x
    zoomTy.value = -focal.y
    clampPan()
  }
}

function onDblclick(event: MouseEvent): void {
  if (Date.now() < suppressDblclickUntil) return
  handleDoubleTap(event.clientX, event.clientY)
}

function onTouchStart(event: TouchEvent): void {
  if (isFullscreen.value && event.touches.length === 2) {
    gesture = 'pinch'
    zoomAnimated.value = false
    tapMoved = true
    pinchStartDist = touchDistance(event)
    pinchStartScale = zoomScale.value
    pinchStartTx = zoomTx.value
    pinchStartTy = zoomTy.value
    const a = event.touches[0]!
    const b = event.touches[1]!
    const focal = pointFromCenter((a.clientX + b.clientX) / 2, (a.clientY + b.clientY) / 2)
    pinchFocalX = focal.x
    pinchFocalY = focal.y
    return
  }
  if (event.touches.length !== 1) return
  const touch = event.touches[0]!
  if (isFullscreen.value && isZoomed.value) {
    gesture = 'pan'
    zoomAnimated.value = false
    panStartX = touch.clientX
    panStartY = touch.clientY
    panStartTx = zoomTx.value
    panStartTy = zoomTy.value
  } else {
    gesture = 'none'
  }
  tapStartX = touch.clientX
  tapStartY = touch.clientY
  tapMoved = false
}

function onTouchMove(event: TouchEvent): void {
  if (gesture === 'pinch' && event.touches.length >= 2) {
    event.preventDefault()
    const scale = Math.min(
      ZOOM_MAX,
      Math.max(ZOOM_MIN, pinchStartScale * (touchDistance(event) / pinchStartDist)),
    )
    // Odak-noktalı zoom: parmakların ortasındaki görüntü noktası ekranda sabit
    // kalır — t1 = f - (s1/s0) * (f - t0).
    const ratio = scale / pinchStartScale
    zoomScale.value = scale
    zoomTx.value = pinchFocalX - ratio * (pinchFocalX - pinchStartTx)
    zoomTy.value = pinchFocalY - ratio * (pinchFocalY - pinchStartTy)
    clampPan()
    return
  }
  if (gesture === 'pan' && event.touches.length === 1) {
    event.preventDefault()
    const touch = event.touches[0]!
    zoomTx.value = panStartTx + (touch.clientX - panStartX)
    zoomTy.value = panStartTy + (touch.clientY - panStartY)
    clampPan()
    // Pan yapılan parmak kalkınca double-tap sayılmasın.
    if (Math.hypot(touch.clientX - tapStartX, touch.clientY - tapStartY) > 10) tapMoved = true
    return
  }
  if (event.touches.length === 1) {
    const touch = event.touches[0]!
    if (Math.hypot(touch.clientX - tapStartX, touch.clientY - tapStartY) > 10) tapMoved = true
  }
}

function onTouchEnd(event: TouchEvent): void {
  if (gesture === 'pinch') {
    if (event.touches.length === 1) {
      // Bir parmak kalktı — kalan parmakla kesintisiz pan'a geç.
      const touch = event.touches[0]!
      gesture = 'pan'
      panStartX = touch.clientX
      panStartY = touch.clientY
      panStartTx = zoomTx.value
      panStartTy = zoomTy.value
      return
    }
    gesture = 'none'
    // 1x'e çok yakın bırakıldıysa tam 1x'e oturt (yamuk yarım-zoom kalmasın).
    if (zoomScale.value < 1.05) resetZoom(true)
    return
  }
  if (gesture === 'pan') {
    if (event.touches.length === 0) gesture = 'none'
    return
  }
  if (event.touches.length > 0 || tapMoved) return

  const now = Date.now()
  if (now - lastTapAt < DOUBLE_TAP_MS) {
    lastTapAt = 0
    suppressDblclickUntil = now + 500
    const touch = event.changedTouches[0]
    handleDoubleTap(touch?.clientX ?? tapStartX, touch?.clientY ?? tapStartY)
  } else {
    lastTapAt = now
  }
}

function onTouchCancel(): void {
  gesture = 'none'
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
        role="status"
        aria-live="polite"
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
        :aria-label="updateAvailable ? 'Kamera Ayarları (yeni sürüm mevcut)' : 'Kamera Ayarları'"
        class="relative flex h-11 w-11 items-center justify-center rounded-full border border-guard-border bg-guard-surface/80 text-guard-secondary backdrop-blur-md transition-colors hover:text-brand active:scale-95"
        @click="goAdmin"
      >
        <AppIcon :svg="actionSettingsSvg" class="h-5 w-5" />
        <!-- Yeni sürüm badge'i: pop-up yerine sessiz nokta — güncelleme
        Admin > Sürüm bölümünden elle yapılır. -->
        <span
          v-if="updateAvailable"
          aria-hidden="true"
          class="absolute right-0.5 top-0.5 h-2.5 w-2.5 rounded-full bg-brand ring-2 ring-guard-bg"
        />
      </button>
    </header>

    <!-- Stream alanı -->
    <div
      :class="[
        'flex h-full items-center justify-center overflow-hidden select-none',
        isFullscreen ? 'fixed inset-0 z-30 touch-none bg-black' : 'p-4',
      ]"
      @touchstart="onTouchStart"
      @touchmove="onTouchMove"
      @touchend="onTouchEnd"
      @touchcancel="onTouchCancel"
      @dblclick="onDblclick"
    >
      <img
        v-if="streamActive"
        ref="streamImg"
        :src="streamUrl"
        alt="Canlı kamera görüntüsü"
        draggable="false"
        class="max-h-full max-w-full object-contain"
        :class="[isFullscreen ? 'rounded-none' : 'rounded-2xl', zoomAnimated && 'zoom-animated']"
        :style="
          isFullscreen
            ? { transform: `translate(${zoomTx}px, ${zoomTy}px) scale(${zoomScale})` }
            : undefined
        "
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

      <!-- Tam ekrandan çıkış — tek çıkış yolu bu buton (double-tap artık
      zoom'a ayrıldı, native video oynatıcı deseni). -->
      <button
        v-if="isFullscreen"
        type="button"
        aria-label="Tam Ekrandan Çık"
        class="fixed z-40 flex h-11 w-11 items-center justify-center rounded-full border border-guard-border bg-guard-surface/80 text-lg text-guard-secondary backdrop-blur-md transition-colors hover:text-guard-primary active:scale-95"
        :style="{ top: 'calc(var(--sat) + 1rem)', right: 'calc(var(--sar) + 1rem)' }"
        @click="exitFullscreen"
      >
        ✕
      </button>
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
          aria-label="Oturumu Kapat"
          class="flex min-h-11 items-center gap-2 rounded-full px-4 py-2.5 text-sm font-medium text-guard-secondary transition-colors hover:bg-guard-elevated hover:text-guard-primary active:scale-95"
          @click="logout"
        >
          <AppIcon :svg="actionLogoutSvg" class="h-5 w-5" />
          Çıkış
        </button>
        <button
          type="button"
          aria-label="Tam Ekran Yap"
          class="flex min-h-11 items-center gap-2 rounded-full px-4 py-2.5 text-sm font-medium text-guard-secondary transition-colors hover:bg-guard-elevated hover:text-guard-primary active:scale-95"
          @click="toggleFullscreen"
        >
          Tam Ekran
        </button>
        <button
          type="button"
          aria-label="Anlık Fotoğraf Kaydet"
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
