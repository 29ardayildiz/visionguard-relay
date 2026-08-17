<script setup lang="ts">
import AppIcon from '../AppIcon.vue'

defineProps<{
  title: string
  icon: string
}>()
</script>

<template>
  <section class="overflow-hidden rounded-2xl border border-guard-border bg-guard-surface">
    <header class="flex items-center gap-2 border-b border-guard-border bg-guard-elevated/40 px-4 py-2.5">
      <AppIcon :svg="icon" class="h-5 w-5 text-brand" />
      <h3 class="text-sm font-semibold text-guard-primary">{{ title }}</h3>
    </header>
    <div class="space-y-5 p-4">
      <slot />
    </div>
  </section>
</template>
