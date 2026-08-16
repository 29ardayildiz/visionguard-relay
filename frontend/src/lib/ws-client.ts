// Tarayıcının /ws/client kanalına bağlanan, framework-bağımsız WebSocket
// istemcisi. Exponential backoff ile reconnect eder ve MASTER.md §11.2'deki
// üç durumlu (waking/offline/live) bağlantı state machine'ini yönetir.
//
// Durum mantığı:
// - 'waking'  : WS henüz bağlı değil (ilk bağlantı ya da reconnect sırasında).
//               Render cold-start senaryosunda bu durumda uzun süre kalınır.
// - 'offline' : WS bağlı ama ESP32 kapalı (health.esp32_connected === false).
// - 'live'    : WS bağlı ve ESP32 aktif yayında.

export type ConnectionStatus = 'waking' | 'offline' | 'live'

export interface HealthPayload {
  type: 'health'
  fps: number
  esp32_connected: boolean
  mode: 'websocket' | 'push' | 'none'
}

export interface SettingsPayload {
  type: 'settings'
  esp32_connected: boolean
  [key: string]: unknown
}

type Unsubscribe = () => void

const RECONNECT_BASE_MS = 1000
const RECONNECT_MAX_MS = 15000

export class WsClient {
  private ws: WebSocket | null = null
  private reconnectDelay = RECONNECT_BASE_MS
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private manuallyClosed = true
  private status: ConnectionStatus = 'waking'

  private healthListeners = new Set<(payload: HealthPayload) => void>()
  private settingsListeners = new Set<(payload: SettingsPayload) => void>()
  private statusListeners = new Set<(status: ConnectionStatus) => void>()

  connect(): void {
    this.manuallyClosed = false
    this.open()
  }

  disconnect(): void {
    this.manuallyClosed = true
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    this.ws?.close()
    this.ws = null
  }

  reconnectNow(): void {
    this.disconnect()
    this.reconnectDelay = RECONNECT_BASE_MS
    this.connect()
  }

  onHealth(fn: (payload: HealthPayload) => void): Unsubscribe {
    this.healthListeners.add(fn)
    return () => this.healthListeners.delete(fn)
  }

  onSettings(fn: (payload: SettingsPayload) => void): Unsubscribe {
    this.settingsListeners.add(fn)
    return () => this.settingsListeners.delete(fn)
  }

  onStatus(fn: (status: ConnectionStatus) => void): Unsubscribe {
    this.statusListeners.add(fn)
    fn(this.status)
    return () => this.statusListeners.delete(fn)
  }

  private setStatus(next: ConnectionStatus): void {
    if (this.status === next) return
    this.status = next
    this.statusListeners.forEach((fn) => fn(next))
  }

  private open(): void {
    this.setStatus('waking')

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}/ws/client`
    const ws = new WebSocket(url)
    this.ws = ws

    ws.onopen = () => {
      this.reconnectDelay = RECONNECT_BASE_MS
    }

    ws.onmessage = (event: MessageEvent<string>) => {
      let data: (HealthPayload | SettingsPayload) & { type: string }
      try {
        data = JSON.parse(event.data)
      } catch {
        return
      }

      if (data.type === 'health') {
        const payload = data as HealthPayload
        this.setStatus(payload.esp32_connected ? 'live' : 'offline')
        this.healthListeners.forEach((fn) => fn(payload))
      } else if (data.type === 'settings') {
        this.settingsListeners.forEach((fn) => fn(data as SettingsPayload))
      }
    }

    ws.onclose = () => {
      this.ws = null
      if (this.manuallyClosed) return
      this.setStatus('waking')
      const delay = this.reconnectDelay
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, RECONNECT_MAX_MS)
      this.reconnectTimer = setTimeout(() => {
        if (!this.manuallyClosed) this.open()
      }, delay)
    }

    ws.onerror = () => {
      ws.close()
    }
  }
}
