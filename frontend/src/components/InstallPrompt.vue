<script setup lang="ts">
import { computed } from 'vue'

import appIconUrl from '../icons/pwa/app-icon.svg'
import { useConnectionStore } from '../stores/connection'
import { useInstallStore } from '../stores/install'

const connection = useConnectionStore()
const install = useInstallStore()

// iOS: programatik install imkânsız (beforeinstallprompt yok) — talimat kartı
// ilk ziyaretten itibaren hemen gösterilir ki kullanıcı PWA'yı keşfedebilsin.
// Chromium: native prompt elimizde, kart canlı yayın ilk izlendikten sonra
// gösterilir (MASTER.md §12 — değer görülmeden install isteme).
const visible = computed(
  () =>
    install.canShowInstallCard &&
    (install.showIOSInstructions || connection.hasSeenLive),
)

function onInstallClick(): void {
  void install.promptInstall()
}
</script>

<template>
  <Transition name="toast">
    <div
      v-if="visible"
      role="region"
      aria-label="Uygulama Yükleme Bildirimi"
      class="fixed inset-x-0 bottom-0 z-50 flex justify-center px-4"
      :style="{ paddingBottom: 'calc(var(--sab) + 1rem)' }"
    >
      <div
        class="selectable flex w-full max-w-sm items-center gap-3 rounded-2xl border border-guard-border bg-guard-surface p-4 shadow-2xl backdrop-blur-md"
      >
        <img :src="appIconUrl" alt="" class="h-10 w-10 shrink-0" />
        <div class="min-w-0 flex-1">
          <p class="text-sm font-semibold text-guard-primary">VisionGuard'ı Ana Ekrana Ekle</p>
          <p v-if="install.showIOSInstructions && !install.canPromptInstall" class="mt-0.5 text-xs text-guard-secondary">
            Paylaş simgesine dokunup "Ana Ekrana Ekle"yi seçin
          </p>
          <p v-else class="mt-0.5 text-xs text-guard-secondary">Native bir uygulama gibi hızlı erişim</p>
        </div>
        <button
          v-if="install.canPromptInstall"
          type="button"
          aria-label="Ana Ekrana Ekle"
          class="shrink-0 min-h-11 rounded-lg bg-brand px-4 text-sm font-bold text-guard-bg transition-colors hover:bg-brand-hover active:scale-95"
          @click="onInstallClick"
        >
          Ekle
        </button>
        <button
          type="button"
          aria-label="Bildirimi Kapat"
          class="shrink-0 min-h-11 rounded-lg px-3 text-sm text-guard-secondary transition-all active:scale-95 hover:text-guard-primary"
          @click="install.dismiss"
        >
          ✕
        </button>
      </div>
    </div>
  </Transition>
</template>
