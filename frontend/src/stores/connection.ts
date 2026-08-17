import { ref } from 'vue'
import { defineStore } from 'pinia'

import { WsClient, type ConnectionStatus } from '../lib/ws-client'

type Unsubscribe = () => void

const HAS_SEEN_LIVE_KEY = 'vg_has_seen_live'

// Tek bir /ws/client bağlantısını uygulama genelinde paylaşan store.
// Viewer ve Admin (Faz 5) aynı store'u kullanır — sayfa geçişinde bağlantı
// kopmaz, yeniden bağlanmaz.
export const useConnectionStore = defineStore('connection', () => {
  const status = ref<ConnectionStatus>('waking')
  const fps = ref(0)
  const esp32Connected = ref(false)
  const mode = ref<'websocket' | 'push' | 'none'>('none')
  const cameraSettings = ref<Record<string, unknown> | null>(null)
  // MASTER.md §12: install kartı kullanıcı canlı yayını ilk izledikten sonra
  // gösterilir — localStorage'da kalıcı, oturumlar arası hatırlanır.
  const hasSeenLive = ref(localStorage.getItem(HAS_SEEN_LIVE_KEY) === '1')

  // Native yaşam döngüsü durumu: uygulama arka plandayken stream/WS durdurulur
  // (pil + veri), internet yokken UI dürüst bir "bağlantı yok" gösterebilir.
  const appVisible = ref(document.visibilityState === 'visible')
  const networkOnline = ref(navigator.onLine)

  const client = new WsClient()
  let started = false
  let lifecycleInstalled = false
  const unsubscribers: Unsubscribe[] = []

  function installLifecycleListeners(): void {
    if (lifecycleInstalled) return
    lifecycleInstalled = true

    // Arka plana geçişte bağlantıyı BİLİNÇLİ kapatıyoruz, dönüşte taze
    // bağlantı kuruyoruz. Bu, iOS'un dondurup close event'i vermeden zombie
    // bıraktığı WebSocket'leri kökten imkânsız kılar (dönüşte socket zaten
    // hep yeni) ve native uygulamaların arka plan davranışıyla birebir aynıdır.
    document.addEventListener('visibilitychange', () => {
      appVisible.value = document.visibilityState === 'visible'
      if (!started) return
      if (appVisible.value) {
        client.reconnectNow()
      } else {
        client.disconnect()
      }
    })

    window.addEventListener('online', () => {
      networkOnline.value = true
      if (started) client.reconnectNow()
    })
    window.addEventListener('offline', () => {
      networkOnline.value = false
    })
  }

  function start(): void {
    if (started) return
    started = true
    installLifecycleListeners()

    unsubscribers.push(
      client.onStatus((next) => {
        status.value = next
        if (next === 'live' && !hasSeenLive.value) {
          hasSeenLive.value = true
          localStorage.setItem(HAS_SEEN_LIVE_KEY, '1')
        }
      }),
    )
    unsubscribers.push(
      client.onHealth((payload) => {
        fps.value = payload.fps
        esp32Connected.value = payload.esp32_connected
        mode.value = payload.mode
      }),
    )
    unsubscribers.push(
      client.onSettings((payload) => {
        const { type: _type, ...rest } = payload
        cameraSettings.value = rest
      }),
    )
    unsubscribers.push(
      client.onConnectionTrouble(() => {
        void diagnoseConnectionTrouble()
      }),
    )

    // Sayfa arka plandayken yüklendiyse (ör. sekme geri yüklemesi) bağlantıyı
    // hemen kurma — görünür olduğunda visibilitychange handler'ı kuracak.
    if (appVisible.value) client.connect()
  }

  // Art arda WS bağlantı başarısızlığında bir kez çalışır: sorun süresi dolmuş
  // JWT mi (handshake 403 -> tarayıcıda generic 1006, close code'dan ayırt
  // edilemez) yoksa ağ/cold-start mı? Tek seferlik bir /health teşhisi ile
  // ayrıştırır — CLAUDE.md'nin yasakladığı periyodik polling DEĞİLDİR.
  async function diagnoseConnectionTrouble(): Promise<void> {
    try {
      const response = await fetch('/health')
      if (response.status === 401) {
        // Oturum düştü: sonsuz "sunucu uyanıyor" yerine login'e yönlendir.
        // api.ts'teki 401 davranışıyla aynı desen (tam navigasyon = tam reset).
        window.location.href = '/login'
      }
    } catch {
      // Ağ yok / sunucu uyanıyor — reconnect döngüsü zaten denemeye devam ediyor.
    }
  }

  function stop(): void {
    started = false
    unsubscribers.forEach((unsubscribe) => unsubscribe())
    unsubscribers.length = 0
    client.disconnect()
  }

  function reconnectNow(): void {
    client.reconnectNow()
  }

  return {
    status,
    fps,
    esp32Connected,
    mode,
    cameraSettings,
    hasSeenLive,
    appVisible,
    networkOnline,
    start,
    stop,
    reconnectNow,
  }
})
