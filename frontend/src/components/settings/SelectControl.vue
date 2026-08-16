<script setup lang="ts">
defineProps<{
  label: string
  modelValue: number
  options: { value: number; label: string }[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: number]
}>()

function onChange(event: Event): void {
  emit('update:modelValue', Number((event.target as HTMLSelectElement).value))
}
</script>

<template>
  <div class="flex items-center gap-4">
    <label class="w-28 shrink-0 text-xs text-guard-secondary">{{ label }}</label>
    <select
      :value="modelValue"
      class="min-h-11 flex-1 rounded-lg border border-guard-border bg-guard-bg px-3 py-2.5 text-xs text-guard-primary outline-none focus:border-brand"
      @change="onChange"
    >
      <option v-for="opt in options" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
    </select>
  </div>
</template>
