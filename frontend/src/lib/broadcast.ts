// Multi-Tab senkronizasyonu: Birden fazla sekme açıkken birinde çıkış
// yapıldığında, ayar güncellendiğinde veya SW güncellendiğinde diğer sekmeleri
// haberdar eder. Desteklenmeyen eski tarayıcılarda sessiz no-op.

export type BroadcastMessage =
  | { type: 'logout' }
  | { type: 'settings_updated'; key?: string }
  | { type: 'sw_updated' }

type MessageHandler = (message: BroadcastMessage) => void

const CHANNEL_NAME = 'visionguard_sync_channel'
let channel: BroadcastChannel | null = null
const listeners = new Set<MessageHandler>()

export function initBroadcast(): void {
  if (channel || typeof window === 'undefined' || !('BroadcastChannel' in window)) return
  try {
    channel = new BroadcastChannel(CHANNEL_NAME)
    channel.onmessage = (event: MessageEvent<BroadcastMessage>) => {
      listeners.forEach((fn) => fn(event.data))
    }
  } catch {
    // Tarayıcı güvenlik kısıtı / sandbox
  }
}

export function sendBroadcast(message: BroadcastMessage): void {
  if (!channel) initBroadcast()
  try {
    channel?.postMessage(message)
  } catch {
    // Sessiz yut
  }
}

export function onBroadcast(fn: MessageHandler): () => void {
  if (!channel) initBroadcast()
  listeners.add(fn)
  return () => {
    listeners.delete(fn)
  }
}
