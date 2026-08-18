import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

// Tarayıcının varsayılan "Add to Home Screen" banner'ı engellenip
// (preventDefault), yerine MASTER.md §12'deki özel karta karar verilene
// kadar event saklanır. Sadece Chromium tabanlı tarayıcılar bu event'i
// destekler (Android Chrome, masaüstü Chrome/Edge) — iOS Safari hiç
// desteklemez, orada ayrı bir manuel talimat kartı gösterilir.
interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

function isStandaloneDisplay(): boolean {
  const nav = window.navigator as Navigator & { standalone?: boolean }
  return window.matchMedia('(display-mode: standalone)').matches || nav.standalone === true
}

function isIOSDevice(): boolean {
  return /iphone|ipad|ipod/i.test(window.navigator.userAgent)
}

// iOS kartı her ziyarette (hasSeenLive beklemeden) gösterildiği için kapatma
// tercihi oturumluk değil kalıcı olmalı — yoksa her açılışta yeniden çıkıp
// nag'e dönüşür. Chromium tarafında da aynı kalıcılık zarar vermez.
const DISMISSED_KEY = 'vg_install_dismissed'

export const useInstallStore = defineStore('install', () => {
  const deferredEvent = ref<BeforeInstallPromptEvent | null>(null)
  const installed = ref(isStandaloneDisplay())
  const dismissed = ref(localStorage.getItem(DISMISSED_KEY) === '1')
  let listening = false

  const isIOS = isIOSDevice()

  // Chromium: gerçek native install prompt tetiklenebilir.
  const canPromptInstall = computed(() => !!deferredEvent.value && !installed.value && !dismissed.value)
  // iOS Safari: beforeinstallprompt hiç ateşlenmez, manuel talimat gösterilir.
  const showIOSInstructions = computed(() => isIOS && !installed.value && !dismissed.value)
  const canShowInstallCard = computed(() => canPromptInstall.value || showIOSInstructions.value)

  function listen(): void {
    if (listening) return
    listening = true
    window.addEventListener('beforeinstallprompt', (event) => {
      event.preventDefault()
      deferredEvent.value = event as BeforeInstallPromptEvent
    })
    window.addEventListener('appinstalled', () => {
      installed.value = true
      deferredEvent.value = null
    })
  }

  async function promptInstall(): Promise<void> {
    if (!deferredEvent.value) return
    await deferredEvent.value.prompt()
    const choice = await deferredEvent.value.userChoice
    if (choice.outcome === 'accepted') installed.value = true
    deferredEvent.value = null
  }

  function dismiss(): void {
    dismissed.value = true
    localStorage.setItem(DISMISSED_KEY, '1')
  }

  return { canPromptInstall, showIOSInstructions, canShowInstallCard, listen, promptInstall, dismiss }
})
