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
  <!-- SliderControl ile aynı mobile-first desen: dar ekranda label üstte,
  select altta tam genişlik; sm: üzerinde yatay düzen. -->
  <div class="flex flex-col gap-1.5 sm:flex-row sm:items-center sm:gap-4">
    <label class="text-sm text-guard-secondary sm:w-28 sm:shrink-0">{{ label }}</label>
    <select
      :value="modelValue"
      class="min-h-11 w-full rounded-lg border border-guard-border bg-guard-bg px-3 py-2.5 text-sm text-guard-primary outline-none focus:border-brand sm:flex-1"
      @change="onChange"
    >
      <option v-for="opt in options" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
    </select>
  </div>
</template>
