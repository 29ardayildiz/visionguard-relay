<script setup lang="ts">
import { useToastStore } from '../stores/toast'

const toast = useToastStore()
</script>

<template>
  <Transition name="toast">
    <div v-if="toast.visible" class="fixed inset-x-0 bottom-24 z-40 flex justify-center px-4">
      <div
        class="selectable rounded-xl border px-4 py-2 text-xs font-medium backdrop-blur-md"
        :class="
          toast.kind === 'ok'
            ? 'border-brand/30 bg-brand/10 text-brand-accent'
            : 'border-status-offline/30 bg-status-offline/10 text-status-offline'
        "
      >
        {{ toast.message }}
      </div>
    </div>
  </Transition>
</template>
