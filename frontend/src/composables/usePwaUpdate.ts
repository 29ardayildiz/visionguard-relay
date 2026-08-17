import { computed, ref, type Ref } from 'vue'
import { useRegisterSW } from 'virtual:pwa-register/vue'

// PWA güncelleme akışının tamamı bu composable'da yaşar; PwaUpdatePrompt.vue
// sadece bunu tüketen ince bir UI katmanıdır.
//
// Tasarım kuralları:
// - ASLA otomatik reload yok: yeni service worker "waiting" durumunda bekler,
//   yalnızca kullanıcı "Güncelle"ye basınca (applyUpdate) aktive edilir.
// - Modül seviyesi singleton: useRegisterSW her çağrıldığında yeni bir SW
//   kaydı başlattığı ve listener/interval'ların bir kez kurulması gerektiği
//   için, tüm state modül kapsamında bir kez oluşturulur — composable kaç
//   component'ten çağrılırsa çağrılsın aynı instance'ı paylaşır.
// - SW dosyası backend tarafından zaten `Cache-Control: no-store` ile servis
//   edildiği için (backend/app.py güvenlik middleware'i), güncel sw.js'i
//   görmek için ayrıca cache-bypass fetch hilesine gerek yok —
//   registration.update() yeterli.

const FOREGROUND_DEBOUNCE_MS = 15_000
const CHECK_INTERVAL_MS = 5 * 60_000

type UpdateCheckReason = 'init' | 'foreground' | 'interval' | 'online'

interface PwaUpdateState {
  needRefresh: Ref<boolean>
  updateServiceWorker: (reloadPage?: boolean) => Promise<void>
}

let state: PwaUpdateState | null = null
let swRegistration: ServiceWorkerRegistration | undefined
let lastCheckAt = 0
let intervalTimer: ReturnType<typeof setInterval> | null = null

const dismissed = ref(false)
const updating = ref(false)

async function checkForUpdate(reason: UpdateCheckReason, force = false): Promise<void> {
  if (!swRegistration) return
  const now = Date.now()
  if (!force && now - lastCheckAt < FOREGROUND_DEBOUNCE_MS) return
  lastCheckAt = now
  try {
    await swRegistration.update()
  } catch {
    // Offline / geçici ağ hatası — sessizce yut, bir sonraki tetikleyici dener.
  }
}

function installGlobalListeners(): void {
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      void checkForUpdate('foreground')
    }
  })

  window.addEventListener('online', () => {
    void checkForUpdate('online', true)
  })

  intervalTimer = setInterval(() => {
    if (document.visibilityState === 'visible') {
      void checkForUpdate('interval')
    }
  }, CHECK_INTERVAL_MS)
  // App ömrü boyunca yaşayan kasıtlı bir interval; referans yalnızca
  // testte/ileride temizleme gerekirse diye tutuluyor.
  void intervalTimer
}

function ensureInitialized(): PwaUpdateState {
  if (state) return state

  const { needRefresh, updateServiceWorker } = useRegisterSW({
    immediate: true,
    onRegisteredSW(_swUrl, registration) {
      swRegistration = registration
      void checkForUpdate('init', true)
    },
  })

  installGlobalListeners()
  state = { needRefresh, updateServiceWorker }
  return state
}

export function usePwaUpdate() {
  const s = ensureInitialized()

  const showPrompt = computed(() => s.needRefresh.value && !dismissed.value)

  async function applyUpdate(): Promise<void> {
    if (updating.value) return
    updating.value = true
    // Tek reload noktası: waiting worker'a skipWaiting mesajı gönderir ve
    // sayfayı yeniler. Kullanıcı butona basmadan buraya asla gelinmez.
    await s.updateServiceWorker(true)
  }

  function dismiss(): void {
    // Oturum boyunca gizli kalır; kullanıcı uygulamayı bir sonraki tam
    // açışında (güncelleme hâlâ bekliyorsa) kartı tekrar görür.
    dismissed.value = true
  }

  return { showPrompt, updating, applyUpdate, dismiss }
}
