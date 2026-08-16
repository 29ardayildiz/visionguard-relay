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

  const client = new WsClient()
  let started = false
  const unsubscribers: Unsubscribe[] = []

  function start(): void {
    if (started) return
    started = true

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

    client.connect()
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

  return { status, fps, esp32Connected, mode, cameraSettings, hasSeenLive, start, stop, reconnectNow }
})
