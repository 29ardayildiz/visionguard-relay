<script setup lang="ts">
import { computed } from 'vue'

import { debounce } from '../../lib/debounce'

const props = defineProps<{
  label: string
  modelValue: number
  min: number
  max: number
}>()

// Dolgu (progress) rengi: native range input'ta cross-browser "lower fill"
// olmadığı için iz, iki renkli bir linear-gradient ile boyanır (MASTER.md
// §9.4: dolgu brand-accent, zemin guard-elevated).
const fillPercent = computed(() =>
  props.max === props.min ? 0 : ((props.modelValue - props.min) / (props.max - props.min)) * 100,
)
// `background` shorthand DEĞİL, `backgroundImage`: shorthand, index.css'teki
// background-clip: content-box'ı (44px dokunma alanı / 4px görsel iz ayrımını
// sağlayan mekanizma) sıfırlardı.
const trackStyle = computed(() => ({
  backgroundImage: `linear-gradient(to right, var(--color-brand-accent) 0%, var(--color-brand-accent) ${fillPercent.value}%, var(--color-guard-elevated) ${fillPercent.value}%, var(--color-guard-elevated) 100%)`,
}))

const emit = defineEmits<{
  'update:modelValue': [value: number]
  commit: [value: number]
}>()

// MASTER.md §11.3: sürüklerken anlık değer gösterilir (aşağıdaki mono
// rozet), backend'e 300ms debounce sonrası ya da parmak çekildiğinde
// (pointerup -> flush) istek gönderilir.
const debouncedCommit = debounce((value: number) => emit('commit', value), 300)

function onInput(event: Event): void {
  const value = Number((event.target as HTMLInputElement).value)
  emit('update:modelValue', value)
  debouncedCommit(value)
}

function onPointerUp(event: Event): void {
  const value = Number((event.target as HTMLInputElement).value)
  debouncedCommit.flush(value)
}
</script>

<template>
  <div class="flex items-center gap-4">
    <label class="w-28 shrink-0 text-xs text-guard-secondary">{{ label }}</label>
    <div class="flex flex-1 items-center gap-3">
      <input
        type="range"
        :min="min"
        :max="max"
        :value="modelValue"
        :style="trackStyle"
        class="w-full flex-1 cursor-pointer"
        @input="onInput"
        @pointerup="onPointerUp"
      />
      <span class="w-8 shrink-0 text-right font-mono text-xs text-brand-accent tabular-nums">
        {{ modelValue }}
      </span>
    </div>
  </div>
</template>
