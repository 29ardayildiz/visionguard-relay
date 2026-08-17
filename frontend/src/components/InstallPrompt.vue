<script setup lang="ts">
import { computed } from 'vue'

import appIconUrl from '../icons/pwa/app-icon.svg'
import { usePwaUpdate } from '../composables/usePwaUpdate'
import { useConnectionStore } from '../stores/connection'
import { useInstallStore } from '../stores/install'

const connection = useConnectionStore()
const install = useInstallStore()
// Destructure şart: usePwaUpdate düz obje döndürdüğü için showPrompt bir Ref —
// `!pwaUpdate.showPrompt` yazılsaydı Ref objesi her zaman truthy olurdu.
const { showPrompt: updatePromptVisible } = usePwaUpdate()

// Güncelleme kartı öncelikli — ikisi de alt kenara sabitlendiği için aynı anda
// gösterilmez; güncelleme kapatılınca/uygulanınca install kartı geri gelir.
const visible = computed(
  () => connection.hasSeenLive && install.canShowInstallCard && !updatePromptVisible.value,
)

function onInstallClick(): void {
  void install.promptInstall()
}
</script>

<template>
  <Transition name="toast">
    <div
      v-if="visible"
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
          class="shrink-0 rounded-lg bg-brand px-3 py-2 text-xs font-bold text-guard-bg transition-colors hover:bg-brand-hover active:scale-95"
          @click="onInstallClick"
        >
          Ekle
        </button>
        <button
          type="button"
          class="shrink-0 rounded-lg px-2 py-2 text-xs text-guard-secondary transition-all active:scale-95 hover:text-guard-primary"
          @click="install.dismiss"
        >
          ✕
        </button>
      </div>
    </div>
  </Transition>
</template>
