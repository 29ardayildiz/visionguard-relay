<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import appIconUrl from '../icons/pwa/app-icon.svg'
import { isAuthenticated, login } from '../lib/auth'

const router = useRouter()

const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref(false)
const shaking = ref(false)

onMounted(async () => {
  if (await isAuthenticated()) {
    router.replace({ name: 'viewer' })
  }
})

function vibrate() {
  if ('vibrate' in navigator) {
    navigator.vibrate(10)
  }
}

async function handleSubmit() {
  if (loading.value) return
  loading.value = true
  error.value = false

  const ok = await login(username.value, password.value)

  loading.value = false

  if (ok) {
    // push değil replace: giriş yapmış bir kullanıcının "geri" jestiyle
    // login formuna dönmesi istenmiyor — bu bir durum geçişi, drill-in değil.
    router.replace({ name: 'viewer' })
    return
  }

  error.value = true
  vibrate()
  shaking.value = true
  setTimeout(() => {
    shaking.value = false
  }, 400)
}
</script>

<template>
  <main class="flex min-h-full items-center justify-center bg-guard-bg p-4">
    <form
      :class="[
        'w-full max-w-sm rounded-2xl border border-guard-border bg-guard-surface/80 p-8 backdrop-blur-md',
        shaking && 'animate-shake',
      ]"
      @submit.prevent="handleSubmit"
    >
      <div class="mb-6 flex flex-col items-center gap-2">
        <img :src="appIconUrl" alt="VisionGuard" class="h-18 w-18" />
        <h1 class="text-lg font-semibold text-guard-primary">VisionGuard</h1>
        <p class="text-xs text-guard-secondary">Güvenli Kamera Erişimi</p>
      </div>

      <div class="space-y-4">
        <div class="relative">
          <input
            id="username"
            v-model="username"
            type="text"
            autocomplete="username"
            required
            autofocus
            placeholder=" "
            class="peer w-full rounded-lg border border-guard-border bg-guard-elevated px-4 pt-5 pb-2 text-sm text-guard-primary outline-none focus:border-brand"
          />
          <label
            for="username"
            class="pointer-events-none absolute top-1 left-4 text-xs text-guard-secondary transition-all peer-placeholder-shown:top-3.5 peer-placeholder-shown:text-sm peer-focus:top-1 peer-focus:text-xs peer-focus:text-brand"
          >
            Kullanıcı Adı
          </label>
        </div>

        <div class="relative">
          <input
            id="password"
            v-model="password"
            type="password"
            autocomplete="current-password"
            required
            placeholder=" "
            class="peer w-full rounded-lg border border-guard-border bg-guard-elevated px-4 pt-5 pb-2 text-sm text-guard-primary outline-none focus:border-brand"
          />
          <label
            for="password"
            class="pointer-events-none absolute top-1 left-4 text-xs text-guard-secondary transition-all peer-placeholder-shown:top-3.5 peer-placeholder-shown:text-sm peer-focus:top-1 peer-focus:text-xs peer-focus:text-brand"
          >
            Şifre
          </label>
        </div>
      </div>

      <p
        v-if="error"
        class="selectable mt-4 rounded-lg border border-status-offline/30 bg-status-offline/10 px-3 py-2 text-center text-xs text-status-offline"
      >
        Kullanıcı adı veya şifre hatalı.
      </p>

      <button
        type="submit"
        :disabled="loading"
        class="mt-6 w-full rounded-xl bg-brand py-3 text-sm font-bold text-guard-bg transition-all hover:bg-brand-hover active:scale-[0.98] disabled:opacity-60"
      >
        {{ loading ? 'Giriş yapılıyor...' : 'Giriş Yap' }}
      </button>
    </form>
  </main>
</template>
