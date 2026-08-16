<script setup lang="ts">
const props = defineProps<{
  label: string
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

function toggle(): void {
  emit('update:modelValue', !props.modelValue)
  if ('vibrate' in navigator) navigator.vibrate(10)
}
</script>

<template>
  <div class="flex min-h-11 items-center justify-between gap-4">
    <span class="text-xs text-guard-secondary">{{ label }}</span>
    <button
      type="button"
      role="switch"
      :aria-checked="modelValue"
      class="relative h-7 w-[50px] shrink-0 rounded-full transition-colors active:scale-95"
      :class="modelValue ? 'bg-brand' : 'bg-guard-elevated'"
      @click="toggle"
    >
      <span
        class="absolute top-0.5 left-0.5 h-6 w-6 rounded-full bg-guard-primary shadow transition-transform"
        :class="modelValue && 'translate-x-[22px]'"
      />
    </button>
  </div>
</template>
