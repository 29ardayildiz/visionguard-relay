<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import appIconUrl from '../icons/pwa/app-icon.svg'
import { login } from '../lib/auth'

const router = useRouter()

const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref(false)
const shaking = ref(false)

const DRAFT_USER_KEY = 'vg_draft_username'

onMounted(() => {
  const savedUser = sessionStorage.getItem(DRAFT_USER_KEY)
  if (savedUser) username.value = savedUser
})

function onUsernameInput(): void {
  sessionStorage.setItem(DRAFT_USER_KEY, username.value)
}

function vibrate(): void {
  if ('vibrate' in navigator) {
    navigator.vibrate(10)
  }
}

function dismissKeyboard(event: MouseEvent): void {
  if ((event.target as HTMLElement).tagName !== 'INPUT') {
    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur()
    }
  }
}

async function handleSubmit() {
  if (loading.value) return
  loading.value = true
  error.value = false

  const ok = await login(username.value, password.value)

  loading.value = false

  if (ok) {
    sessionStorage.removeItem(DRAFT_USER_KEY)
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
  <main
    class="flex min-h-full items-center justify-center bg-guard-bg p-4"
    :style="{
      paddingTop: 'calc(var(--sat) + 1rem)',
      paddingBottom: 'calc(var(--sab) + 1rem)',
      paddingLeft: 'calc(var(--sal) + 1rem)',
      paddingRight: 'calc(var(--sar) + 1rem)',
    }"
    @click="dismissKeyboard"
  >
    <form
      :class="[
        'w-full max-w-sm rounded-2xl border border-guard-border bg-guard-surface/80 p-6 backdrop-blur-md sm:p-8',
        shaking && 'animate-shake',
      ]"
      novalidate
      @submit.prevent="handleSubmit"
    >
      <div class="mb-6 flex flex-col items-center gap-2">
        <img :src="appIconUrl" alt="VisionGuard Logo" class="h-18 w-18" />
        <h1 class="text-lg font-semibold text-guard-primary">VisionGuard</h1>
        <p class="text-xs text-guard-secondary">Güvenli Kamera Erişimi</p>
      </div>

      <div class="space-y-4">
        <div class="relative">
          <input
            id="username"
            v-model="username"
            type="text"
            inputmode="text"
            autocapitalize="none"
            autocorrect="off"
            spellcheck="false"
            enterkeyhint="next"
            autocomplete="username"
            required
            autofocus
            placeholder=" "
            :aria-invalid="error ? 'true' : 'false'"
            aria-describedby="login-error"
            class="peer w-full rounded-lg border border-guard-border bg-guard-elevated px-4 pt-5 pb-2 text-base text-guard-primary outline-none focus:border-brand"
            @input="onUsernameInput"
          />
          <label
            for="username"
            class="pointer-events-none absolute top-1 left-4 text-xs text-guard-secondary transition-all peer-placeholder-shown:top-3.5 peer-placeholder-shown:text-base peer-focus:top-1 peer-focus:text-xs peer-focus:text-brand"
          >
            Kullanıcı Adı
          </label>
        </div>

        <div class="relative">
          <input
            id="password"
            v-model="password"
            type="password"
            enterkeyhint="done"
            autocomplete="current-password"
            required
            placeholder=" "
            :aria-invalid="error ? 'true' : 'false'"
            aria-describedby="login-error"
            class="peer w-full rounded-lg border border-guard-border bg-guard-elevated px-4 pt-5 pb-2 text-base text-guard-primary outline-none focus:border-brand"
          />
          <label
            for="password"
            class="pointer-events-none absolute top-1 left-4 text-xs text-guard-secondary transition-all peer-placeholder-shown:top-3.5 peer-placeholder-shown:text-base peer-focus:top-1 peer-focus:text-xs peer-focus:text-brand"
          >
            Şifre
          </label>
        </div>
      </div>

      <p
        v-if="error"
        id="login-error"
        role="alert"
        aria-live="assertive"
        class="selectable mt-4 rounded-lg border border-status-offline/30 bg-status-offline/10 px-3 py-2 text-center text-sm text-status-offline"
      >
        Kullanıcı adı veya şifre hatalı.
      </p>

      <button
        type="submit"
        :disabled="loading"
        class="mt-6 w-full rounded-xl bg-brand py-3 text-base font-bold text-guard-bg transition-all hover:bg-brand-hover active:scale-[0.98] disabled:opacity-60"
      >
        {{ loading ? 'Giriş yapılıyor...' : 'Giriş Yap' }}
      </button>
    </form>
  </main>
</template>

