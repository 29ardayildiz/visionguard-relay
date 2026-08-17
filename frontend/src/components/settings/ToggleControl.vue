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
  <!-- Satırın TAMAMI tıklanabilir (iOS Ayarlar davranışı) — 28px'lik switch'i
  parmakla hedeflemek yerine 44px+ yüksekliğindeki tüm satır dokunma alanıdır.
  Buton üzerinden gelen tıklama/klavye etkinleşmesi buraya bubble olur; butonun
  kendi handler'ı yok, çifte tetiklenme olmaz. -->
  <div class="flex min-h-12 cursor-pointer items-center justify-between gap-4" @click="toggle">
    <span class="text-sm text-guard-secondary">{{ label }}</span>
    <button
      type="button"
      role="switch"
      :aria-checked="modelValue"
      class="relative h-[31px] w-[51px] shrink-0 rounded-full transition-colors active:scale-95"
      :class="modelValue ? 'bg-brand' : 'bg-guard-elevated'"
    >
      <span
        class="absolute top-0.5 left-0.5 h-[27px] w-[27px] rounded-full bg-guard-primary shadow transition-transform"
        :class="modelValue && 'translate-x-[20px]'"
      />
    </button>
  </div>
</template>
