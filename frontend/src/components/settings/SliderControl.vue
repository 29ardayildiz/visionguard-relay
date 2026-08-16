<script setup lang="ts">
import { debounce } from '../../lib/debounce'

const props = defineProps<{
  label: string
  modelValue: number
  min: number
  max: number
}>()

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
        class="h-1 w-full flex-1 cursor-pointer accent-brand-accent"
        @input="onInput"
        @pointerup="onPointerUp"
      />
      <span class="w-10 shrink-0 text-right font-mono text-xs text-brand-accent tabular-nums">
        {{ modelValue }}
      </span>
    </div>
  </div>
</template>
