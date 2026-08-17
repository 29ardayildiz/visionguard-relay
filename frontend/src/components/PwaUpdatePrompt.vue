<script setup lang="ts">
import appIconUrl from '../icons/pwa/app-icon.svg'
import { usePwaUpdate } from '../composables/usePwaUpdate'

// Destructure şart: usePwaUpdate düz obje döndürür (Pinia store değil), bu
// yüzden ref'ler ancak top-level değişken olarak template'te unwrap edilir.
const { showPrompt, updating, applyUpdate, dismiss } = usePwaUpdate()

function vibrate(): void {
  if ('vibrate' in navigator) navigator.vibrate(10)
}

function onUpdate(): void {
  vibrate()
  void applyUpdate()
}

function onLater(): void {
  vibrate()
  dismiss()
}
</script>

<template>
  <Transition name="toast">
    <div
      v-if="showPrompt"
      class="fixed inset-x-0 bottom-0 z-50 flex justify-center px-4"
      :style="{ paddingBottom: 'calc(var(--sab) + 1rem)' }"
    >
      <div
        class="flex w-full max-w-sm items-center gap-3 rounded-2xl border border-guard-border bg-guard-surface p-4 shadow-2xl backdrop-blur-md"
      >
        <img :src="appIconUrl" alt="" class="h-10 w-10 shrink-0" />
        <div class="min-w-0 flex-1">
          <p class="text-sm font-semibold text-guard-primary">Yeni sürüm hazır</p>
          <p class="mt-0.5 text-xs text-guard-secondary">
            Şimdi güncelleyebilir veya sonraya bırakabilirsiniz
          </p>
        </div>
        <button
          type="button"
          :disabled="updating"
          class="shrink-0 rounded-lg bg-brand px-3 py-2 text-xs font-bold text-guard-bg transition-all active:scale-95 hover:bg-brand-hover disabled:opacity-60"
          @click="onUpdate"
        >
          {{ updating ? '...' : 'Güncelle' }}
        </button>
        <button
          type="button"
          class="shrink-0 rounded-lg px-2 py-2 text-xs text-guard-secondary transition-all active:scale-95 hover:text-guard-primary"
          @click="onLater"
        >
          Sonra
        </button>
      </div>
    </div>
  </Transition>
</template>
