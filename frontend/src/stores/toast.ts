import { ref } from 'vue'
import { defineStore } from 'pinia'

export type ToastKind = 'ok' | 'err'

export const useToastStore = defineStore('toast', () => {
  const message = ref('')
  const kind = ref<ToastKind>('ok')
  const visible = ref(false)
  let hideTimer: ReturnType<typeof setTimeout> | null = null

  function show(msg: string, type: ToastKind = 'ok'): void {
    message.value = msg
    kind.value = type
    visible.value = true
    if (hideTimer) clearTimeout(hideTimer)
    hideTimer = setTimeout(() => {
      visible.value = false
    }, 2500)
  }

  return { message, kind, visible, show }
})
